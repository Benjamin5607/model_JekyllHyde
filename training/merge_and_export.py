"""Merge LoRA adapter and export for Ollama."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge LoRA and register Ollama model")
    parser.add_argument("--base", default="gemma2-2b")
    parser.add_argument("--adapter", type=Path, help="LoRA adapter dir")
    parser.add_argument("--ollama", action="store_true", help="Create Ollama model after merge")
    args = parser.parse_args()

    with CONFIG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    adapter_dir = args.adapter or Path(cfg["training"]["output_dir"])
    merged_dir = Path(cfg["training"]["merged_dir"])
    base_id = cfg["base_models"][args.base]["huggingface"]

    if not adapter_dir.exists():
        raise SystemExit(f"Adapter not found: {adapter_dir}. Run train_lora.py first.")

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit("pip install -e '.[train]'") from exc

    print(f"Loading base {base_id}")
    base = AutoModelForCausalLM.from_pretrained(base_id, trust_remote_code=True, torch_dtype=torch.float16, device_map="cpu")
    tokenizer = AutoTokenizer.from_pretrained(base_id, trust_remote_code=True)
    model = PeftModel.from_pretrained(base, str(adapter_dir))
    merged = model.merge_and_unload()

    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(merged_dir)
    tokenizer.save_pretrained(merged_dir)

    manifest = {
        "name": "jekyll-hyde",
        "display_name": "Jekyll & Hyde",
        "fine_tuned": True,
        "method": "lora-merge",
        "base_key": args.base,
        "base_huggingface": base_id,
        "params_b": cfg["base_models"][args.base]["params_b"],
        "merged_at": datetime.now(UTC).isoformat(),
        "identity": (
            "Independent Gemma-derived model. LoRA weights merged into base weights. "
            "Not a prompt wrapper — this is the custom Jekyll & Hyde model."
        ),
        "specialization": [
            "equity_market_analysis",
            "guideline_policy_audit",
            "gray_zone_classification",
            "policy_weakness_hardening",
        ],
    }
    manifest_path = merged_dir / "jekyll_hyde_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Merged model -> {merged_dir}")
    print(f"Manifest -> {manifest_path}")

    if args.ollama:
        modelfile = ROOT / "models" / "Modelfile.merged"
        content = modelfile.read_text(encoding="utf-8")
        content = content.replace("{{MERGED}}", str(merged_dir.resolve()).replace("\\", "/"))
        generated = ROOT / "models" / "Modelfile.merged.generated"
        generated.write_text(content, encoding="utf-8")
        name = cfg["ollama"]["model_name"]
        result = subprocess.run(
            ["ollama", "create", name, "-f", str(generated)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or f"ollama create failed ({result.returncode})")
        print(f"Ollama model created: {name}")


if __name__ == "__main__":
    main()
