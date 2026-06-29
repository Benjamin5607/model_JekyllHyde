"""MCP server — guidelines, chat, and platform integration."""

from __future__ import annotations

from safety_eval.chat.agent import ChatAgent, ChatSettings
from safety_eval.i18n.apac import APAC_LANGUAGES, APAC_LANGUAGE_POLICY
from safety_eval.platform.engine import JekyllHydeEngine
from safety_eval.platform.model_registry import list_bases
from safety_eval.store import get_guidelines_store
from safety_eval.verification.registry import list_mcp_servers, list_providers, run_verification
from safety_eval.quant import MARKET_SAMPLES, build_quant_context, market_weather_text, scan_market_universe

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemError("Install MCP support: pip install 'jekyll-hyde[mcp]'") from exc

GUIDELINES_CHAT_URL = "http://127.0.0.1:8080"
PLATFORM_URL = "http://127.0.0.1:8080"

mcp = FastMCP(
    "jekyll-hyde",
    instructions=(
        "Jekyll & Hyde — APAC multilingual Gemma-based LLM. "
        "Use set_guidelines to push community rules as plain text. "
        "Open Guidelines Chat at http://127.0.0.1:8770 for MCP-synced conversation."
    ),
)


@mcp.tool()
def get_guidelines() -> str:
    """Return the currently active community guidelines text."""
    store = get_guidelines_store()
    snap = store.snapshot()
    return f"# {snap.title}\n(source: {snap.source}, updated: {snap.updated_at})\n\n{snap.text}"


@mcp.tool()
def set_guidelines(text: str, title: str = "MCP Guidelines") -> str:
    """Set community guidelines from plain text (Markdown). Syncs to Guidelines Chat app."""
    snap = get_guidelines_store().set_text(text, title=title, source="mcp")
    return (
        f"Guidelines saved: {snap.title} ({len(snap.text)} chars)\n"
        f"Open chat app: {GUIDELINES_CHAT_URL}\n"
        f"Updated at: {snap.updated_at}"
    )


@mcp.tool()
def append_guidelines(section: str, text: str) -> str:
    """Append a new section to active guidelines (Markdown heading added automatically)."""
    store = get_guidelines_store()
    merged = store.text.rstrip() + f"\n\n## {section.strip()}\n{text.strip()}\n"
    snap = store.set_text(merged, title=store.title, source="mcp")
    return f"Appended section '{section}'. Total {len(snap.text)} chars. Chat: {GUIDELINES_CHAT_URL}"


@mcp.tool()
def chat_with_model(message: str, jekyll: bool = True, hyde: bool = False, duel_rounds: int = 2) -> str:
    """Chat with Jekyll & Hyde using toggles. Both ON = duel with free API verification."""
    engine = JekyllHydeEngine()
    resp = engine.complete_toggled(message, jekyll=jekyll, hyde=hyde, duel_rounds=duel_rounds)
    header = f"[{resp.mode}|lang={resp.language}|jekyll={resp.jekyll_verdict}]\n"
    if resp.meta.get("verification"):
        header += f"[verification rounds: {len(resp.meta['verification'])}]\n"
    return header + resp.content


@mcp.tool()
def run_duel_verification(topic: str, rounds: int = 2) -> str:
    """Run Hyde↔Jekyll duel with all free verification APIs (Wikipedia, DDG, Wikidata, etc.)."""
    engine = JekyllHydeEngine()
    resp = engine.complete_toggled(topic, jekyll=True, hyde=True, duel_rounds=max(1, min(rounds, 4)))
    lines = [resp.content, "", f"Verdict: {resp.meta.get('verdict', '?')}", resp.meta.get("summary", "")]
    for vr in resp.meta.get("verification", []):
        lines.append(f"\n--- Verify query: {vr.get('query')} ({vr.get('providers_ok')} ok) ---")
        for f in vr.get("findings", [])[:5]:
            if f.get("ok") and f.get("finding"):
                lines.append(f"  [{f['provider']}] {f['finding'][:200]}")
    return "\n".join(lines)


