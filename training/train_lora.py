"""LoRA fine-tune Jekyll & Hyde on Gemma base models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def normalize_messages(messages: list[dict]) -> list[dict]:
    """Gemma 2 chat templates reject system role; fold into first user turn."""
    system_parts: list[str] = []
    out: list[dict] = []
    for msg in messages:
        if msg["role"] == "system":
            system_parts.append(msg["content"])
        else:
            out.append(dict(msg))
    if system_parts:
        prefix = "\n\n".join(system_parts)
        for i, msg in enumerate(out):
            if msg["role"] == "user":
                out[i] = {"role": "user", "content": f"{prefix}\n\n{msg['content']}"}
                break
    return out


def format_sample(record: dict, tokenizer) -> dict:
    messages = normalize_messages(record["messages"])
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": text}


def main() -> None:
    parser = argparse.ArgumentParser(description="LoRA train Jekyll & Hyde")
    parser.add_argument("--base", default="gemma2-2b", help="Key from training/config.yaml base_models")
    parser.add_argument("--dataset", type=Path, default=ROOT / "training" / "datasets" / "jekyll_hyde_train.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Validate dataset/config only")
    parser.add_argument("--4bit", action="store_true", help="Use 4-bit quantization (needs GPU)")
    parser.add_argument("--epochs", type=int, default=None, help="Override num_epochs from config")
    args = parser.parse_args()

    cfg = load_config()
    if args.base not in cfg["base_models"]:
        raise SystemExit(f"Unknown base: {args.base}. Options: {list(cfg['base_models'])}")

    if not args.dataset.exists():
        raise SystemExit(f"Dataset missing. Run: python training/prepare_dataset.py")

    records = load_jsonl(args.dataset)
    print(f"Dataset: {len(records)} samples")
    print(f"Base: {args.base} -> {cfg['base_models'][args.base]['huggingface']}")
    print(f"VRAM estimate: {cfg['base_models'][args.base]['vram_gb']} GB")

    if args.dry_run:
        print("Dry run OK.")
        return

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer, BitsAndBytesConfig
    except ImportError as exc:
        raise SystemExit("Install training deps: pip install -e '.[train]'") from exc

    base_cfg = cfg["base_models"][args.base]
    model_id = base_cfg["huggingface"]
    lora_cfg = cfg["lora"]
    train_cfg = cfg["training"]

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant = None
    if args.__dict__.get("4bit"):
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        trust_remote_code=True,
        device_map="auto",
        torch_dtype=torch.float16,
        quantization_config=quant,
    )

    peft_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg["lora_dropout"],
        target_modules=lora_cfg["target_modules"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    dataset = Dataset.from_list([format_sample(r, tokenizer) for r in records])

    out_dir = Path(train_cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    num_epochs = args.epochs if args.epochs is not None else train_cfg["num_epochs"]

    training_args = TrainingArguments(
        output_dir=str(out_dir),
        per_device_train_batch_size=train_cfg["batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=train_cfg["learning_rate"],
        num_train_epochs=num_epochs,
        warmup_ratio=train_cfg["warmup_ratio"],
        logging_steps=train_cfg["logging_steps"],
        save_steps=train_cfg["save_steps"],
        fp16=True,
        report_to="none",
        remove_unused_columns=False,
    )

    def tokenize(batch):
        out = tokenizer(
            batch["text"],
            truncation=True,
            max_length=train_cfg["max_seq_length"],
            padding="max_length",
        )
        pad_id = tokenizer.pad_token_id
        out["labels"] = [
            [(-100 if tok == pad_id else tok) for tok in ids]
            for ids in out["input_ids"]
        ]
        return out

    tokenized = dataset.map(tokenize, batched=True)

    trainer = Trainer(model=model, args=training_args, train_dataset=tokenized)
    trainer.train()
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print(f"LoRA adapter saved -> {out_dir}")
    print("Next: python training/merge_and_export.py")


if __name__ == "__main__":
    main()
