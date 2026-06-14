"""Registry and orchestration for free verification providers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import yaml

from safety_eval.verification.base import VerificationFinding, VerificationReport
from safety_eval.platform.prefs import provider_enabled_override
from safety_eval.verification.providers import (
    arxiv,
    conceptnet,
    dictionary_api,
    duckduckgo,
    local_guidelines,
    local_jekyll,
    local_logic,
    openlibrary,
    open_meteo,
    restcountries,
    wikidata,
    wikipedia,
)

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "verification_providers.yaml"

ProviderFn = Callable[..., VerificationFinding]

_REGISTRY: dict[str, ProviderFn] = {
    "local_guidelines": local_guidelines.verify,
    "local_jekyll": local_jekyll.verify,
    "local_logic": local_logic.verify,
    "wikipedia": wikipedia.verify,
    "duckduckgo": duckduckgo.verify,
    "wikidata": wikidata.verify,
    "arxiv": arxiv.verify,
    "dictionary": dictionary_api.verify,
    "conceptnet": conceptnet.verify,
    "open_meteo": open_meteo.verify,
    "restcountries": restcountries.verify,
    "openlibrary": openlibrary.verify,
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"providers": {k: {"enabled": True} for k in _REGISTRY}}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def list_providers() -> list[dict]:
    cfg = load_config()
    providers_cfg = cfg.get("providers", {})
    out = []
    for name, fn in _REGISTRY.items():
        pc = providers_cfg.get(name, {})
        override = provider_enabled_override(name)
        enabled = override if override is not None else pc.get("enabled", True)
        out.append({
            "name": name,
            "enabled": enabled,
            "description": pc.get("description", fn.__doc__ or ""),
            "kind": pc.get("kind", "http"),
        })
    return out


def list_mcp_servers() -> list[dict]:
    cfg = load_config()
    servers = cfg.get("mcp_servers", {})
    return [{"name": k, **v} for k, v in servers.items()]


def _extract_query(text: str, topic: str = "") -> str:
    combined = f"{topic} {text}".strip()
    # Prefer quoted probe content
    quoted = re.findall(r"['\"]([^'\"]{8,120})['\"]", combined)
    if quoted:
        return quoted[0][:120]
    words = re.findall(r"[A-Za-z가-힣]{4,}", combined)
    if words:
        return " ".join(words[:8])
    return combined[:120] or "community guidelines moderation"


def _build_context(findings: list[VerificationFinding]) -> str:
    lines = ["EXTERNAL VERIFICATION (free APIs + local checks):"]
    for f in findings:
        if f.ok and f.finding:
            lines.append(f"- [{f.provider}] ({f.support}, conf={f.confidence:.2f}) {f.finding[:400]}")
        elif f.error:
            lines.append(f"- [{f.provider}] unavailable: {f.error[:120]}")
    return "\n".join(lines)


def run_verification(
    *,
    text: str,
    topic: str = "",
    guidelines_text: str = "",
    guidelines_title: str = "Guidelines",
    prior_turns: list[dict] | None = None,
    providers: list[str] | None = None,
) -> VerificationReport:
    cfg = load_config()
    providers_cfg = cfg.get("providers", {})
    query = _extract_query(text, topic)

    enabled = providers or []
    if not enabled:
        for name in _REGISTRY:
            pc = providers_cfg.get(name, {})
            override = provider_enabled_override(name)
            is_on = override if override is not None else pc.get("enabled", True)
            if is_on:
                enabled.append(name)

    findings: list[VerificationFinding] = []
    ok_count = 0
    fail_count = 0

    for name in enabled:
        fn = _REGISTRY.get(name)
        if not fn:
            continue
        try:
            finding = fn(
                query=query,
                text=text,
                topic=topic,
                guidelines_text=guidelines_text,
                guidelines_title=guidelines_title,
                prior_turns=prior_turns or [],
            )
        except Exception as exc:
            finding = VerificationFinding(
                provider=name,
                query=query,
                finding="",
                ok=False,
                error=str(exc),
            )
        findings.append(finding)
        if finding.ok and finding.finding:
            ok_count += 1
        else:
            fail_count += 1

    return VerificationReport(
        query=query,
        findings=findings,
        context_block=_build_context(findings),
        providers_ok=ok_count,
        providers_failed=fail_count,
    )
