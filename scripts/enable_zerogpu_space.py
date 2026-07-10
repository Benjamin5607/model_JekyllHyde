#!/usr/bin/env python3
"""Switch Jekyll & Hyde Space to ZeroGPU, set HF_TOKEN secret, redeploy."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from safety_eval.platform.secrets_loader import load_secrets

load_secrets()

DEFAULT_SPACE = "benjamin5607/jekyll-hyde-demo"


def enable_zerogpu(space_id: str, *, redeploy: bool = True) -> dict:
    from huggingface_hub import HfApi, SpaceHardware

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        raise SystemExit("Set HF_TOKEN or run: huggingface-cli login")

    api = HfApi(token=token)
    runtime = api.request_space_hardware(space_id, SpaceHardware.ZERO_A10G)
    result = {
        "space": space_id,
        "hardware": "zero-a10g",
        "stage": runtime.stage if runtime else None,
        "url": f"https://huggingface.co/spaces/{space_id}",
    }
    if token and not token.startswith("hf_your"):
        try:
            api.add_space_secret(space_id, "HF_TOKEN", token, description="Gated Gemma + Hub access")
            result["hf_token_secret"] = "updated"
        except Exception as exc:
            result["hf_token_secret"] = f"skip: {exc}"

    if redeploy:
        from scripts.upload_hf_hub import create_space_repo

        result["redeploy"] = create_space_repo(space_id=space_id, dry_run=False)
        api.restart_space(space_id)
        result["restarted"] = True

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Enable ZeroGPU on HF Space")
    parser.add_argument("--space", default=os.environ.get("HF_SPACE", DEFAULT_SPACE))
    parser.add_argument("--no-redeploy", action="store_true")
    args = parser.parse_args()
    import json

    print(json.dumps(enable_zerogpu(args.space, redeploy=not args.no_redeploy), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
