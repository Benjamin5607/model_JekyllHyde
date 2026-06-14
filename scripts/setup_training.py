#!/usr/bin/env python3
"""One-shot setup: GPU venv, HuggingFace auth, Gemma access check."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv-train"
HF_GEMMA_MODEL = "google/gemma-2-2b-it"
LICENSE_URL = f"https://huggingface.co/{HF_GEMMA_MODEL}"


def find_python312() -> Path | None:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python312/python.exe",
        Path("C:/Program Files/Python312/python.exe"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, check=False, **kwargs)


def ensure_venv(py312: Path) -> Path:
    if not VENV.exists():
        run([str(py312), "-m", "venv", str(VENV)])
    return VENV / "Scripts/python.exe"


def pip_install(venv_python: Path) -> None:
    run([str(venv_python), "-m", "pip", "install", "-U", "pip", "wheel"])
    run([
        str(venv_python), "-m", "pip", "install",
        "torch", "torchvision", "torchaudio",
        "--index-url", "https://download.pytorch.org/whl/cu128",
    ])
    run([str(venv_python), "-m", "pip", "install", "-e", f"{ROOT}[train]"])


def check_cuda(venv_python: Path) -> bool:
    code = (
        "import torch;"
        "print('cuda', torch.cuda.is_available());"
        "print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"
    )
    result = run([str(venv_python), "-c", code])
    return result.returncode == 0


def setup_hf_token(token: str | None, venv_python: Path | None = None) -> None:
    token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    secrets = ROOT / "secrets"
    secrets.mkdir(exist_ok=True)
    token_file = secrets / "hf_token.txt"
    py = venv_python or Path(sys.executable)
    if token:
        token_file.write_text(token.strip(), encoding="utf-8")
        os.environ["HF_TOKEN"] = token.strip()
        run([
            str(py),
            "-c",
            f"from huggingface_hub import login; login(token={token.strip()!r}, add_to_git_credential=False)",
        ])
    elif token_file.exists():
        os.environ["HF_TOKEN"] = token_file.read_text(encoding="utf-8").strip()
        print("Using existing secrets/hf_token.txt")
    else:
        print(f"""
HuggingFace token required for Gemma LoRA.
1. Open {LICENSE_URL}
2. Log in and click 'Agree and access repository'
3. Create token: https://huggingface.co/settings/tokens
4. Run: python scripts/setup_training.py --hf-token hf_xxxx
   Or save token to secrets/hf_token.txt (gitignored)
""")


def test_gemma_access(venv_python: Path) -> bool:
    code = f"""
from huggingface_hub import hf_hub_download
try:
    path = hf_hub_download("{HF_GEMMA_MODEL}", "config.json")
    print("Gemma access OK:", path)
except Exception as e:
    print("Gemma access FAILED:", e)
    raise SystemExit(1)
"""
    result = run([str(venv_python), "-c", code])
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf-token", help="HuggingFace read token")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--base", default="gemma2-2b")
    args = parser.parse_args()

    py312 = find_python312()
    if not py312:
        raise SystemExit("Python 3.12 not found. Run: winget install Python.Python.3.12")

    print(f"Using Python 3.12: {py312}")
    venv_py = ensure_venv(py312)
    pip_install(venv_py)
    check_cuda(venv_py)
    setup_hf_token(args.hf_token, venv_py)

    if not test_gemma_access(venv_py):
        raise SystemExit(1)

    run([str(venv_py), str(ROOT / "training" / "prepare_dataset.py")])

    if args.skip_train:
        print("Setup complete (skip train).")
        return

    run([str(venv_py), str(ROOT / "training" / "train_lora.py"), "--base", args.base, "--4bit"])
    run([str(venv_py), str(ROOT / "training" / "merge_and_export.py"), "--base", args.base, "--ollama"])
    print("Done. Model: jekyll-hyde-ft")


if __name__ == "__main__":
    main()
