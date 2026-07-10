#!/usr/bin/env python3
"""
Tri-deploy setup: Ollama GGUF personas + Groq env + HF demo pointers.

  [demo]  HF Space ZeroGPU  — already at hf_space/
  [api]   Oracle + Ollama   — jekyll-hyde-jekyll / jekyll-hyde-hyde GGUF
  [agent] Groq free tier    — GROQ_API_KEY + persona prompts

Usage:
  python scripts/setup_triple_deploy.py --merge --gguf --ollama
  python scripts/setup_triple_deploy.py --print-env
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MERGED_ROOT = ROOT / "models" / "merged"
PERSONAS = ("jekyll", "hyde")


def _merge_persona(persona: str) -> Path:
    import torch
    import yaml
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    cfg_path = ROOT / "training" / "config.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    adapter_dir = Path(cfg["adapters"][persona])
    if not (adapter_dir / "adapter_config.json").exists():
        raise SystemExit(f"Adapter missing: {adapter_dir} — run train_lora.py --persona {persona}")

    out_dir = MERGED_ROOT / f"jekyll-hyde-{persona}"
    base_id = cfg["base_models"][cfg.get("default_base", "gemma3-4b")]["huggingface"]
    print(f"Merging {persona} -> {out_dir}")
    base = AutoModelForCausalLM.from_pretrained(
        base_id, trust_remote_code=True, torch_dtype=torch.float16, device_map="cpu"
    )
    tokenizer = AutoTokenizer.from_pretrained(base_id, trust_remote_code=True)
    merged = PeftModel.from_pretrained(base, str(adapter_dir)).merge_and_unload()
    out_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    return out_dir


def _export_gguf(merged_dir: Path, quant: str = "q4_k_m") -> dict:
    from training.quantize_export import export_gguf

    # Temporarily point export at persona dir
    import training.quantize_export as qe

    old = qe.MERGED
    qe.MERGED = merged_dir
    try:
        tag = quant.lower().replace("-", "_")
        out = merged_dir / f"jekyll-hyde-{merged_dir.name.split('-')[-1]}-{tag}.gguf"
        result = export_gguf(quantize=quant, prune_old=True)
        result["expected"] = str(out)
        return result
    finally:
        qe.MERGED = old


def _write_modelfile(persona: str, gguf_path: Path | None, hf_dir: Path) -> Path:
    from safety_eval.platform.persona import CORE_IDENTITY, HYDE_PERSONA, JEKYLL_PERSONA

    persona_block = JEKYLL_PERSONA if persona == "jekyll" else HYDE_PERSONA
    system = f'{CORE_IDENTITY}\n\n{persona_block}'.replace('"""', "'''")
    src = gguf_path if gguf_path and gguf_path.exists() else hf_dir
    from_line = f'FROM {src.resolve().as_posix()}'
    temp = 0.2 if persona == "jekyll" else 0.35
    content = f"""{from_line}

PARAMETER temperature {temp}
PARAMETER top_p 0.9
PARAMETER num_ctx 8192

SYSTEM \"\"\"
{system}
\"\"\"
"""
    out = ROOT / "models" / f"Modelfile.{persona}"
    out.write_text(content, encoding="utf-8")
    return out


def _ollama_create(name: str, modelfile: Path) -> str:
    result = subprocess.run(
        ["ollama", "create", name, "-f", str(modelfile)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "ollama create failed")
    return f"Created Ollama model: {name}"


def print_env() -> None:
    from safety_eval.platform.inference_config import deployment_summary

    summary = deployment_summary()
    print(
        json.dumps(
            {
                "deployment": summary,
                "env_template": {
                    "JH_API_BACKEND": "ollama",
                    "JH_AGENT_BACKEND": "groq",
                    "JH_OLLAMA_URL": "http://127.0.0.1:11434",
                    "GROQ_API_KEY": "<from https://console.groq.com/keys>",
                    "GROQ_MODEL": "llama-3.1-8b-instant",
                    "HF_SPACE": "https://benjamin5607-jekyll-hyde-demo.hf.space",
                },
            },
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup tri-deploy (Ollama + Groq + HF demo)")
    parser.add_argument("--merge", action="store_true", help="Merge jekyll + hyde LoRA into separate HF dirs")
    parser.add_argument("--gguf", action="store_true", help="Export GGUF (needs llama.cpp)")
    parser.add_argument("--quant", default="q4_k_m")
    parser.add_argument("--ollama", action="store_true", help="ollama create jekyll-hyde-jekyll / hyde")
    parser.add_argument("--print-env", action="store_true")
    args = parser.parse_args()

    if args.print_env:
        print_env()
        return 0

    results: dict = {"personas": {}}

    if args.merge or args.gguf or args.ollama:
        for persona in PERSONAS:
            merged_dir = _merge_persona(persona)
            entry: dict = {"merged_dir": str(merged_dir)}
            gguf_path = None
            if args.gguf:
                entry["gguf"] = _export_gguf(merged_dir, quant=args.quant)
                tag = args.quant.lower().replace("-", "_")
                candidate = merged_dir / f"jekyll-hyde-{persona}-{tag}.gguf"
                if candidate.exists():
                    gguf_path = candidate
            mf = _write_modelfile(persona, gguf_path, merged_dir)
            entry["modelfile"] = str(mf)
            if args.ollama:
                name = f"jekyll-hyde-{persona}"
                try:
                    entry["ollama"] = _ollama_create(name, mf)
                except Exception as exc:
                    if persona == "hyde":
                        alias = ROOT / "models" / "Modelfile.hyde.alias"
                        entry["ollama"] = _ollama_create(name, alias)
                        entry["ollama_note"] = f"alias fallback: {exc}"
                    else:
                        raise
                time.sleep(5)
            results["personas"][persona] = entry

    results["next_steps"] = [
        "Oracle: bash deploy/oracle/setup.sh",
        "Agent: export GROQ_API_KEY=... && JH_AGENT_BACKEND=groq",
        "API: JH_API_BACKEND=ollama python -m safety_eval.platform.serve --host 0.0.0.0 --port 8080",
        "Demo: https://benjamin5607-jekyll-hyde-demo.hf.space",
    ]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
