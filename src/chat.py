"""Interactive demo.  python -m src.chat [--tag lora_r16|lora_r4|zeroshot]   (/reset, /quit)"""

import argparse
import json

from .agent import run_agent
from .utils import load_model


def show(step):
    for call, result in zip(step["calls"], step["results"]):
        print(
            f"  -> {call['name']}({json.dumps(call['arguments'])})\n  <- {json.dumps(result)}"
        )
    for call in step["calls"]:
        if "invalid" in call:
            print(f"  !! unparseable tool call: {call['invalid'][:200]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="lora_r16")
    model, tok = load_model(ap.parse_args().tag)
    history = []
    while (text := input("\nyou> ").strip()) != "/quit":
        if text == "/reset":
            history = []
        elif text:
            out = run_agent(
                model, tok, [*history, {"role": "user", "content": text}], on_step=show
            )
            if out["stopped"] == "answer":
                history = out["messages"]
            print(f"\nstylist> {out['final'] or '(stopped: ' + out['stopped'] + ')'}")


if __name__ == "__main__":
    main()
