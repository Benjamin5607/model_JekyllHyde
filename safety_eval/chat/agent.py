"""Chat agent orchestrating Jekyll, Hyde, and APAC multilingual LLM."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from safety_eval.arena import run_arena
from safety_eval.blue_team import build_blue_team
from safety_eval.evolution import run_evolution
from safety_eval.i18n.apac import APAC_LANGUAGE_POLICY, apac_system_suffix, detect_apac_language
from safety_eval.red_team import build_red_team
from safety_eval.store import GuidelinesStore, get_guidelines_store

CHAT_SYSTEM = """You are the Jekyll & Hyde assistant — one interface for two co-evolving roles:

- Jekyll (defense): enforces community guidelines, flags gray zones, blocks violations.
- Hyde (attack): tests guidelines via evasion and borderline content (authorized testing only).

Help the user configure guidelines, run duel/evolution sessions, and explain results.
Never provide operational instructions for real-world harm. Testing probes only.

{apac_policy}
"""


@dataclass
class ChatMessage:
    role: str
    content: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatSettings:
    llm_url: str = "http://localhost:11434"
    model: str = "llama3.2"
    api_key: str | None = None
    jekyll_backend: str = "keyword"
    hyde_backend: str = "guideline"
    rounds: int = 2
    attacks_per_round: int = 8


class ChatAgent:
    def __init__(self, store: GuidelinesStore | None = None, settings: ChatSettings | None = None):
        self.store = store or get_guidelines_store()
        self.settings = settings or ChatSettings()
        self.history: list[ChatMessage] = []

    def _system_prompt(self, user_text: str = "") -> str:
        guidelines = self.store.text[:4000]
        apac = apac_system_suffix(user_text)
        return (
            CHAT_SYSTEM.format(apac_policy=APAC_LANGUAGE_POLICY)
            + apac
            + f"\n\nActive guidelines ({self.store.title}):\n{guidelines}\n"
        )

    def _ollama_chat(self, user_text: str) -> str:
        url = self.settings.llm_url.rstrip("/")
        endpoint = f"{url}/api/chat"
        messages = [{"role": "system", "content": self._system_prompt(user_text)}]
        for msg in self.history[-12:]:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_text})

        payload = {"model": self.settings.model, "messages": messages, "stream": False}
        with httpx.Client(timeout=120.0) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
        return data.get("message", {}).get("content", str(data))

    def _openai_chat(self, user_text: str) -> str:
        url = self.settings.llm_url.rstrip("/")
        endpoint = url if url.endswith("/chat/completions") else f"{url}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        messages = [{"role": "system", "content": self._system_prompt(user_text)}]
        for msg in self.history[-12:]:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_text})

        payload = {"model": self.settings.model, "messages": messages, "temperature": 0.7}
        with httpx.Client(timeout=120.0) as client:
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]

    def _llm_reply(self, user_text: str) -> str:
        if "11434" in self.settings.llm_url or "/api/chat" in self.settings.llm_url:
            return self._ollama_chat(user_text)
        return self._openai_chat(user_text)

    def _run_evolution_summary(self) -> str:
        path = self.store.active_path()
        apac_probes = path.parent / "guideline_probes_apac.yaml"
        probes = [path.parent / "guideline_probes.yaml"]
        if apac_probes.exists():
            probes.append(apac_probes)

        hyde = build_red_team(
            self.settings.hyde_backend,
            guidelines=path,
            probes_path=probes[0],
            seed=42,
        )
        # Merge APAC probes by loading combined - simpler: pass apac as extra via guideline update
        jekyll = build_blue_team(self.settings.jekyll_backend, guidelines_path=path, rules_path=path.parent / "keyword_rules.yaml")

        session = run_evolution(
            hyde,
            jekyll,
            guidelines_title=self.store.title,
            rounds=self.settings.rounds,
            count_per_round=self.settings.attacks_per_round,
            attack_modes=["evasion", "gray_zone"],
        )

        trend = " -> ".join(f"{r:.0%}" for r in session.catch_rate_trend())
        lang = detect_apac_language(self.store.text) or "multi"
        return (
            f"Evolution complete ({lang} APAC-aware).\n"
            f"Rounds: {len(session.rounds)} | Jekyll catch trend: {trend}\n"
            f"Final catch rate: {session.final_catch_rate:.0%}\n"
            f"Hyde escapes remembered: {len(session.hyde_memory.bypasses)}\n"
            f"Jekyll patterns learned: {len(session.jekyll_memory.learned_patterns)}"
        )

    def _jekyll_check(self, text: str) -> str:
        path = self.store.active_path()
        jekyll = build_blue_team(
            self.settings.jekyll_backend,
            guidelines_path=path,
            rules_path=path.parent / "keyword_rules.yaml",
        )
        result = jekyll.classify(text)
        lang = detect_apac_language(text) or "unknown"
        status = "BLOCKED" if result.blocked else ("FLAGGED" if result.flagged else "ALLOWED")
        return (
            f"Jekyll verdict: {status}\n"
            f"Language hint: {lang}\n"
            f"Score: {result.score}\n"
            f"Categories: {', '.join(result.categories) or '-'}"
        )

    def _hyde_sample(self) -> str:
        path = self.store.active_path()
        hyde = build_red_team(
            "guideline",
            guidelines=path,
            seed=7,
        )
        prompts = hyde.generate(count=3, attack_modes=["evasion", "gray_zone"])
        lines = ["Hyde sample probes (APAC, testing only):"]
        for item in prompts:
            lines.append(f"- [{item.attack_mode.value}|{item.guideline_section}] {item.prompt}")
        return "\n".join(lines)

    def _handle_command(self, text: str) -> str | None:
        stripped = text.strip()
        if not stripped.startswith("/"):
            return None

        parts = stripped.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/help", "/도움"):
            return (
                "Commands:\n"
                "/guidelines <text> — set guidelines (or use MCP)\n"
                "/run — evolution duel (Hyde vs Jekyll)\n"
                "/hyde — sample APAC Hyde probes\n"
                "/jekyll <text> — classify a message\n"
                "/lang — show APAC language support\n"
                "/help — this message"
            )
        if cmd == "/lang":
            from safety_eval.i18n.apac import APAC_LANGUAGES

            return "APAC languages: " + ", ".join(APAC_LANGUAGES.values())
        if cmd == "/guidelines":
            if not arg:
                preview = self.store.text[:1200]
                return f"Current guidelines ({self.store.title}):\n\n{preview}"
            self.store.set_text(arg, title="Chat Guidelines", source="chat")
            return f"Guidelines updated ({len(arg)} chars)."
        if cmd == "/run":
            return self._run_evolution_summary()
        if cmd == "/hyde":
            return self._hyde_sample()
        if cmd == "/jekyll":
            if not arg:
                return "Usage: /jekyll <message to classify>"
            return self._jekyll_check(arg)

        return f"Unknown command: {cmd}. Try /help"

    def chat(self, user_text: str) -> ChatMessage:
        self.history.append(ChatMessage(role="user", content=user_text))

        command_reply = self._handle_command(user_text)
        if command_reply is not None:
            reply = ChatMessage(role="assistant", content=command_reply, meta={"mode": "command"})
            self.history.append(reply)
            return reply

        try:
            content = self._llm_reply(user_text)
            meta = {"mode": "llm", "lang": detect_apac_language(user_text)}
        except Exception as exc:
            content = (
                f"LLM unavailable ({exc}). Use slash commands: /help /run /hyde /jekyll /guidelines\n\n"
                + (self._handle_command("/help") or "")
            )
            meta = {"mode": "fallback", "error": str(exc)}

        reply = ChatMessage(role="assistant", content=content, meta=meta)
        self.history.append(reply)
        return reply