@mcp.tool()
def verify_text(text: str, topic: str = "") -> str:
    """Run all enabled free verification providers on text (guidelines, Wikipedia, DDG, ...)."""
    store = get_guidelines_store()
    report = run_verification(
        text=text,
        topic=topic,
        guidelines_text=store.text,
        guidelines_title=store.title,
    )
    lines = [f"Query: {report.query}", f"Providers OK: {report.providers_ok}", ""]
    for f in report.findings:
        if f.ok and f.finding:
            lines.append(f"[{f.provider}|{f.support}] {f.finding[:300]}")
        elif f.error:
            lines.append(f"[{f.provider}] error: {f.error[:100]}")
    return "\n".join(lines)


@mcp.tool()
def list_verification_providers() -> str:
    """List built-in free verification APIs (no key required)."""
    lines = ["Built-in verification providers (HTTP + local):"]
    for p in list_providers():
        flag = "ON" if p["enabled"] else "OFF"
        lines.append(f"- [{flag}] {p['name']}: {p['description']}")
    lines.append("\nOptional Cursor MCP servers (no API key):")
    for s in list_mcp_servers():
        lines.append(f"- {s['name']}: {s.get('description', '')}")
    lines.append("\nQuant: analyze_stocks, scan_market_region, get_market_weather")
    lines.append("Workforce: delegate_workforce_brief, workforce_status, manager_approve_workforce")
    lines.append("Run: python scripts/setup_free_mcp.py to add MCP servers to Cursor.")
    return "\n".join(lines)


@mcp.tool()
def get_market_weather() -> str:
    """Live global index snapshot (S&P, NASDAQ, KOSPI, Vietnam)."""
    return market_weather_text()


@mcp.tool()
def analyze_stocks(query: str, mode: str = "chat") -> str:
    """Collect price, fundamentals, quarterly trend, news; return analysis context for Jekyll/Hyde."""
    ctx = build_quant_context(query, mode=mode if mode in ("chat", "jekyll", "hyde") else "chat")
    if not ctx:
        return "No finance targets resolved. Example: 'Analyze Samsung vs SK Hynix'"
    engine = JekyllHydeEngine()
    resp = engine.complete(query, mode=mode if mode in ("chat", "jekyll", "hyde") else "chat")
    header = f"[quant tickers: {', '.join(s.ticker for s in ctx.snapshots)}]\n"
    header += ctx.to_prompt_block(mode=mode)[:1200] + "\n\n--- AI Analysis ---\n"
    return header + resp.content


@mcp.tool()
def scan_market_region(market: str = "Korea", limit: int = 10) -> str:
    """Scan APAC/frontier market for top movers with PER/PBR."""
    if market not in MARKET_SAMPLES:
        return f"Unknown market. Options: {', '.join(MARKET_SAMPLES)}"
    rows = scan_market_universe(market, limit=max(1, min(limit, 20)))
    lines = [market_weather_text(), f"\nTop movers in {market}:"]
    for r in rows:
        lines.append(f"- {r['name']} ({r['ticker']}): {r['change_pct']:+.2f}% PER={r.get('per')} src={r['source']}")
    prompt = f"Summarize {market} scan and pick one solid name + one risky name with fundamentals."
    engine = JekyllHydeEngine()
    resp = engine.complete(prompt, mode="jekyll")
    lines.append("\n--- Jekyll Briefing ---\n" + resp.content)
    return "\n".join(lines)


@mcp.tool()
def guidelines_chat_url() -> str:
    """URL of the dedicated MCP Guidelines Chat platform app."""
    return (
        f"Guidelines Chat: {GUIDELINES_CHAT_URL}\n"
        f"Main Platform: {PLATFORM_URL}\n"
        "Start: python -m safety_eval.apps.guidelines_chat.server"
    )


