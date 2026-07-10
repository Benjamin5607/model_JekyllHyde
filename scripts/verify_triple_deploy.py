#!/usr/bin/env python3
"""Verify tri-deploy: Ollama API + Groq agent + HF demo URL."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_secrets() -> None:
    env = ROOT / "secrets" / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    _load_secrets()
    results: dict = {"checks": []}

    def ok(name: str, detail: str = "") -> None:
        results["checks"].append({"name": name, "ok": True, "detail": detail})

    def fail(name: str, detail: str) -> None:
        results["checks"].append({"name": name, "ok": False, "detail": detail})

    from safety_eval.platform.inference_config import deployment_summary, ollama_settings
    from safety_eval.platform.groq_client import chat as groq_chat, groq_available
    from safety_eval.platform.inference_router import generate
    from safety_eval.platform.ollama_client import model_exists, ollama_available

    ds = deployment_summary()
    results["deployment"] = ds

    url = os.environ.get("JH_OLLAMA_URL", "http://127.0.0.1:11434")
    if ollama_available(url):
        ok("ollama_reachable", url)
        ocfg = ollama_settings()
        models = ocfg["models"]
        hyde_model = os.environ.get("JH_OLLAMA_HYDE", models.get("hyde", "jekyll-hyde-hyde"))
        for m in (models.get("jekyll", "jekyll-hyde-jekyll"), hyde_model, models.get("chat", "jekyll-hyde")):
            if model_exists(m, url):
                ok(f"ollama_model_{m}")
            else:
                fail(f"ollama_model_{m}", "missing")
    else:
        fail("ollama_reachable", url)

    try:
        text, rt = generate(
            [{"role": "user", "content": "Reply with exactly: API_OK"}],
            role="api",
            adapter="jekyll",
            max_new_tokens=32,
        )
        if "API_OK" in text or len(text) > 3:
            ok("api_inference", f"{rt.backend}/{rt.name}")
        else:
            fail("api_inference", text[:80])
    except Exception as exc:
        fail("api_inference", str(exc)[:200])

    if groq_available():
        try:
            g = groq_chat(
                [{"role": "user", "content": "Reply with exactly: GROQ_OK"}],
                persona="jekyll",
                max_tokens=32,
            )
            if "GROQ_OK" in g or len(g) > 3:
                ok("groq_agent", g[:60])
            else:
                fail("groq_agent", g[:80])
        except Exception as exc:
            fail("groq_agent", str(exc)[:200])
    else:
        fail("groq_agent", "GROQ_API_KEY not set in secrets/.env")

    hf = ds.get("hf_space", "")
    if hf.startswith("http"):
        ok("hf_demo_url", hf)
    else:
        fail("hf_demo_url", "not configured")

    passed = sum(1 for c in results["checks"] if c["ok"])
    total = len(results["checks"])
    results["summary"] = f"{passed}/{total} passed"
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
