"""Generate train/val/test jsonl from templates and scripted gold traces.

Train and test use disjoint phrasings; test outfit requests use held-out
(venue, event, day, time) contexts. Run: python -m src.dataset.split
"""

import random

from ..tools import check_outfit
from ..utils import CFG, DATA_DIR, db, write_jsonl
from .constants import (CAT_WORDS, COLOR_Q, DAYS, EVENT_WORDS, FULL_Q, ITEM_RE, KINDS, LEVELS, NO_TOOL,
                        RECOVERY_P, SEARCH_Q, SEARCH_SPECIAL_Q, SLOTS, TIMES, VENUE_Q, WEATHER_Q)
from .utils import add_call, outfit_options, phrase, record, search_args, venue_lookup, venue_mention, when_words


def gen_full(split, rng, context):
    venue_key, event, day, time = context
    v = db()["venues"][venue_key]
    ctx = {"venue": v["name"], "event_type": event, "day": day, "time_of_day": time}
    req, options = outfit_options(*ctx.values())
    cats, good, clash = rng.choice(options)
    mention, said = venue_mention(v, split, rng), rng.choice(phrase(EVENT_WORDS[event], split))
    user = rng.choice(FULL_Q[split]).format(event=said, venue=mention, when=when_words(day, time, split, rng))

    msgs = [{"role": "user", "content": user}]
    venue_lookup(msgs, mention, event, said, rng)
    add_call(msgs, "get_weather", {"city": v["city"], "day": day, "time_of_day": time})
    for c in cats:
        add_call(msgs, "search_wardrobe", search_args(req, c))
    if clash and rng.random() < RECOVERY_P:
        bad = rng.choice(clash)
        add_call(msgs, "check_color_harmony", {"item_ids": bad})
        pick = max(good, key=lambda g: sum(a == b for a, b in zip(g, bad)))
    else:
        pick = rng.choice(good)
    add_call(msgs, "check_color_harmony", {"item_ids": pick})

    wardrobe = {it["id"]: it for it in db()["wardrobe"]}
    why = [f"formality {req['min_formality']}-{req['max_formality']}", *(db()["rules"][r] for r in req["rules"])]
    if req["needs_warm_layer"]:
        why.append(f"a warm layer for {req['temp_c']}C")
    if req["needs_waterproof"]:
        why.append(f"a waterproof layer for {req['rain_pct']}% rain")
    final = (f"For your {event.replace('_', ' ')} at {v['name']} on {day.capitalize()} {time} "
             f"({req['temp_c']}C, {req['rain_pct']}% rain), wear:\n"
             + "\n".join(f"- {wardrobe[i]['name']} ({i}, {wardrobe[i]['color']})" for i in pick)
             + f"\nIt fits {', '.join(why)}, and the colors work together.")
    return record("full_outfit", msgs, final, context=ctx)


def gen_venue(split, rng):
    v = db()["venues"][rng.choice(list(db()["venues"]))]
    event, mention = rng.choice(v["events"]), venue_mention(v, split, rng)
    said = rng.choice(phrase(EVENT_WORDS[event], split))
    msgs = [{"role": "user", "content": rng.choice(VENUE_Q[split]).format(event=said, venue=mention)}]
    r = venue_lookup(msgs, mention, event, said, rng)
    rules = [db()["rules"][x] for x in r["rules"]]
    final = (f"For a {event.replace('_', ' ')} at {r['venue']} ({r['city']}, {r['setting']}), aim for formality "
             f"{r['min_formality']}-{r['max_formality']} on a 1-5 scale. "
             + (f"Dress rules: {', '.join(rules)}." if rules else "There are no special dress rules."))
    return record("single_tool", msgs, final, keys=[str(r["min_formality"]), *rules])


def gen_weather(split, rng):
    city, day, time = rng.choice(list(db()["weather"])), rng.choice(DAYS), rng.choice(TIMES)
    msgs = [{"role": "user", "content": rng.choice(WEATHER_Q[split]).format(
        city=city, when=when_words(day, time, split, rng))}]
    r = add_call(msgs, "get_weather", {"city": city, "day": day, "time_of_day": time})
    final = (f"In {city} on {day.capitalize()} {time} it will be about {r['temp_c']}C "
             f"with a {r['rain_pct']}% chance of rain.")
    return record("single_tool", msgs, final, keys=[str(r["temp_c"]), str(r["rain_pct"])])