@mcp.tool()
def list_gemma_bases() -> str:
    """List supported Gemma base models for Ollama and LoRA fine-tuning."""
    lines = ["Gemma bases (Ollama + HuggingFace LoRA):"]
    for b in list_bases():
        lines.append(f"- {b['key']}: ollama={b['ollama']} hf={b['huggingface']} ~{b['vram_gb']}GB VRAM")
    return "\n".join(lines)


@mcp.tool()
def list_apac_languages() -> str:
    """List supported APAC language codes and names."""
    lines = [APAC_LANGUAGE_POLICY, "", "Languages:"]
    lines.extend(f"- {code}: {name}" for code, name in APAC_LANGUAGES.items())
    return "\n".join(lines)


@mcp.tool()
def jekyll_classify(message: str, backend: str = "keyword") -> str:
    """Classify a user message against active guidelines (Jekyll)."""
    agent = ChatAgent(settings=ChatSettings(jekyll_backend=backend))
    return agent._jekyll_check(message)


@mcp.tool()
def hyde_sample_probes(count: int = 3) -> str:
    """Generate sample Hyde adversarial probes (APAC, testing only)."""
    agent = ChatAgent()
    agent.settings.attacks_per_round = max(1, min(count, 10))
    return agent._hyde_sample()


@mcp.tool()
def run_evolution(rounds: int = 2, attacks_per_round: int = 8) -> str:
    """Run Hyde vs Jekyll co-evolution on active guidelines."""
    agent = ChatAgent(settings=ChatSettings(rounds=rounds, attacks_per_round=attacks_per_round))
    return agent._run_evolution_summary()


@mcp.tool()
def learning_status() -> str:
    """Continuous learning stats — curated samples, generation, training state."""
    from safety_eval.learning.store import get_learning_store

    s = get_learning_store().status()
    return (
        f"Generation: {s['generation']}\n"
        f"Interactions: {s['interactions_total']}\n"
        f"Curated for training: {s['curated_total']}\n"
        f"Pending until auto-train: {s['curated_since_train']}/{s['train_threshold']}\n"
        f"Training in progress: {s['training_in_progress']}\n"
        f"Last train: {s['last_train_at'] or 'never'}\n"
        f"Last error: {s['last_error'] or 'none'}"
    )


@mcp.tool()
def run_gray_zone_duel(topic: str, rounds: int = 2) -> str:
    """Run Hyde↔Jekyll duel, extract gray zones, synthesize patches, and auto-curate training records."""
    engine = JekyllHydeEngine()
    resp = engine.complete_toggled(topic, jekyll=True, hyde=True, duel_rounds=max(1, min(rounds, 4)))
    gr = resp.meta.get("gray_reinforce")
    if not gr:
        return f"Duel complete. Verdict: {resp.meta.get('verdict')}. No gray zones extracted."
    return (
        f"Verdict: {resp.meta.get('verdict')}\n"
        f"Gray zones: {len(gr.get('zones', []))}\n"
        f"Solutions: {len(gr.get('solutions', []))}\n"
        f"Training records: {gr.get('training_records_written', 0)}\n\n"
        f"{gr.get('synthesis_markdown', '')[:4000]}"
    )


@mcp.tool()
def run_continuous_learning(train: bool = False) -> str:
    """Curate chat feedback into LoRA dataset; optionally run incremental retrain."""
    from safety_eval.learning.pipeline import get_pipeline

    result = get_pipeline().run_now(train=train)
    return str(result)


@mcp.tool()
def delegate_workforce_brief(brief: str) -> str:
    """Manager-Worker: enqueue data-only workers for a one-sentence brief (returns job id immediately)."""
    from safety_eval.mcp.workforce import delegate_brief, plan_from_brief

    job = delegate_brief(brief)
    plan = " → ".join(s.worker for s in plan_from_brief(brief))
    return (
        f"Job {job.id} queued.\n"
        f"Brief: {brief[:200]}\n"
        f"Worker chain: {plan}\n"
        f"Poll: workforce_status(job_id='{job.id}')\n"
        f"Approve: manager_approve_workforce(job_id='{job.id}') when status=workers_complete"
    )


