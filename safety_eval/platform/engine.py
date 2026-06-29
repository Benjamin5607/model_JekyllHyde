"""Jekyll & Hyde LLM engine — the model runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from safety_eval.blue_team import build_blue_team
from safety_eval.i18n.apac import detect_user_language, language_generation_reminder, reply_language_name
from safety_eval.platform.ollama_client import MODEL_NAME
from safety_eval.platform.output_guard import sanitize_chat_output
from safety_eval.platform.router import compute_lora_mix, resolve_persona_focus
from safety_eval.platform.runtime import describe_runtime, generate, runtime_ready
from safety_eval.platform.duel import run_duel
from safety_eval.platform.formats import build_format_block, format_refusal, max_tokens_for_format, temperature_for_format
from safety_eval.platform.persona import build_system_prompt
from safety_eval.specialization.domains import build_specialization_block, primary_domain
from safety_eval.quant.analyzer import build_quant_context, finance_query_with_history, is_finance_query, is_temporal_market_correction
from safety_eval.quant.compact import compact_quant_digest
from safety_eval.quant.pipeline import run_investment_memo_pipeline
from safety_eval.store import GuidelinesStore, get_guidelines_store
from safety_eval.learning.collector import get_collector
from safety_eval.learning.gray_reinforce import GrayReinforcer

Mode = Literal["chat", "jekyll", "hyde", "duel"]


@dataclass
class EngineResponse:
    content: str
    role: str = "assistant"
    mode: str = "chat"
    blocked_input: bool = False
    blocked_output: bool = False
    jekyll_verdict: str = "allowed"
    language: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineConfig:
    ollama_url: str = "http://localhost:11434"
    model: str = MODEL_NAME
    mode: Mode = "chat"
    jekyll_guard: bool = True
    temperature: float = 0.7


class JekyllHydeEngine:
    """
    Jekyll & Hyde product model runtime.

    Primary path: merged fine-tuned weights at models/merged/jekyll-hyde (local GPU).
    Ollama is only a fallback when the merged model is absent.
    """

    def __init__(
        self,
        config: EngineConfig | None = None,
        store: GuidelinesStore | None = None,
    ):
        self.config = config or EngineConfig()
        self.store = store or get_guidelines_store()
        self.history: list[dict[str, str]] = []

    def _jekyll_check(self, text: str) -> tuple[bool, str]:
        if not self.config.jekyll_guard:
            return False, "allowed"
        path = self.store.active_path()
        jekyll = build_blue_team(
            "keyword",
            guidelines_path=path,
            rules_path=path.parent / "keyword_rules.yaml",
        )
        result = jekyll.classify(text)
        if result.blocked:
            return True, "blocked"
        if result.flagged:
            return False, "flagged"
        return False, "allowed"

    def _refusal(self, lang: str | None, reason: str = "guidelines") -> str:
        return format_refusal(lang, reason)

    def resolve_mode(self, *, jekyll: bool, hyde: bool) -> Mode:
        if jekyll and hyde:
            return "duel"
        if jekyll:
            return "jekyll"
        if hyde:
            return "hyde"
        return "chat"

    def complete_toggled(
        self,
        user_message: str,
        *,
        jekyll: bool = True,
        hyde: bool = False,
        duel_rounds: int = 2,
        history: list[dict[str, str]] | None = None,
    ) -> EngineResponse:
        mode = self.resolve_mode(jekyll=jekyll, hyde=hyde)
        if mode == "duel":
            return self._complete_duel(user_message, rounds=duel_rounds)
        return self.complete(user_message, mode=mode, history=history)

    def _complete_duel(self, user_message: str, *, rounds: int = 2) -> EngineResponse:
        lang = detect_user_language(user_message)
        topic = user_message.strip() or (
            "Open debate on the user's question."
            if not self.store.has_mcp_guidelines()
            else "General guideline stress test across all active sections."
        )
        quant_ctx = build_quant_context(user_message, mode="duel")
        if quant_ctx:
            topic += "\n" + compact_quant_digest(quant_ctx)

        if not runtime_ready():
            return EngineResponse(
                content="Duel mode requires the fine-tuned jekyll-hyde model.",
                mode="duel",
                language=lang,
                meta={"error": "model_unavailable"},
            )

        try:
            mcp_gl = self.store.has_mcp_guidelines()
            snap = self.store.snapshot()
            result = run_duel(
                topic=topic,
                guidelines_text=snap.text if mcp_gl else "",
                guidelines_title=snap.title if mcp_gl else "",
                rounds=rounds,
                ollama_url=self.config.ollama_url,
                model_name=self.config.model,
                temperature=self.config.temperature,
                guideline_enforcement=mcp_gl,
                user_message=user_message,
            )
            gray_report = None
            reinforcer = GrayReinforcer()
            if reinforcer.enabled():
                gray_report = reinforcer.reinforce_from_duel(
                    result,
                    topic=user_message.strip() or topic.split("\n")[0],
                    guidelines_text=snap.text if mcp_gl else "",
                    generate_fn=generate,
                )
            runtime = describe_runtime()
            transcript = "\n\n".join(
                f"{'HYDE' if t.speaker == 'hyde' else 'JEKYLL'} (R{t.round_num}): {t.content}"
                for t in result.turns
            )
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": transcript})

            rec = get_collector().record_turn(
                user=user_message,
                assistant=transcript,
                mode="duel",
                format_id="duel_transcript",
                language=lang,
                meta={
                    "duel": True,
                    "verdict": result.verdict,
                    "duel_kind": result.mode,
                    "gray_zones": len(gray_report.zones) if gray_report else 0,
                    "gray_reinforce_records": gray_report.training_records_written if gray_report else 0,
                },
            )

            meta = {
                "model": runtime.name,
                "backend": runtime.backend,
                "fine_tuned": runtime.fine_tuned,
                "duel": result.to_dict(),
                "verdict": result.verdict,
                "summary": result.summary,
                "verification": result.verification,
                "interaction_id": rec.id if rec else None,
            }
            if gray_report and gray_report.zones:
                meta["gray_reinforce"] = gray_report.to_dict()
                meta["summary"] = (
                    f"{result.summary} · {len(gray_report.zones)} gray zone(s) · "
                    f"{len(gray_report.solutions)} patch(es) · "
                    f"{gray_report.training_records_written} training record(s)"
                )

            return EngineResponse(
                content=transcript,
                mode="duel",
                language=lang,
                meta=meta,
            )
        except Exception as exc:
            return EngineResponse(
                content=f"Duel error: {exc}",
                mode="duel",
                language=lang,
                meta={"error": str(exc)},
            )

    def complete(
        self,
        user_message: str,
        *,
        mode: Mode | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> EngineResponse:
        mode = mode or self.config.mode
        lang = detect_user_language(user_message)

        blocked_in, verdict_in = self._jekyll_check(user_message)
        if blocked_in and mode != "hyde":
            return EngineResponse(
                content=self._refusal(lang),
                mode=mode,
                blocked_input=True,
                jekyll_verdict=verdict_in,
                language=lang,
                meta={"guard": "input", "format": "refusal", "format_label": "Refusal"},
            )

        source_history = history if history is not None else self.history
        finance_query = finance_query_with_history(user_message, source_history)
        needs_quant = is_finance_query(user_message) or is_temporal_market_correction(user_message)

        quant_ctx = build_quant_context(finance_query if needs_quant else user_message, mode=mode)
        has_comparison = bool(quant_ctx and len(quant_ctx.snapshots) >= 2)

        has_gl = bool(self.store.text.strip())
        spec_block, domains = build_specialization_block(
            user_message,
            mode=mode,
            has_quant=bool(quant_ctx),
            has_guidelines=has_gl,
        )

        try:
            from safety_eval.learning.memory_store import get_rule_memory

            mem_block = get_rule_memory().format_block(user_message)
            if mem_block:
                spec_block = f"{spec_block}\n\n{mem_block}" if spec_block else mem_block
        except Exception:
            pass

        format_block, response_format = build_format_block(
            user_message,
            mode=mode,
            has_quant=bool(quant_ctx),
            has_comparison=has_comparison,
            guideline_enforcement=self.store.has_mcp_guidelines(),
            domains=domains,
        )

        analyst_harness = bool(
            quant_ctx and quant_ctx.snapshots and response_format.id == "investment_memo"
        )

        if analyst_harness:
            locked_preamble = ""  # pipeline assembles facts internally
            user_payload = ""
            quant_block = ""
        else:
            locked_preamble = ""
            quant_block = compact_quant_digest(quant_ctx) if quant_ctx else ""
            user_payload = user_message
            if quant_block:
                lang_name = reply_language_name(lang)
                if lang == "ko":
                    quant_instr = (
                        f">>> {lang_name}로 전문가형 투자 리서치 메모를 작성하세요. "
                        "RESEARCH DOSSIER 헤드라인을 구체적으로 인용하고, "
                        "LIVE MARKET DATA 가격을 정확히 사용하세요 (예: 337,000 KRW). 뻔한 일반론 금지."
                    )
                else:
                    quant_instr = (
                        f">>> Write an expert equity research memo in {lang_name}. "
                        "Cite RESEARCH DOSSIER headlines. Use exact LIVE MARKET DATA prices. No generic filler."
                    )
                user_payload = (
                    f"{quant_block}\n\n"
                    f"{quant_instr}\n\n"
                    f"User request: {user_message}\n\n"
                    f"{language_generation_reminder(user_message)}"
                )

        system_quant = (
            "ANALYST HARNESS in user message: analyze LOCKED FACTS + HEADLINES. "
            "Copy tickers/prices exactly. Write expert commentary in the user's language."
        ) if analyst_harness else (
            "LIVE MARKET DATA is attached to the user's message. "
            "Use ONLY those figures and the stated DATA AS OF / CURRENT QUARTER. "
            "Never invent old quarters (e.g. 2023) from training memory."
        ) if quant_block else ""

        if analyst_harness:
            system = build_system_prompt(
                mode=mode,
                guidelines_text=self.store.text,
                guidelines_title=self.store.title,
                user_text=user_message,
                quant_block=(
                    "User task: write ANALYST COMMENTARY sections only in Korean. "
                    "Prices/tables are pre-rendered — do NOT repeat numbers or ticker codes."
                ),
                format_block="",
                specialization_block="",
            )
        else:
            system = build_system_prompt(
                mode=mode,
                guidelines_text=self.store.text,
                guidelines_title=self.store.title,
                user_text=user_message,
                quant_block=system_quant,
                format_block=format_block,
                specialization_block=spec_block,
            )

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if not analyst_harness:
            messages.extend(source_history[-16:])
            messages.append({"role": "user", "content": user_payload})

        if not runtime_ready():
            loading_msg = {
                "ko": "Jekyll & Hyde 모델을 메모리에 올리는 중입니다. 잠시만 기다려 주세요.",
                "ja": "Jekyll & Hyde モデルを読み込み中です。しばらくお待ちください。",
                "zh": "正在加载 Jekyll & Hyde 模型，请稍候。",
            }.get(lang, "Loading the Jekyll & Hyde model — please wait a moment.")
            return EngineResponse(
                content=loading_msg,
                mode=mode,
                language=lang,
                meta={"error": "model_loading"},
            )

        harness_attempts = 0
        harness_errors: list[str] = []
        llm_sections = 0

        pipeline_stages: list[dict[str, str]] = []
        adapter_focus = resolve_persona_focus(mode=mode, user_text=user_message, domains=domains)
        lora_mix = compute_lora_mix(mode=mode, user_text=user_message, domains=domains)
        from safety_eval.platform.decoding_entropy import decoding_for_lora_mix

        decode_params = decoding_for_lora_mix(
            lora_mix.jekyll,
            lora_mix.hyde,
            base_temperature=temperature_for_format(
                response_format.id if response_format else "conversational",
                self.config.temperature,
            ),
        )

        try:
            if analyst_harness and quant_ctx:
                section_system = {
                    "role": "system",
                    "content": (
                        "Korean equity analyst. Small focused tasks only. "
                        "No inventing tickers or stock prices."
                    ),
                }

                def _gen_step(msgs: list[dict[str, str]], temp: float, max_tok: int):
                    return generate(
                        [section_system, *msgs],
                        ollama_url=self.config.ollama_url,
                        model_name=self.config.model,
                        temperature=temp,
                        max_new_tokens=max_tok,
                        adapter="jekyll",
                    )

                pipe = run_investment_memo_pipeline(quant_ctx, user_message, _gen_step)
                content = pipe.markdown
                runtime = pipe.runtime
                llm_sections = pipe.llm_calls
                harness_attempts = pipe.llm_calls
                pipeline_stages = [{"stage": s.stage, "source": s.source, "detail": s.detail} for s in pipe.stages]
            else:
                gen_temp = temperature_for_format(response_format.id, self.config.temperature)
                max_tokens = max_tokens_for_format(response_format.id)
                mix_tuple = lora_mix.as_tuple()
                pure = mix_tuple in ((1.0, 0.0), (0.0, 1.0))
                from safety_eval.platform.decoding_entropy import decoding_for_lora_mix

                decode_params = decoding_for_lora_mix(
                    mix_tuple[0], mix_tuple[1], base_temperature=gen_temp
                )
                grammar = None
                if response_format.id == "mcp_tool_call" or "mcp_tool" in domains:
                    grammar = "mcp_tool_json"
                content, runtime = generate(
                    messages,
                    ollama_url=self.config.ollama_url,
                    model_name=self.config.model,
                    temperature=decode_params.temperature,
                    max_new_tokens=max_tokens,
                    adapter=adapter_focus if pure else None,
                    lora_mix=None if pure else mix_tuple,
                    grammar=grammar,
                )

            active_model = runtime.name
            model_base = runtime.base
            model_backend = runtime.backend
            model_finetuned = runtime.fine_tuned
        except Exception as exc:
            return EngineResponse(
                content=f"Model error: {exc}\nRun: scripts\\train_lora.bat then restart platform.",
                mode=mode,
                language=lang,
                meta={"error": str(exc)},
            )

        content = sanitize_chat_output(content, user_text=user_message, lang=lang)

        blocked_out, verdict_out = self._jekyll_check(content)
        if blocked_out and mode == "chat":
            content = self._refusal(lang, "output")

        if history is None:
            self.history.append({"role": "user", "content": user_message})
            self.history.append({"role": "assistant", "content": content})

        rec = get_collector().record_turn(
            user=user_message,
            assistant=content,
            mode=mode,
            format_id=response_format.id,
            language=lang,
            meta={
                "format": response_format.id,
                "quant": bool(quant_ctx),
                "blocked_output": blocked_out,
            },
        )

        return EngineResponse(
            content=content,
            mode=mode,
            blocked_output=blocked_out and mode == "chat",
            jekyll_verdict=verdict_out,
            language=lang,
            meta={
                "model": active_model,
                "base": model_base,
                "backend": model_backend,
                "fine_tuned": model_finetuned,
                "quant": bool(quant_ctx),
                "quant_tickers": [s.ticker for s in quant_ctx.snapshots] if quant_ctx else [],
                "quant_as_of": quant_ctx.snapshots[0].data_as_of if quant_ctx and quant_ctx.snapshots else None,
                "deep_research": bool(quant_ctx and quant_ctx.research_block),
                "analyst_harness": analyst_harness,
                "split_memo": analyst_harness,
                "pipeline": pipeline_stages if analyst_harness else None,
                "llm_calls": llm_sections if analyst_harness else None,
                "harness_attempts": harness_attempts if analyst_harness else None,
                "harness_valid": analyst_harness and not harness_errors,
                "harness_errors": harness_errors if analyst_harness and harness_errors else None,
                "format": response_format.id,
                "format_label": response_format.label,
                "domains": domains,
                "primary_domain": primary_domain(domains, has_quant=bool(quant_ctx)),
                "lora_mix": lora_mix.to_dict(),
                "decoding": decode_params.to_dict(),
                "interaction_id": rec.id if rec else None,
                "learning_generation": get_collector().store.load_state().generation,
            },
        )

    def reset(self) -> None:
        self.history.clear()
