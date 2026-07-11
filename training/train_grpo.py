"""GRPO training loop — RLAIF gate as reward, no separate critic model.

Two paths:
  1. TRL GRPOTrainer (if trl>=0.14 available): online group sampling with an
     RLAIF reward function on the fine-tuned base.
  2. Fallback: advantage-weighted SFT over group samples exported by
     safety_eval.learning.grpo (works without the TRL GRPO trainer).
"""

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


def load_grpo_cfg() -> dict:
    lc = ROOT / "config" / "learning.yaml"
    if not lc.exists():
        return {}
    with lc.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("grpo", {})


def _rlaif_reward_fn():
    """Return a TRL-compatible reward function scoring completions via the RLAIF gate."""
    from safety_eval.learning.rlaif_gate import RlaifGate

    gate = RlaifGate()

    def reward(prompts, completions, **_kwargs):
        scores = []
        for p, c in zip(prompts, completions):
            text = c if isinstance(c, str) else (c[0]["content"] if c else "")
            record = {
                "messages": [
                    {"role": "user", "content": p},
                    {"role": "assistant", "content": text},
                ],
                "meta": {"quality_score": 0.6, "source": "grpo"},
            }
            scores.append(float(gate.score_record(record, topic=p).score) / 100.0)
        return scores

    return reward


def _fallback_weighted_sft(base: str, *, dry_run: bool) -> None:
    """Advantage-weighted SFT over exported GRPO samples."""
    from safety_eval.learning.grpo import run_grpo_sampling

    print("TRL GRPOTrainer unavailable — using advantage-weighted SFT fallback.")
    info = run_grpo_sampling()
    print(json.dumps({k: v for k, v in info.items() if k != "groups_detail"}, indent=2))
    if dry_run:
        print("Dry run — sampling + reward only, no weight update.")
        return
    if info["positive_samples"] == 0:
        print("No positive-advantage samples; skipping update.")
        return
    print(
        "Weighted dataset ready at "
        f"{info['dataset_path']} — feed into train_lora.py for a weighted SFT pass."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="GRPO loop (RLAIF reward, critic-free)")
    parser.add_argument("--base", default="gemma3-4b")
    parser.add_argument("--persona", choices=("jekyll", "hyde", "both"), default="both")
    parser.add_argument("--group-size", type=int, default=None)
    parser.add_argument("--num-prompts", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--4bit", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    if args.base not in cfg["base_models"]:
        raise SystemExit(f"Unknown base: {args.base}")
    grpo_cfg = load_grpo_cfg()
    group_size = args.group_size or int(grpo_cfg.get("group_size", 4))
    num_prompts = args.num_prompts or int(grpo_cfg.get("num_prompts", 8))

    # Path 1: TRL GRPOTrainer (online)
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from trl import GRPOConfig, GRPOTrainer
    except ImportError:
        _fallback_weighted_sft(args.base, dry_run=args.dry_run)
        return

    from safety_eval.learning.grpo import load_gray_prompts

    prompts = load_gray_prompts(limit=num_prompts)
    if not prompts:
        print("No gray-zone prompts available.")
        return
    if args.dry_run:
        print(f"Dry run: {len(prompts)} prompts, group_size={group_size}, base={args.base}")
        return

    model_id = cfg["base_models"][args.base]["huggingface"]
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

    personas = ("jekyll", "hyde") if args.persona == "both" else (args.persona,)
    dataset = Dataset.from_list([{"prompt": p} for p in prompts])
    reward_fn = _rlaif_reward_fn()

    for persona in personas:
        adapter_dir = Path(cfg["adapters"][persona])
        if not (adapter_dir / "adapter_config.json").exists():
            print(f"Skip {persona}: adapter missing")
            continue
        print(f"\n=== GRPO persona={persona} group_size={group_size} prompts={len(prompts)} ===")

        peft_model = PeftModel.from_pretrained(
            model, str(adapter_dir), adapter_name=persona, is_trainable=True
        )
        peft_config = LoraConfig(
            r=lora_cfg["r"],
            lora_alpha=lora_cfg["lora_alpha"],
            lora_dropout=lora_cfg["lora_dropout"],
            target_modules=lora_cfg["target_modules"],
            bias="none",
            task_type="CAUSAL_LM",
        )
        grpo_args = GRPOConfig(
            output_dir=str(adapter_dir / "grpo_checkpoints"),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
            learning_rate=train_cfg["learning_rate"] * 0.3,
            num_generations=group_size,
            max_prompt_length=min(512, train_cfg["max_seq_length"] // 2),
            max_completion_length=int(grpo_cfg.get("max_new_tokens", 320)),
            num_train_epochs=int(grpo_cfg.get("epochs", 1)),
            logging_steps=train_cfg["logging_steps"],
            fp16=True,
            report_to="none",
            beta=float(grpo_cfg.get("kl_beta", 0.04)),
        )
        trainer = GRPOTrainer(
            model=peft_model,
            reward_funcs=reward_fn,
            args=grpo_args,
            train_dataset=dataset,
            peft_config=peft_config,
            processing_class=tokenizer,
        )
        trainer.train()
        peft_model.save_pretrained(adapter_dir)
        tokenizer.save_pretrained(adapter_dir)
        print(f"GRPO-updated adapter saved -> {adapter_dir}")


if __name__ == "__main__":
    main()
