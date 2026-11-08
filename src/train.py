"""LoRA fine-tuning with loss on assistant turns only.  python -m src.train --rank 16|4"""

import argparse
import json
import math

import torch
from peft import LoraConfig, get_peft_model
from transformers import Trainer, TrainingArguments, set_seed
from transformers.trainer_utils import get_last_checkpoint

from .constants import ASSISTANT_RE, TOOL_SCHEMAS
from .utils import CFG, DATA_DIR, OUT_DIR, load_base, read_jsonl, system_prompt


def encode(rec, tok, max_len):
    text = tok.apply_chat_template([{"role": "system", "content": system_prompt()}, *rec["messages"]],
                                   tools=TOOL_SCHEMAS, tokenize=False)
    enc = tok(text, return_offsets_mapping=True, add_special_tokens=False)
    if len(enc["input_ids"]) > max_len:
        return None
    keep = [m.get("train", True) for m in rec["messages"] if m["role"] == "assistant"]
    spans = [m.span(1) for m, k in zip(ASSISTANT_RE.finditer(text), keep) if k]
    labels = [t if any(a <= s < b for a, b in spans) else -100
              for t, (s, _) in zip(enc["input_ids"], enc["offset_mapping"])]
    return {"input_ids": enc["input_ids"], "labels": labels}


def collate(batch, pad_id):
    n = max(len(b["input_ids"]) for b in batch)
    pad = lambda xs, v: xs + [v] * (n - len(xs))
    return {"input_ids": torch.tensor([pad(b["input_ids"], pad_id) for b in batch]),
            "attention_mask": torch.tensor([pad([1] * len(b["input_ids"]), 0) for b in batch]),
            "labels": torch.tensor([pad(b["labels"], -100) for b in batch])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", type=int, default=CFG["lora"]["rank"])
    rank = ap.parse_args().rank
    set_seed(CFG["seed"])
    t, run_dir = CFG["train"], OUT_DIR / f"lora_r{rank}"

    model, tok = load_base()
    data = {}
    for split in ("train", "val"):
        recs = read_jsonl(DATA_DIR / f"{split}.jsonl")
        data[split] = [e for r in recs if (e := encode(r, tok, t["max_len"]))]
        print(f"{split}: {len(data[split])}/{len(recs)} within {t['max_len']} tokens")

    steps = math.ceil(len(data["train"]) / (t["batch_size"] * t["grad_accum"])) * t["epochs"]
    model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=CFG["lora"]["dropout"],
                                             target_modules=CFG["lora"]["target_modules"], task_type="CAUSAL_LM"))
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model, train_dataset=data["train"], eval_dataset=data["val"],
        data_collator=lambda b: collate(b, tok.pad_token_id),
        args=TrainingArguments(
            output_dir=str(run_dir / "checkpoints"), seed=CFG["seed"], report_to="none",
            num_train_epochs=t["epochs"], learning_rate=t["lr"], lr_scheduler_type="cosine",
            warmup_steps=int(t["warmup_ratio"] * steps), per_device_train_batch_size=t["batch_size"],
            per_device_eval_batch_size=t["batch_size"], gradient_accumulation_steps=t["grad_accum"],
            fp16=CFG["model"]["dtype"] == "float16", eval_strategy="epoch", save_strategy="steps",
            save_steps=50, save_total_limit=1, logging_steps=10, remove_unused_columns=False,
            label_names=["labels"], gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False}, prediction_loss_only=True))

    # resume after a disconnect: pick up the latest checkpoint in run_dir/checkpoints if one exists
    ckpt_dir = run_dir / "checkpoints"
    last = get_last_checkpoint(str(ckpt_dir)) if ckpt_dir.is_dir() else None
    if last:
        print(f"resuming from {last}")
    trainer.train(resume_from_checkpoint=last)

    model.save_pretrained(run_dir / "adapter")
    (run_dir / "train_log.json").write_text(json.dumps(trainer.state.log_history, indent=2))
    print(f"saved {run_dir / 'adapter'}")


if __name__ == "__main__":
    main()
