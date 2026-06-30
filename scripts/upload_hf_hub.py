#!/usr/bin/env python3
"""Upload Jekyll & Hyde LoRA adapters to Hugging Face Hub."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ADAPTER_FILES = (
    "adapter_config.json",
    "adapter_model.safetensors",
)

DEFAULT_USER = "benjamin5607"


def _token() -> str | None:
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


def upload_adapter(
    *,
    local_dir: Path,
    repo_id: str,
    readme_src: Path,
    dry_run: bool = False,
    private: bool = False,
) -> dict:
    missing = [f for f in ADAPTER_FILES if not (local_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"{local_dir}: missing {missing}")

    if dry_run:
        size_mb = sum((local_dir / f).stat().st_size for f in ADAPTER_FILES) / (1024 * 1024)
        return {"repo_id": repo_id, "dry_run": True, "size_mb": round(size_mb, 1)}

    from huggingface_hub import HfApi, create_repo

    token = _token()
    if not token:
        raise SystemExit(
            "Set HF_TOKEN or run: huggingface-cli login\n"
            "Create token: https://huggingface.co/settings/tokens"
        )

    api = HfApi(token=token)
    create_repo(repo_id, repo_type="model", private=private, exist_ok=True)

    api.upload_folder(
        folder_path=str(local_dir),
        repo_id=repo_id,
        repo_type="model",
        allow_patterns=list(ADAPTER_FILES),
        commit_message="Upload Jekyll & Hyde LoRA adapter",
    )
    if readme_src.exists():
        api.upload_file(
            path_or_fileobj=str(readme_src),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="model",
            commit_message="Add model card",
        )
    return {"repo_id": repo_id, "url": f"https://huggingface.co/{repo_id}"}


def create_space_repo(*, space_id: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"space_id": space_id, "dry_run": True}

    token = _token()
    if not token:
        raise SystemExit("HF_TOKEN required for Space creation")

    from huggingface_hub import HfApi, create_repo

    api = HfApi(token=token)
    create_repo(space_id, repo_type="space", exist_ok=True, space_sdk="gradio")

    hf_space = ROOT / "hf_space"
    for name in ("app.py", "requirements.txt", "README.md"):
        path = hf_space / name
        if path.exists():
            api.upload_file(
                path_or_fileobj=str(path),
                path_in_repo=name,
                repo_id=space_id,
                repo_type="space",
                commit_message="Jekyll & Hyde Gradio demo",
            )

    # safety_eval package (minimal import surface for Space)
    for rel in (
        "safety_eval/__init__.py",
        "safety_eval/platform/__init__.py",
        "safety_eval/platform/lora_router.py",
        "safety_eval/platform/lora_mix_cache.py",
        "safety_eval/platform/decoding_entropy.py",
        "safety_eval/platform/local_model.py",
        "safety_eval/platform/output_guard.py",
        "config/learning.yaml",
    ):
        path = ROOT / rel
        if path.exists():
            api.upload_file(
                path_or_fileobj=str(path),
                path_in_repo=rel.replace("\\", "/"),
                repo_id=space_id,
                repo_type="space",
                commit_message="Add safety_eval deps for Space",
            )

    return {"space_id": space_id, "url": f"https://huggingface.co/spaces/{space_id}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload adapters + optional Gradio Space to HF Hub")
    parser.add_argument("--user", default=os.environ.get("HF_USER", DEFAULT_USER))
    parser.add_argument("--jekyll-repo", default=None)
    parser.add_argument("--hyde-repo", default=None)
    parser.add_argument("--space", default=None, help="e.g. Benjamin5607/jekyll-hyde-demo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--adapters-only", action="store_true")
    args = parser.parse_args()

    user = args.user
    if user == DEFAULT_USER:
        try:
            from huggingface_hub import HfApi

            who = HfApi(token=_token()).whoami()
            user = who.get("name") or user
        except Exception:
            pass
    jekyll_repo = args.jekyll_repo or f"{user}/jekyll-hyde-jekyll-lora"
    hyde_repo = args.hyde_repo or f"{user}/jekyll-hyde-hyde-lora"
    space_id = args.space or f"{user}/jekyll-hyde-demo"

    jekyll_dir = ROOT / "models" / "adapters" / "jekyll-lora"
    hyde_dir = ROOT / "models" / "adapters" / "hyde-lora"

    results = []
    results.append(
        upload_adapter(
            local_dir=jekyll_dir,
            repo_id=jekyll_repo,
            readme_src=ROOT / "hf_hub" / "jekyll-lora-README.md",
            dry_run=args.dry_run,
            private=args.private,
        )
    )
    results.append(
        upload_adapter(
            local_dir=hyde_dir,
            repo_id=hyde_repo,
            readme_src=ROOT / "hf_hub" / "hyde-lora-README.md",
            dry_run=args.dry_run,
            private=args.private,
        )
    )

    if not args.adapters_only:
        results.append(create_space_repo(space_id=space_id, dry_run=args.dry_run))

    import json

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