@mcp.tool()
def workforce_status(job_id: str) -> str:
    """Poll Manager-Worker job status and partial worker outputs."""
    from safety_eval.mcp.workforce import get_job

    job = get_job(job_id)
    if not job:
        return f"Job not found: {job_id}"
    lines = [
        f"Job: {job.id}",
        f"Status: {job.status.value}",
        f"Brief: {job.brief[:160]}",
        f"Workers: {len(job.results)}/{len(job.plan)}",
    ]
    for r in job.results:
        flag = "OK" if r.ok else "FAIL"
        lines.append(f"  [{flag}] {r.worker} ({r.elapsed_ms}ms)")
        if r.error:
            lines.append(f"    error: {r.error[:120]}")
    if job.manager_verdict:
        lines.append(f"\n--- Manager verdict ---\n{job.manager_verdict[:3000]}")
    if job.error:
        lines.append(f"\nError: {job.error}")
    return "\n".join(lines)


@mcp.tool()
def manager_approve_workforce(job_id: str) -> str:
    """Manager (JekyllHyde LLM) synthesizes worker bundle and RLAIF-scores the final report."""
    from safety_eval.mcp.workforce import manager_approve

    job = manager_approve(job_id)
    meta = job.manager_meta or {}
    rlaif = meta.get("rlaif", {})
    header = (
        f"Status: {job.status.value}\n"
        f"RLAIF score: {rlaif.get('score', '?')} — {'PASS' if meta.get('approved') else 'REVIEW'}\n\n"
    )
    return header + (job.manager_verdict or job.error or "No verdict")


@mcp.tool()
def run_workforce_brief(brief: str, wait_seconds: int = 120) -> str:
    """Blocking: delegate workers, wait, then manager approve — full Manager-Worker pipeline."""
    from safety_eval.mcp.workforce import run_brief_sync

    job = run_brief_sync(brief, wait_seconds=float(max(30, min(wait_seconds, 300))))
    meta = job.manager_meta or {}
    rlaif = meta.get("rlaif", {})
    header = (
        f"Job: {job.id}\n"
        f"Status: {job.status.value}\n"
        f"RLAIF score: {rlaif.get('score', '?')} — {'PASS' if meta.get('approved') else 'REVIEW'}\n\n"
    )
    return header + (job.manager_verdict or job.error or "Workers finished; no manager verdict")


@mcp.tool()
def list_workforce_workers() -> str:
    """List data-only MCP workers (no LLM — manager approves final output)."""
    from safety_eval.mcp.workforce import list_workers

    lines = ["Manager-Worker data workers (JekyllHyde manager approves final report):"]
    for w in list_workers():
        lines.append(f"- {w['name']}: {w['desc']}")
    lines.append("\nOne-liner: delegate_workforce_brief('IT sector gray zone report this quarter')")
    return "\n".join(lines)


@mcp.tool()
def lora_pipeline_help() -> str:
    """Instructions for LoRA fine-tuning pipeline."""
    return """
LoRA fine-tune pipeline:
1. python training/prepare_dataset.py
2. pip install -e '.[train]'
3. python training/train_lora.py --base gemma2-2b --4bit
4. python training/merge_and_export.py --base gemma2-2b

Continuous learning (from platform chat):
- Chat auto-records quality turns → data/learning/curated_train.jsonl
- python training/continuous.py --curate-only
- python training/continuous.py --train   (or scripts\\evolve_train.bat)
- Auto-train when 20+ curated samples (config/learning.yaml)

Manager-Worker (v1.4): delegate_workforce_brief → workforce_status → manager_approve_workforce

Bases: gemma2-2b, gemma2-9b, gemma3-4b, gemma3-12b
"""


@mcp.resource("guidelines://active")
def guidelines_resource() -> str:
    return get_guidelines_store().text


@mcp.resource("guidelines://default")
def default_guidelines_resource() -> str:
    store = get_guidelines_store()
    store.load_file(store.default_path)
    return store.text


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
