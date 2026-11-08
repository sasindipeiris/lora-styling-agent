"""The 4 LLM tools, a safe dispatcher, and the outfit checker used as ground truth."""

import json
import re

from .constants import MAX_RESULTS
from .dataset.constants import CATEGORIES, DAYS, TIMES
from .utils import db


class ToolError(Exception):
    pass


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _pick(value, options, field):
    """Exact match ignoring case/punctuation, else a unique prefix ('sat' -> 'saturday')."""
    q = _norm(value)
    hits = [o for o in options if _norm(o) == q] or [o for o in options if len(q) >= 3 and _norm(o).startswith(q)]
    if len(hits) != 1:
        raise ToolError(f"unknown {field} '{value}'. Options: {list(options)}")
    return hits[0]


def violates(item, rule):
    return {
        "closed_shoes": item.get("shoe_type") == "sandals",
        "no_heels": item.get("shoe_type") == "heels",
        "no_white": item.get("color") == "white",
        "covered_shoulders_knees": item.get("coverage") in ("sleeveless", "short_hem"),
    }[rule]


def get_venue_info(venue, event_type):
    names = {_norm(a): k for k, v in db()["venues"].items() for a in [k, v["name"], *v["aliases"]]}
    v = db()["venues"][names[_pick(venue, names, "venue")]]
    event = _pick(event_type, db()["events"], "event_type")
    if event not in v["events"]:
        raise ToolError(f"{v['name']} does not host '{event}'. It hosts: {v['events']}")
    lo = max(v["base_formality"], db()["events"][event]["formality"])
    return {"venue": v["name"], "city": v["city"], "setting": v["setting"], "event_type": event,
            "min_formality": lo, "max_formality": min(5, lo + db()["thresholds"]["max_overdress"]),
            "rules": sorted(set(v["rules"]) | set(db()["events"][event]["rules"]))}


def get_weather(city, day, time_of_day):
    c = _pick(city, db()["weather"], "city")
    d, t = _pick(day, DAYS, "day"), _pick(time_of_day, TIMES, "time_of_day")
    return {"city": c, "day": d, "date": db()["days"][d], "time_of_day": t, **db()["weather"][c][d][t]}


def search_wardrobe(category, min_formality, max_formality=5, rules=None, waterproof=False, min_warmth=1):
    cat = _pick(category, CATEGORIES, "category")
    rules = [_pick(r, db()["rules"], "rule") for r in ([rules] if isinstance(rules, str) else rules or [])]
    waterproof = str(waterproof).lower() == "true"
    hits = sorted((it for it in db()["wardrobe"]
                   if it["category"] == cat
                   and int(min_formality) <= it["formality"] <= int(max_formality)
                   and not any(violates(it, r) for r in rules)
                   and (it["waterproof"] or not waterproof)
                   and it["warmth"] >= int(min_warmth)),
                  key=lambda it: (it["formality"], it["id"]))
    keep = ("id", "name", "color", "formality", "warmth", "waterproof")
    return {"category": cat, "total_matches": len(hits),
            "items": [{k: it[k] for k in keep} for it in hits[:MAX_RESULTS]]}


def check_color_harmony(item_ids):
    wardrobe = {it["id"]: it for it in db()["wardrobe"]}
    ids = [str(i).strip().upper() for i in item_ids]
    if unknown := [i for i in ids if i not in wardrobe]:
        raise ToolError(f"unknown item ids: {unknown}")
    rules = db()["color_rules"]
    pairs = [sorted(p) for p in rules["clashes"]]
    clashes = [[a, b] for i, a in enumerate(ids) for b in ids[i + 1:]
               if sorted([wardrobe[a]["color"], wardrobe[b]["color"]]) in pairs]
    accents = sorted({wardrobe[i]["color"] for i in ids} - set(rules["neutrals"]))
    reasons = [f"{a} clashes with {b}" for a, b in clashes]
    if len(accents) > rules["max_accent_colors"]:
        reasons.append(f"too many accent colors {accents} (max {rules['max_accent_colors']})")
    return {"ok": not reasons, "colors": {i: wardrobe[i]["color"] for i in ids},
            "clashes": clashes, "reason": "; ".join(reasons) or "colors work together"}


TOOLS = {f.__name__: f for f in (get_venue_info, get_weather, search_wardrobe, check_color_harmony)}


def call_tool(name, args):
    """Never raises; problems come back as {'error': ...}."""
    try:
        if name not in TOOLS:
            raise ToolError(f"unknown tool '{name}'. Available: {list(TOOLS)}")
        return TOOLS[name](**(json.loads(args) if isinstance(args, str) else args))
    except (ToolError, TypeError, ValueError, KeyError) as e:
        return {"error": str(e)}


def requirements(venue, event_type, day, time_of_day):
    info = get_venue_info(venue, event_type)
    w = get_weather(info["city"], day, time_of_day)
    th = db()["thresholds"]
    return {**info, "temp_c": w["temp_c"], "rain_pct": w["rain_pct"],
            "needs_warm_layer": w["temp_c"] < th["cold_below_c"],
            "needs_waterproof": info["setting"] == "outdoor" and w["rain_pct"] > th["rain_above_pct"],
            "too_hot": w["temp_c"] >= th["hot_from_c"]}


def check_outfit(item_ids, venue, event_type, day, time_of_day):
    """{'pass', 'failed', 'details'} over: ids_exist, slots, formality, rules, cold, rain, heat, colors."""
    req = requirements(venue, event_type, day, time_of_day)
    wardrobe = {it["id"]: it for it in db()["wardrobe"]}
    ids = [str(i).strip().upper() for i in item_ids]
    items = [wardrobe[i] for i in ids if i in wardrobe]
    cats = sorted(it["category"] for it in items)
    base = [c for c in cats if c in ("top", "bottom", "dress", "traditional")]
    lo, hi = req["min_formality"], req["max_formality"]

    failures = {
        "ids_exist": [i for i in ids if i not in wardrobe],
        "slots": [] if base in (["dress"], ["traditional"], ["bottom", "top"])
                 and cats.count("shoes") == 1 and cats.count("outerwear") <= 1 else cats or ["no items"],
        "formality": [it["id"] for it in items if not lo <= it["formality"] <= hi],
        "rules": [f"{it['id']}:{r}" for it in items for r in req["rules"] if violates(it, r)],
        "cold": [] if not req["needs_warm_layer"]
                or any(it["category"] == "outerwear" and it["warmth"] >= 2 for it in items)
                else [f"{req['temp_c']}C needs outerwear with warmth >= 2"],
        "rain": [] if not req["needs_waterproof"] or any(it["waterproof"] for it in items)
                else [f"{req['rain_pct']}% rain outdoors needs a waterproof item"],
        "heat": [it["id"] for it in items if req["too_hot"] and it["warmth"] >= 3],
        "colors": [] if not items or (c := check_color_harmony([it["id"] for it in items]))["ok"]
                  else [c["reason"]],
    }
    details = {k: v for k, v in failures.items() if v}
    return {"pass": not details, "failed": list(details), "details": details}
