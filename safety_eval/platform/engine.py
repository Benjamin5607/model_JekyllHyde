"""Jekyll & Hyde LLM engine — the model runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from safety_eval.blue_team import build_blue_team
from safety_eval.i18n.apac import detect_user_language
from safety_eval.platform.ollama_client import MODEL_NAME
from safety_eval.platform.runtime import describe_runtime, generate, runtime_ready
from safety_eval.platform.duel import run_duel
from safety_eval.platform.formats import build_format_block, format_refusal, temperature_for_format
from safety_eval.platform.persona import build_system_prompt
from safety_eval.quant.analyzer import build_quant_context, compare_snapshots
from safety_eval.store import GuidelinesStore, get_guidelines_store
from safety_eval.learning.collector import get_collector

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
            topic += "\n" + quant_ctx.to_prompt_block(mode="duel")

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
                meta={"duel": True, "verdict": result.verdict},
            )

            return EngineResponse(
                content=transcript,
                mode="duel",
                language=lang,
                meta={
                    "model": runtime.name,
                    "backend": runtime.backend,
                    "fine_tuned": runtime.fine_tuned,
                    "duel": result.to_dict(),
                    "verdict": result.verdict,
                    "summary": result.summary,
                    "verification": result.verification,
                    "interaction_id": rec.id if rec else None,
                },
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

        quant_ctx = build_quant_context(user_message, mode=mode)
        quant_block = quant_ctx.to_prompt_block(mode=mode) if quant_ctx else ""
        has_comparison = bool(quant_ctx and len(quant_ctx.snapshots) >= 2)
        if has_comparison:
            quant_block += "\n" + compare_snapshots(quant_ctx.snapshots)

        format_block, response_format = build_format_block(
            user_message,
            mode=mode,
            has_quant=bool(quant_ctx),
            has_comparison=has_comparison,
            guideline_enforcement=self.store.has_mcp_guidelines(),
        )

        system = build_system_prompt(
            mode=mode,
            guidelines_text=self.store.text,
            guidelines_title=self.store.title,
            user_text=user_message,
            quant_block=quant_block,
            format_block=format_block,
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        source_history = history if history is not None else self.history
        messages.extend(source_history[-16:])
        messages.append({"role": "user", "content": user_message})

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

        try:
            gen_temp = temperature_for_format(response_format.id, self.config.temperature)
            content, runtime = generate(
                messages,
                ollama_url=self.config.ollama_url,
                model_name=self.config.model,
                temperature=gen_temp,
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
                "format": response_format.id,
                "format_label": response_format.label,
                "interaction_id": rec.id if rec else None,
                "learning_generation": get_collector().store.load_state().generation,
            },
        )

    def reset(self) -> None:
        self.history.clear()
