"""Agent loop: generate -> parse <tool_call> -> run tool -> feed result back -> repeat."""

import json
import re

import torch

from .constants import TOOL_CALL_RE, TOOL_SCHEMAS
from .tools import TOOLS, call_tool
from .utils import CFG, system_prompt


def _parse(block):
    try:
        obj = json.loads(block)
        args = obj.get("arguments", {})
        args = json.loads(args) if isinstance(args, str) else args
        if obj["name"] in TOOLS and isinstance(args, dict):
            return {"name": obj["name"], "arguments": args}
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    return {"invalid": block.strip()}


def parse_tool_calls(text):
    """[] for a plain answer, else {'name', 'arguments'} or {'invalid': raw} per call."""
    if blocks := TOOL_CALL_RE.findall(text):
        return [_parse(b) for b in blocks]
    return [{"invalid": text}] if "<tool_call>" in text or re.search(r'"name"\s*:', text) else []


@torch.no_grad()
def generate(model, tok, messages):
    enc = tok.apply_chat_template(messages, tools=TOOL_SCHEMAS, add_generation_prompt=True,
                                  return_dict=True, return_tensors="pt").to(model.device)
    out = model.generate(**enc, max_new_tokens=CFG["model"]["max_new_tokens"], do_sample=False,
                         temperature=None, top_p=None, top_k=None, pad_token_id=tok.eos_token_id)
    return tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def run_agent(model, tok, history, on_step=lambda step: None):
    """One user turn. Returns {'messages', 'steps', 'final', 'stopped': answer|invalid_call|max_steps}."""
    messages = [{"role": "system", "content": system_prompt()}, *history]
    steps = []
    for _ in range(CFG["model"]["max_agent_steps"]):
        raw = generate(model, tok, messages)
        calls = parse_tool_calls(raw)
        step = {"raw": raw, "calls": calls, "results": []}
        steps.append(step)
        if not calls or any("invalid" in c for c in calls):
            messages.append({"role": "assistant", "content": raw})
            on_step(step)
            return {"messages": messages[1:], "steps": steps, "final": None if calls else raw,
                    "stopped": "invalid_call" if calls else "answer"}
        messages.append({"role": "assistant", "content": "",
                         "tool_calls": [{"type": "function", "function": c} for c in calls]})
        step["results"] = [call_tool(c["name"], c["arguments"]) for c in calls]
        messages += [{"role": "tool", "content": json.dumps(r)} for r in step["results"]]
        on_step(step)
    return {"messages": messages[1:], "steps": steps, "final": None, "stopped": "max_steps"}
