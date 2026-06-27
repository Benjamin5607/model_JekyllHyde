"""Post-merge quantization export (GGUF via llama.cpp when available)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MERGED = ROOT / "models" / "merged" / "jekyll-hyde"


def gguf_output_path(quantize: str = "q4_k_m") -> Path:
    tag = quantize.lower().replace("-", "_")
    return MERGED / f"jekyll-hyde-{tag}.gguf"


def _find_llama_convert() -> Path | None:
    for name in ("convert_hf_to_gguf.py", "convert.py"):
        p = shutil.which(name)
        if p:
            return Path(p)
    llama_dirs = [
        ROOT / "tools" / "llama.cpp",
        ROOT / "tools" / "llama-bin",
        Path.home() / "llama.cpp",
    ]
    for base in llama_dirs:
        script = base / "convert_hf_to_gguf.py"
        if script.exists():
            return script
    return None


def prune_stale_gguf(*, keep: Path | None = None) -> list[str]:
    """Remove old GGUF/F16 artifacts before a fresh export."""
    removed: list[str] = []
    if not MERGED.exists():
        return removed
    keep_resolved = keep.resolve() if keep else None
    for pattern in ("*.gguf",):
        for path in MERGED.glob(pattern):
            if keep_resolved and path.resolve() == keep_resolved:
                continue
            path.unlink(missing_ok=True)
            removed.append(path.name)
    return removed


def export_gguf(*, quantize: str = "q4_k_m", prune_old: bool = True) -> dict:
    """Export merged HF weights to GGUF; non-fatal when llama.cpp is missing."""
    if not (MERGED / "config.json").exists():
        return {"ok": False, "reason": "merged model missing"}

    out_path = gguf_output_path(quantize)
    if prune_old:
        prune_stale_gguf(keep=None)

    convert = _find_llama_convert()
    if convert is None:
        return {
            "ok": False,
            "reason": "llama.cpp convert_hf_to_gguf.py not found — runtime uses 4-bit bitsandbytes instead",
            "skipped": True,
        }

    f16 = MERGED / "jekyll-hyde-f16.gguf"
    python = sys.executable
    try:
        subprocess.run(
            [python, str(convert), str(MERGED), "--outfile", str(f16), "--outtype", "f16"],
            check=True,
            timeout=7200,
            cwd=str(convert.parent),
        )
        quantize_bin = shutil.which("llama-quantize") or shutil.which("quantize")
        if quantize_bin is None:
            for base in (ROOT / "tools" / "llama-bin", ROOT / "tools" / "llama.cpp" / "build" / "bin"):
                for name in ("llama-quantize.exe", "llama-quantize", "quantize.exe"):
                    candidate = base / name
                    if candidate.exists():
                        quantize_bin = str(candidate)
                        break
                if quantize_bin:
                    break
                for candidate in base.rglob("llama-quantize.exe"):
                    quantize_bin = str(candidate)
                    break
        if quantize_bin and f16.exists():
            subprocess.run(
                [quantize_bin, str(f16), str(out_path), quantize.upper()],
                check=True,
                timeout=7200,
            )
            f16.unlink(missing_ok=True)
            if prune_old:
                prune_stale_gguf(keep=out_path)
            return {
                "ok": True,
                "path": str(out_path),
                "size_mb": round(out_path.stat().st_size / 1e6, 1),
                "quantized": True,
            }
        return {"ok": True, "path": str(f16), "quantized": False}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:300]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export merged model to GGUF (optional)")
    parser.add_argument("--quant", default="q4_k_m")
    parser.add_argument("--no-prune", action="store_true")
    args = parser.parse_args()
    result = export_gguf(quantize=args.quant, prune_old=not args.no_prune)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
