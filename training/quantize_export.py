"""Optional post-merge quantization export (GGUF via llama.cpp when available)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MERGED = ROOT / "models" / "merged" / "jekyll-hyde"
GGUF_OUT = MERGED / "jekyll-hyde-q4_k_m.gguf"


def _find_llama_convert() -> Path | None:
    for name in ("convert_hf_to_gguf.py", "convert.py"):
        p = shutil.which(name)
        if p:
            return Path(p)
    llama_dirs = [
        ROOT / "tools" / "llama.cpp",
        Path.home() / "llama.cpp",
    ]
    for base in llama_dirs:
        script = base / "convert_hf_to_gguf.py"
        if script.exists():
            return script
    return None


def export_gguf(*, quantize: str = "q4_k_m") -> dict:
    """Try GGUF export; return status dict (non-fatal if tools missing)."""
    if not (MERGED / "config.json").exists():
        return {"ok": False, "reason": "merged model missing"}

    convert = _find_llama_convert()
    if convert is None:
        return {
            "ok": False,
            "reason": "llama.cpp convert_hf_to_gguf.py not found — runtime uses 4-bit bitsandbytes instead",
            "skipped": True,
        }

    f16 = MERGED / "jekyll-hyde-f16.gguf"
    try:
        subprocess.run(
            ["python", str(convert), str(MERGED), "--outfile", str(f16), "--outtype", "f16"],
            check=True,
            timeout=7200,
            cwd=str(convert.parent),
        )
        quantize_bin = shutil.which("llama-quantize") or shutil.which("quantize")
        if quantize_bin and f16.exists():
            subprocess.run([quantize_bin, str(f16), str(GGUF_OUT), quantize.upper()], check=True, timeout=7200)
            f16.unlink(missing_ok=True)
            return {"ok": True, "path": str(GGUF_OUT), "size_mb": round(GGUF_OUT.stat().st_size / 1e6, 1)}
        return {"ok": True, "path": str(f16), "quantized": False}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:300]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export merged model to GGUF (optional)")
    parser.add_argument("--quant", default="q4_k_m")
    args = parser.parse_args()
    result = export_gguf(quantize=args.quant)
    print(result)


if __name__ == "__main__":
    main()
