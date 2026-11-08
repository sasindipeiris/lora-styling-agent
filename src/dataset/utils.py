"""Helpers for building gold traces."""

import itertools
import json
import re
from functools import lru_cache

from ..tools import call_tool, check_outfit, requirements, search_wardrobe
from .constants import DAY_WORDS, ERROR_P, TIME_WORDS


def search_args(req, category):
    """Correct search_wardrobe arguments for one category under these requirements."""
    args = {
        "category": category,
        "min_formality": req["min_formality"],
        "max_formality": req["max_formality"],
    }
    if req["rules"]:
        args["rules"] = req["rules"]
    if category == "outerwear":
        if req["needs_waterproof"]:
            args["waterproof"] = True
        if req["needs_warm_layer"]:
            args["min_warmth"] = 2
    return args


@lru_cache(maxsize=None)
def outfit_options(venue, event_type, day, time_of_day):
    """Returns (req, [(categories, passing combos, color-only-failing combos) per feasible style])."""
    req = requirements(venue, event_type, day, time_of_day)
    extra = ("shoes",) + (
        ("outerwear",) if req["needs_warm_layer"] or req["needs_waterproof"] else ()
    )
    options = []
    for style in (("dress",), ("traditional",), ("top", "bottom")):
        cats = style + extra
        pools = [
            [it["id"] for it in search_wardrobe(**search_args(req, c))["items"]]
            for c in cats
        ]
        checked = [
            (
                list(c),
                check_outfit(list(c), venue, event_type, day, time_of_day)["failed"],
            )
            for c in itertools.product(*pools)
        ]
        good = [c for c, failed in checked if not failed]
        if good:
            options.append(
                (cats, good, [c for c, failed in checked if failed == ["colors"]])
            )
    return req, options


def add_call(msgs, name, args, train=True):
    """Append a tool call and its real result. train=False keeps the call out of the loss."""
    msgs.append(
        {
            "role": "assistant",
            "content": "",
            "train": train,
            "tool_calls": [
                {"type": "function", "function": {"name": name, "arguments": args}}
            ],
        }
    )
    result = call_tool(name, args)
    msgs.append({"role": "tool", "content": json.dumps(result)})
    return result


def venue_lookup(msgs, venue, event, said, rng):
    """Gold venue call; sometimes first tries the user's wording as event_type, gets an error, and fixes it."""
    wrong = re.sub(r"\W+", "_", re.sub(r"^(a|an|my|the) ", "", said)).strip("_")
    args = {"venue": venue, "event_type": wrong}
    if rng.random() < ERROR_P and "error" in call_tool("get_venue_info", args):
        add_call(msgs, "get_venue_info", args, train=False)
    return add_call(msgs, "get_venue_info", {"venue": venue, "event_type": event})


def record(kind, msgs, final, context=None, keys=(), key_mode="all", reject=()):
    msgs.append({"role": "assistant", "content": final})
    return {
        "kind": kind,
        "user": msgs[0]["content"],
        "context": context,
        "gold_calls": [
            tc["function"]
            for m in msgs
            if m.get("train", True)
            for tc in m.get("tool_calls", [])
        ],
        "answer_keys": list(keys),
        "key_mode": key_mode,
        "reject_keys": list(reject),
        "messages": msgs,
    }


def phrase(xs, split):
    return xs[:-1] if split == "train" else xs[-1:]


def venue_mention(v, split, rng):
    return rng.choice(
        [v["name"], v["aliases"][0]]
        if split == "train"
        else [v["name"], *v["aliases"][1:]]
    )


def when_words(day, time, split, rng):
    t = TIME_WORDS[split][time]
    if day == "monday" and rng.random() < 0.3:
        return "tonight" if split == "test" and time == "evening" else f"today {t}"
    if day == "tuesday" and rng.random() < 0.3:
        return f"tomorrow {t}"
    return f"{rng.choice(DAY_WORDS[split]).format(D=day.capitalize())} {t}"
