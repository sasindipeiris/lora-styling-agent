"""python -m src.evaluate --tag zeroshot | lora_r4 | lora_r16 [--limit N]
python -m src.evaluate --compare     -> outputs/comparison.md"""

import argparse
import json
import time
from collections import Counter

from .constants import CHAIN
from .dataset.constants import ITEM_RE, KINDS
from .dataset.utils import search_args
from .tools import call_tool, check_outfit, requirements, search_wardrobe
from .utils import DATA_DIR, OUT_DIR, read_jsonl


def call_ok(call, rec, req):
    """Right tool and arguments = the tool returns the same result as the expected call."""
    got = call_tool(call["name"], call["arguments"])
    if "error" in got:
        return False
    if rec["kind"] == "full_outfit" and call["name"] == "check_color_harmony":
        return True
    if rec["kind"] == "full_outfit" and call["name"] == "search_wardrobe":
        return got == search_wardrobe(**search_args(req, got["category"]))
    return any(
        g["name"] == call["name"] and got == call_tool(g["name"], g["arguments"])
        for g in rec["gold_calls"]
    )


def score(rec, out):
    calls = [c for s in out["steps"] for c in s["calls"]]
    valid = [c for c in calls if "invalid" not in c]
    final = (out["final"] or "").strip()
    r = {
        "id": rec["id"],
        "kind": rec["kind"],
        "n_calls": len(calls),
        "n_steps": len(out["steps"]),
    }

    if rec["kind"] == "no_tool":
        r["abstained"] = not calls
        r["success"] = r["abstained"] and bool(final)
        r["failure"] = (
            None if r["success"] else "unnecessary_call" if calls else "no_answer"
        )
        return r

    full = rec["kind"] == "full_outfit"
    req = requirements(**rec["context"]) if full else None
    ok = [call_ok(c, rec, req) for c in valid]
    complete = not full or CHAIN <= {c["name"] for c in valid}
    r["valid"] = bool(calls) and len(valid) == len(calls)
    r["call_correct"] = r["valid"] and all(ok) and complete

    if full:
        ids = list(dict.fromkeys(ITEM_RE.findall(final)))
        seen = {
            it["id"]
            for s in out["steps"]
            for res in s["results"]
            for it in res.get("items", [])
        }
        outfit = check_outfit(ids, **rec["context"])
        r.update(
            outfit_failed=outfit["failed"], unseen_ids=[i for i in ids if i not in seen]
        )
        r["success"] = bool(final) and outfit["pass"]
    else:
        text, keys = final.lower(), [k.lower() for k in rec["answer_keys"]]
        r["success"] = (
            bool(final)
            and (all if rec["key_mode"] == "all" else any)(k in text for k in keys)
            and not any(k in text for k in rec.get("reject_keys", []))
        )

    r["failure"] = (
        None
        if r["success"]
        else (
            "missing_call"
            if not calls
            else (
                "wrong_format"
                if len(valid) < len(calls)
                else (
                    "wrong_tool"
                    if not full
                    and any(c["name"] != rec["gold_calls"][0]["name"] for c in valid)
                    else (
                        "wrong_argument"
                        if not all(ok)
                        else (
                            "no_answer"
                            if not final
                            else (
                                "incomplete_chain"
                                if not complete
                                else (
                                    "hallucinated_item"
                                    if full and r["unseen_ids"]
                                    else (
                                        "constraint_violated"
                                        if full
                                        else "ignored_result"
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
    )
    return r


def summarize(rows):
    pct = lambda xs: round(100 * sum(xs) / len(xs), 1) if xs else None
    tool = [r for r in rows if r["kind"] != "no_tool"]
    return {
        "n": len(rows),
        "call_validity": pct([r["valid"] for r in tool]),
        "call_accuracy": pct([r["call_correct"] for r in tool]),
        "abstention": pct([r["abstained"] for r in rows if r["kind"] == "no_tool"]),
        "task_success": pct([r["success"] for r in rows]),
        "task_success_by_kind": {
            k: pct([r["success"] for r in rows if r["kind"] == k]) for k in KINDS
        },
        "avg_steps": round(sum(r["n_steps"] for r in rows) / len(rows), 2),
        "sec_per_request": round(sum(r["seconds"] for r in rows) / len(rows), 2),
        "failures": dict(
            Counter(r["failure"] for r in rows if r["failure"]).most_common()
        ),
        "outfit_check_failures": dict(
            Counter(f for r in rows for f in r.get("outfit_failed", [])).most_common()
        ),
    }


def run(tag, limit=None):
    from .agent import run_agent
    from .utils import load_model

    model, tok = load_model(tag)
    out_dir = OUT_DIR / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(out_dir / "predictions.jsonl", "w") as f:
        for i, rec in enumerate(read_jsonl(DATA_DIR / "test.jsonl")[:limit], 1):
            t0 = time.time()
            out = run_agent(model, tok, [{"role": "user", "content": rec["user"]}])
            rows.append({**score(rec, out), "seconds": round(time.time() - t0, 2)})
            f.write(
                json.dumps(
                    {
                        **rows[-1],
                        "user": rec["user"],
                        "final": out["final"],
                        "steps": out["steps"],
                    }
                )
                + "\n"
            )
            f.flush()
            if i % 10 == 0:
                print(f"{i} done, success {sum(r['success'] for r in rows) / i:.0%}")
    metrics = summarize(rows)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


def compare(base="zeroshot", n_examples=10):
    runs = {
        p.parent.name: read_jsonl(p)
        for p in sorted(OUT_DIR.glob("*/predictions.jsonl"))
    }
    assert base in runs, f"run --tag {base} first"
    order = [base, *(t for t in runs if t != base)]
    m = {t: json.loads((OUT_DIR / t / "metrics.json").read_text()) for t in order}
    row = lambda cells: "| " + " | ".join(map(str, cells)) + " |"

    cols = ["call_validity", "call_accuracy", "abstention", "task_success"]
    lines = [
        "# Baseline vs LoRA",
        "",
        row(["run", *cols, *(f"success {k}" for k in KINDS), "avg steps"]),
        row(["---"] * (len(cols) + len(KINDS) + 2)),
    ]
    lines += [
        row(
            [
                t,
                *(m[t][c] for c in cols),
                *(m[t]["task_success_by_kind"][k] for k in KINDS),
                m[t]["avg_steps"],
            ]
        )
        for t in order
    ]

    lines += [
        "",
        "## Failure categories",
        "",
        row(["category", *order]),
        row(["---"] * (len(order) + 1)),
    ]
    lines += [
        row([l, *(m[t]["failures"].get(l, 0) for t in order)])
        for l in sorted({l for t in order for l in m[t]["failures"]})
    ]
    lines += [
        "",
        "## Failed outfit checks",
        "",
        *(f"- {t}: {m[t]['outfit_check_failures'] or 'none'}" for t in order),
    ]

    base_ok = {r["id"]: r["success"] for r in runs[base]}
    lines += [
        "",
        f"## Change vs {base}",
        "",
        row(["run", "fixed", "still failing", "introduced", "introduced as"]),
        row(["---"] * 5),
    ]
    for t in order[1:]:
        c = Counter((base_ok[r["id"]], r["success"]) for r in runs[t])
        new = dict(
            Counter(
                r["failure"] for r in runs[t] if base_ok[r["id"]] and not r["success"]
            )
        )
        lines.append(
            row([t, c[(False, True)], c[(False, False)], c[(True, False)], new or "-"])
        )

    for t in order:
        lines += ["", f"## Sample failures: {t}", ""]
        lines += [
            f"- `{r['id']}` {r['failure']} {r.get('outfit_failed') or ''}: {r['user']}  \n"
            f"  -> {(r['final'] or r['steps'][-1]['raw'])[:200]!r}"
            for r in [r for r in runs[t] if not r["success"]][:n_examples]
        ]

    (OUT_DIR / "comparison.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    if not (args.compare or args.tag):
        ap.error("give --tag or --compare")
    compare() if args.compare else run(args.tag, args.limit)
