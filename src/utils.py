import json
from functools import cache
from pathlib import Path

import yaml

from .constants import ROOT, SYSTEM_PROMPT

CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
DATA_DIR = ROOT / CFG["paths"]["data_dir"]
OUT_DIR = ROOT / CFG["paths"]["out_dir"]


@cache
def db():
    return json.loads((ROOT / CFG["paths"]["db"]).read_text())


def system_prompt():
    return SYSTEM_PROMPT.format(today=db()["today"])


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r) + "\n" for r in rows))


def load_base():
    """Base model and tokenizer; works on transformers 4.x (torch_dtype) and 5.x (dtype)."""
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

    name, dtype = CFG["model"]["name"], getattr(torch, CFG["model"]["dtype"])
    key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
    return AutoModelForCausalLM.from_pretrained(name, **{key: dtype}), AutoTokenizer.from_pretrained(name)


def load_model(tag=None):
    """Base model, with outputs/<tag>/adapter merged in if it exists."""
    import torch

    model, tok = load_base()
    adapter = OUT_DIR / tag / "adapter" if tag else None
    if adapter and adapter.exists():
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(adapter)).merge_and_unload()
    print(f"loaded {CFG['model']['name']} + {adapter if adapter and adapter.exists() else 'no adapter'}")
    return model.to("cuda" if torch.cuda.is_available() else "cpu").eval(), tok
