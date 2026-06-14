#!/usr/bin/env python3
"""Create the jekyll-hyde Ollama model from Gemma base."""

from __future__ import annotations

import argparse
import sys

from safety_eval.platform.model_registry import list_bases
from safety_eval.platform.ollama_client import (
    FINETUNED_NAME,
    MODEL_NAME,
    create_jekyll_hyde_model,
    ensure_model,
    ollama_available,
    pull_base,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Jekyll & Hyde LLM (Gemma-based)")
    parser.add_argument("--base", default="gemma2-2b", help="Base key from training/config.yaml")
    parser.add_argument("--name", default=MODEL_NAME, help=f"Model name (default: {MODEL_NAME})")
    parser.add_argument("--list-bases", action="store_true", help="List available Gemma bases")
    parser.add_argument("--pull-only", action="store_true")
    args = parser.parse_args()

    if args.list_bases:
        for b in list_bases():
            print(f"  {b['key']:12} ollama={b['ollama']:16} params={b['params_b']}B vram~{b['vram_gb']}GB")
        return

    if not ollama_available():
        print("Ollama is not running. Install from https://ollama.com", file=sys.stderr)
        raise SystemExit(1)

    print(f"Pulling base: {args.base}")
    pull_base(args.base)

    if args.pull_only:
        print("Done.")
        return

    print(f"Creating model: {args.name}")
    msg = create_jekyll_hyde_model(base_key=args.base, model_name=args.name)
    print(msg)
    info = ensure_model(base_key=args.base, model_name=args.name, prefer_finetuned=False)
    print(f"Ready: {info.name} (base={info.base})")
    print(f"LoRA fine-tuned model name will be: {FINETUNED_NAME}")


if __name__ == "__main__":
    main()
