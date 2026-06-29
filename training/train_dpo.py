"""DPO / preference alignment from curated vs rejected pairs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="DPO align Jekyll & Hyde LoRA from preference pairs")
    parser.add_argument("--base", default="gemma2-2b")
    parser.add_argument("--persona", choices=("jekyll", "hyde", "both"), default="both")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--4bit", action="store_true")
    parser.add_argument("--beta", type=float, default=None)
    args = parser.parse_args()

    from safety_eval.learning.dpo_pairs import export_dpo_dataset, pair_count

    export_info = export_dpo_dataset()
    pairs = pair_count()
    print(f"DPO pairs: {pairs} -> {export_info['path']}")
    if pairs < export_info["min_pairs"]:
        raise SystemExit(f"Need at least {export_info['min_pairs']} pairs (have {pairs})")

    if args.dry_run:
        print("Dry run OK.")
        return

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, PeftModel, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from trl import DPOConfig, DPOTrainer
    except ImportError as exc:
        raise SystemExit("Install: pip install -e '.[train]' (requires trl)") from exc

    cfg = load_config()
    if args.base not in cfg["base_models"]:
        raise SystemExit(f"Unknown base: {args.base}")

    dpo_path = Path(export_info["path"])
    rows = []
    with dpo_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    from training.bootstrap_adapters import bootstrap_dual_adapters

    bootstrap_dual_adapters()

    learning_cfg_path = ROOT / "config" / "learning.yaml"
    dpo_cfg: dict = {}
    if learning_cfg_path.exists():
        with learning_cfg_path.open(encoding="utf-8") as f:
            dpo_cfg = (yaml.safe_load(f) or {}).get("dpo", {})

    beta = args.beta if args.beta is not None else float(dpo_cfg.get("beta", 0.1))
    base_cfg = cfg["base_models"][args.base]
    model_id = base_cfg["huggingface"]
    lora_cfg = cfg["lora"]
    train_cfg = cfg["training"]

    personas = ("jekyll", "hyde") if args.persona == "both" else (args.persona,)
    for persona in personas:
        adapter_dir = Path(cfg["adapters"][persona])
        if not (adapter_dir / "adapter_config.json").exists():
            print(f"Skip {persona}: adapter missing")
            continue

        print(f"\n=== DPO persona={persona} ({len(rows)} pairs) beta={beta} ===")

        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        quant = None
        if args.__dict__.get("4bit"):
            quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)

        base = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            device_map="auto",
            torch_dtype=torch.float16,
            quantization_config=quant,
        )
        ref = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            device_map="auto",
            torch_dtype=torch.float16,
            quantization_config=quant,
        )

        model = PeftModel.from_pretrained(base, str(adapter_dir), adapter_name=persona, is_trainable=True)
        ref_model = PeftModel.from_pretrained(ref, str(adapter_dir), adapter_name=persona)
        ref_model.eval()
        for p in ref_model.parameters():
            p.requires_grad = False

        if not isinstance(model, PeftModel):
            peft_config = LoraConfig(
                r=lora_cfg["r"],
                lora_alpha=lora_cfg["lora_alpha"],
                lora_dropout=lora_cfg["lora_dropout"],
                target_modules=lora_cfg["target_modules"],
                bias="none",
                task_type="CAUSAL_LM",
            )
            model = get_peft_model(model, peft_config)

        dataset = Dataset.from_list(rows)

        dpo_args = DPOConfig(
            output_dir=str(adapter_dir / "dpo_checkpoints"),
            per_device_train_batch_size=max(1, train_cfg["batch_size"] // 2),
            gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
            learning_rate=train_cfg["learning_rate"] * 0.5,
            num_train_epochs=int(dpo_cfg.get("epochs", 1)),
            beta=beta,
            max_length=train_cfg["max_seq_length"],
            max_prompt_length=min(512, train_cfg["max_seq_length"] // 2),
            logging_steps=train_cfg["logging_steps"],
            fp16=True,
            report_to="none",
            remove_unused_columns=False,
        )

        trainer = DPOTrainer(
            model=model,
            ref_model=ref_model,
            args=dpo_args,
            train_dataset=dataset,
            processing_class=tokenizer,
        )
        trainer.train()
        model.save_pretrained(adapter_dir)
        tokenizer.save_pretrained(adapter_dir)
        print(f"DPO-aligned adapter saved -> {adapter_dir}")


if __name__ == "__main__":
    main()
