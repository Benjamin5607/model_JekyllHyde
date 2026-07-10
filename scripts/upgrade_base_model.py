#!/usr/bin/env python3
"""Upgrade Jekyll & Hyde base model while preserving dual LoRA + MoE serving."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TRAINING_CFG = ROOT / "training" / "config.yaml"
LEARNING_CFG = ROOT / "config" / "learning.yaml"
INFERENCE_CFG = ROOT / "config" / "inference.yaml"


def load_training_cfg() -> dict:
    with TRAINING_CFG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_bases() -> list[str]:
    return list(load_training_cfg().get("base_models", {}).keys())


def validate_base(key: str) -> dict:
    cfg = load_training_cfg()
    if key not in cfg.get("base_models", {}):
        raise SystemExit(f"Unknown base '{key}'. Available: {list_bases()}")
    return cfg["base_models"][key]


def update_default_base(key: str, *, dry_run: bool = False) -> None:
    with TRAINING_CFG.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["default_base"] = key
    if not dry_run:
        TRAINING_CFG.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True), encoding="utf-8")

    if LEARNING_CFG.exists():
        with LEARNING_CFG.open(encoding="utf-8") as f:
            lcfg = yaml.safe_load(f) or {}
        lcfg.setdefault("auto", {})["train_base"] = key
        lcfg.setdefault("iterative_dpo", {})["train_base"] = key
        if not dry_run:
            LEARNING_CFG.write_text(yaml.dump(lcfg, default_flow_style=False, allow_unicode=True), encoding="utf-8")


def pull_ollama(ollama_tag: str, *, dry_run: bool = False) -> None:
    if dry_run:
        print(f"[dry-run] ollama pull {ollama_tag}")
        return
    subprocess.run(["ollama", "pull", ollama_tag], check=False)


def recreate_ollama_personas(base_key: str, *, dry_run: bool = False) -> None:
    py = ROOT / ".venv-train" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)
    cmd = [str(py), str(ROOT / "scripts" / "setup_triple_deploy.py"), "--merge", "--ollama", "--base", base_key]
    if dry_run:
        print("[dry-run]", " ".join(cmd))
        return
    subprocess.run(cmd, cwd=str(ROOT), check=False)


def print_context_notes(key: str) -> None:
    notes = {
        "gemma2-2b": "8K context (legacy default)",
        "gemma3-4b": "128K context window — recommended 2026 lightweight SOTA",
        "gemma3-8b": "128K context — higher VRAM, stronger quant/policy reasoning",
        "gemma3-12b": "128K context — workstation / 24GB+ VRAM",
    }
    print(f"Context: {notes.get(key, 'see model card')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade base model (dual LoRA + MoE preserved)")
    parser.add_argument("--base", default="gemma3-4b", help="Base key from training/config.yaml")
    parser.add_argument("--list", action="store_true", help="List available base models")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-ollama", action="store_true")
    parser.add_argument("--skip-train", action="store_true", help="Only update configs + pull Ollama")
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_bases(), indent=2))
        return 0

    spec = validate_base(args.base)
    print(f"=== Upgrade base -> {args.base} ===")
    print(f"  HuggingFace: {spec['huggingface']}")
    print(f"  Ollama:      {spec['ollama']}")
    print(f"  VRAM est:    {spec.get('vram_gb', '?')} GB")
    print_context_notes(args.base)

    update_default_base(args.base, dry_run=args.dry_run)
    print("Updated default_base in training/config.yaml + learning auto.train_base")

    if not args.skip_ollama:
        pull_ollama(spec["ollama"], dry_run=args.dry_run)
        recreate_ollama_personas(args.base, dry_run=args.dry_run)

    if not args.skip_train:
        py = ROOT / ".venv-train" / "Scripts" / "python.exe"
        if not py.exists():
            py = Path(sys.executable)
        train_cmd = [
            str(py), str(ROOT / "training" / "train_lora.py"),
            "--base", args.base, "--4bit", "--persona", "both", "--epochs", "3",
        ]
        if args.dry_run:
            print("[dry-run]", " ".join(train_cmd))
        else:
            print("Training dual LoRA adapters (jekyll + hyde)...")
            subprocess.run(train_cmd, cwd=str(ROOT))
            subprocess.run([str(py), str(ROOT / "training" / "merge_and_export.py"), "--base", args.base], cwd=str(ROOT))

    print("\nDone. Restart platform: scripts\\restart_api.ps1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
