"""Cross-verify today's specialization + quant pipeline updates."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

FAILURES: list[str] = []


def ok(name: str) -> None:
    print(f"  OK  {name}")


def fail(name: str, detail: str) -> None:
    FAILURES.append(f"{name}: {detail}")
    print(f"  FAIL {name}: {detail}")


def check_imports() -> None:
    print("\n[1] Module imports")
    mods = [
        "safety_eval.specialization.domains",
        "safety_eval.quant.pipeline",
        "safety_eval.quant.harness",
        "safety_eval.quant.research",
        "safety_eval.quant.formatting",
        "safety_eval.platform.formats",
        "safety_eval.i18n.apac",
    ]
    for m in mods:
        try:
            __import__(m)
            ok(m)
        except Exception as exc:
            fail(m, str(exc))


def check_domains() -> None:
    print("\n[2] Specialization domain detection")
    from safety_eval.specialization.domains import build_specialization_block, detect_domains

    cases = [
        ("삼성 vs SK하이닉스 이번 분기 투자 메모", ["quant"]),
        ("가이드라인 section 3 분석", ["policy"]),
        ("gray zone hypothetical research", ["gray_zone"]),
        ("policy weakness gap audit", ["hardening", "policy"]),
    ]
    for text, expected in cases:
        got = detect_domains(text, has_quant="투자" in text)
        if not all(e in got for e in expected):
            fail("detect_domains", f"{text!r} -> {got}, want superset of {expected}")
        else:
            ok(f"detect {expected[0]}")
    block, domains = build_specialization_block("삼성 투자 메모", has_quant=True)
    if "LIVE MARKET DATA" not in block:
        fail("build_specialization_block", "missing LIVE MARKET DATA instruction")
    else:
        ok("quant specialization block")


def check_formats() -> None:
    print("\n[3] Response formats")
    from safety_eval.platform.formats import detect_response_format

    fmt = detect_response_format("삼성 vs SK하이닉스 투자 메모 작성해줘")
    if fmt.id != "investment_memo":
        fail("resolve_response_format", f"got {fmt.id}, want investment_memo")
    else:
        ok("투자 메모 -> investment_memo")


def check_resolver() -> None:
    print("\n[4] Ticker resolver")
    from safety_eval.quant.resolver import resolve_tickers

    tickers = resolve_tickers("삼성 vs SK하이닉스 이번 분기")
    symbols = {t["ticker"] for t in tickers}
    if "005930.KS" not in symbols or "000660.KS" not in symbols:
        fail("resolve_tickers", f"got {symbols}")
    else:
        ok("삼성/SK하이닉스 tickers")
    sk_only = resolve_tickers("SK stock analysis")
    sk_symbols = {t["ticker"] for t in sk_only}
    if sk_symbols == {"005930.KS"}:
        fail("resolve_tickers", f"SK false positive: {sk_only}")
    else:
        ok("no SK-only false positive")


def check_pipeline_mock() -> None:
    print("\n[5] Pipeline (mock LLM)")
    from safety_eval.quant.analyzer import build_quant_context
    from safety_eval.quant.pipeline import run_investment_memo_pipeline, stage_render_facts

    ctx = build_quant_context("삼성 vs SK하이닉스 이번 분기 투자 메모")
    if not ctx or not ctx.snapshots:
        fail("build_quant_context", "empty context")
        return
    facts = stage_render_facts(ctx, "삼성 vs SK하이닉스")
    if "005930" not in facts and "삼성" not in facts:
        fail("stage_render_facts", "missing samsung in facts")
    else:
        ok("stage_render_facts")

    call_n = 0

    def mock_gen(messages, temperature, max_tokens):
        nonlocal call_n
        call_n += 1
        user = messages[-1]["content"]
        if "HEADLINE" in user or "헤드라인" in user:
            return "이 뉴스는 메모리 수요와 실적 전망에 영향을 줍니다. 투자자는 분기 실적 발표를 주시해야 합니다.", None
        return "삼성전자는 다각화로 방어력이 있고 SK하이닉스는 메모리 사이클 민감도가 높습니다. [H1] 인용.", None

    result = run_investment_memo_pipeline(ctx, "삼성 vs SK하이닉스 이번 분기 투자 메모", mock_gen)
    if not result.markdown or "##" not in result.markdown:
        fail("run_investment_memo_pipeline", "empty markdown")
    elif result.llm_calls < 1:
        fail("run_investment_memo_pipeline", f"llm_calls={result.llm_calls}")
    else:
        ok(f"pipeline assembled ({result.llm_calls} LLM calls, {len(result.stages)} stages)")
    if "투자 권유가 아닙니다" not in result.markdown and "Not financial advice" not in result.markdown:
        fail("disclaimer", "missing disclaimer")
    else:
        ok("disclaimer present")


def check_dataset() -> None:
    print("\n[6] Training dataset")
    import json

    path = ROOT / "training" / "datasets" / "jekyll_hyde_train.jsonl"
    if not path.exists():
        fail("dataset", "missing jekyll_hyde_train.jsonl")
        return
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    spec = sum(1 for r in rows if r.get("meta", {}).get("type", "").startswith("specialization"))
    if len(rows) < 40:
        fail("dataset", f"only {len(rows)} rows")
    else:
        ok(f"{len(rows)} training rows ({spec} specialization)")
    from training.specialization_examples import specialization_training_records

    spec_recs = specialization_training_records("SYSTEM")
    if len(spec_recs) < 4:
        fail("specialization_examples", f"only {len(spec_recs)} examples")
    else:
        ok(f"{len(spec_recs)} gold specialization examples")


def check_manifest() -> None:
    print("\n[7] Model manifest")
    import json

    manifest_path = ROOT / "models" / "merged" / "jekyll-hyde" / "jekyll_hyde_manifest.json"
    if not manifest_path.exists():
        fail("manifest", "missing")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = manifest.get("specialization", [])
    if len(spec) < 4:
        fail("manifest", f"specialization={spec}")
    else:
        ok(f"manifest specialization: {len(spec)} domains")


def check_duel_routing() -> None:
    print("\n[8] Duel mode routing")
    from safety_eval.platform.duel import resolve_duel_kind

    q = "compare samsung and hynix for investment insight report for this quarter"
    kind = resolve_duel_kind(q, has_quant=True, has_mcp_guidelines=True)
    if kind != "equity":
        fail("resolve_duel_kind", f"finance duel got {kind}")
    else:
        ok("finance query → equity duel (even with MCP)")
    policy = resolve_duel_kind("audit guideline section 3", has_quant=False, has_mcp_guidelines=True)
    if policy != "guideline":
        fail("resolve_duel_kind", f"policy got {policy}")
    else:
        ok("policy query → guideline duel")
    debate = resolve_duel_kind("should we colonize mars", has_quant=False, has_mcp_guidelines=False)
    if debate != "debate":
        fail("resolve_duel_kind", f"open topic got {debate}")
    else:
        ok("open topic → debate duel")
    from safety_eval.platform.duel import _jekyll_duel_user
    final = _jekyll_duel_user("hyde text", 2, duel_kind="debate", total_rounds=2)
    if "Middle ground" not in final:
        fail("debate synthesis", "final round missing Middle ground prompt")
    else:
        ok("debate final round → middle ground synthesis")


def main() -> int:
    print("=== Jekyll & Hyde cross-verification ===")
    check_imports()
    check_domains()
    check_formats()
    check_resolver()
    check_pipeline_mock()
    check_dataset()
    check_manifest()
    check_duel_routing()
    print("\n=== Summary ===")
    if FAILURES:
        for f in FAILURES:
            print(f"  - {f}")
        print(f"\n{len(FAILURES)} failure(s)")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
