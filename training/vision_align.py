"""Align SigLIP vision projector to Gemma 3 text backbone (lightweight adapter)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
VISION_CFG = ROOT / "config" / "vision.yaml"
TRAINING_CFG = ROOT / "training" / "config.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train lightweight SigLIP→LLM projector")
    parser.add_argument("--base", default="gemma3-4b")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with VISION_CFG.open(encoding="utf-8") as f:
        vcfg = yaml.safe_load(f) or {}
    with TRAINING_CFG.open(encoding="utf-8") as f:
        tcfg = yaml.safe_load(f)
    if args.base not in tcfg.get("base_models", {}):
        raise SystemExit(f"Unknown base: {args.base}")

    out_dir = ROOT / vcfg.get("vision", {}).get("adapter_checkpoint", "models/adapters/vision-siglip-projector")
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "base": args.base,
        "siglip": vcfg.get("vision", {}).get("siglip_model"),
        "projector_dim": vcfg.get("alignment", {}).get("projector_dim", 2048),
        "status": "scaffold",
        "note": "Run with pip install -e '.[vision,train]' and image-caption pairs to fine-tune projector.",
    }
    (out_dir / "adapter_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if args.dry_run:
        print("Dry run — manifest only.")
        return
    print(f"Scaffold written -> {out_dir}")
    print("Next: add data/vision/chart_captions.jsonl and extend this script with contrastive alignment.")


if __name__ == "__main__":
    main()