def gen_search(split, rng):
    if rng.random() < 0.25:
        q, extra = rng.choice(SEARCH_SPECIAL_Q[split])
        args = {"category": "outerwear", "min_formality": 1, **extra}
    else:
        level, cat = rng.choice(list(LEVELS)), rng.choice(list(CAT_WORDS))
        q = rng.choice(SEARCH_Q[split]).format(level=level, cat=CAT_WORDS[cat])
        args = {"category": cat, "min_formality": LEVELS[level][0], "max_formality": LEVELS[level][1]}
    msgs = [{"role": "user", "content": q}]
    r = add_call(msgs, "search_wardrobe", args)
    if not r["items"]:
        return None
    final = "You have:\n" + "\n".join(f"- {it['name']} ({it['id']}, {it['color']}, formality {it['formality']})"
                                      for it in r["items"])
    return record("single_tool", msgs, final, keys=[it["id"] for it in r["items"]])


def gen_color(split, rng):
    ids = [it["id"] for it in rng.sample(db()["wardrobe"], rng.choice([2, 3]))]
    msgs = [{"role": "user", "content": rng.choice(COLOR_Q[split]).format(
        ids=", ".join(ids[:-1]) + " and " + ids[-1])}]
    r = add_call(msgs, "check_color_harmony", {"item_ids": ids})
    yes, no = ["work together", "go together", "match"], ["clash", "too many", "don't", "do not", "not work"]
    if r["ok"]:
        final = f"Yes, {', '.join(ids)} work together."
        return record("single_tool", msgs, final, keys=yes, key_mode="any",
                      reject=["clashes with", "too many", "not work", "not go together", "not match", "don't match"])
    final = f"No: {r['reason']}. Try swapping one of them."
    return record("single_tool", msgs, final, keys=no, key_mode="any",
                  reject=["no clash", "don't clash", "do not clash", "perfectly"])


def gen_no_tool(split, rng):
    q, a = rng.choice(NO_TOOL[split])
    slots = {k: rng.choice(v) for k, v in SLOTS.items()}
    return record("no_tool", [{"role": "user", "content": q.format(**slots)}], a.format(**slots))


def make_split(split, n, mix, contexts, rng):
    """Test requests are all distinct; train may repeat wording."""
    counts = {k: round(n * mix[k]) for k in ("no_tool", "single_tool")}
    counts["full_outfit"] = n - sum(counts.values())
    seen, singles = set(), (gen_venue, gen_weather, gen_search, gen_color)

    def take(k, gen):
        out = []
        while len(out) < k:
            r = gen(len(out))
            if r and not (split == "test" and r["user"] in seen):
                seen.add(r["user"])
                out.append(r)
        return out

    rows = (take(counts["full_outfit"], lambda i: gen_full(split, rng, contexts[i % len(contexts)]))
            + take(counts["single_tool"], lambda i: singles[i % len(singles)](split, rng))
            + take(counts["no_tool"], lambda i: gen_no_tool(split, rng)))
    rng.shuffle(rows)
    return rows


def main():
    rng, d = random.Random(CFG["seed"]), CFG["data"]

    contexts = [(k, e, day, t) for k, v in db()["venues"].items() for e in v["events"]
                for day in DAYS for t in TIMES if outfit_options(v["name"], e, day, t)[1]]
    rng.shuffle(contexts)
    n_test_full = d["n_test"] - sum(round(d["n_test"] * d["test_mix"][k]) for k in ("no_tool", "single_tool"))

    train = make_split("train", d["n_train"] + d["n_val"], d["train_mix"], contexts[n_test_full:], rng)
    splits = {"train": train[d["n_val"]:], "val": train[:d["n_val"]],
              "test": make_split("test", d["n_test"], d["test_mix"], contexts[:n_test_full], rng)}

    for r in (r for rows in splits.values() for r in rows if r["kind"] == "full_outfit"):
        assert check_outfit(ITEM_RE.findall(r["messages"][-1]["content"]), **r["context"])["pass"], r["user"]
    overlap = {r["user"] for r in splits["train"]} & {r["user"] for r in splits["test"]}
    assert not overlap, f"train/test share requests: {list(overlap)[:3]}"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for split, rows in splits.items():
        write_jsonl(DATA_DIR / f"{split}.jsonl", [{"id": f"{split}-{i:04d}", **r} for i, r in enumerate(rows)])
        print(f"{split:5s} {len(rows):5d}  " + "  ".join(f"{k}={sum(r['kind'] == k for r in rows)}" for k in KINDS))
    print(f"{len(contexts)} feasible outfit contexts, {n_test_full} held out for test")


if __name__ == "__main__":
    main()
