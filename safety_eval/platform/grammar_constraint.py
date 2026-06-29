"""Grammar-constrained decoding for MCP tool-call JSON output."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

# Simplified MCP tool JSON schema prefix
MCP_JSON_PREFIX = '```json\n{"tool_calls": ['


def _strip_fence(text: str) -> str:
    t = text
    if "```json" in t:
        t = t.split("```json", 1)[-1]
    if "```" in t:
        t = t.split("```", 1)[0]
    return t.strip()


def validate_mcp_tool_json(text: str) -> bool:
    """Return True if text parses as valid MCP tool_calls JSON."""
    raw = _strip_fence(text)
    if not raw.startswith("{"):
        return False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    calls = data.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return False
    for call in calls:
        if not isinstance(call, dict):
            return False
        if not isinstance(call.get("name"), str):
            return False
        if "arguments" not in call or not isinstance(call["arguments"], dict):
            return False
    return True


def _next_allowed_chars(partial: str) -> set[str]:
    """Character-level FSM for MCP tool_calls JSON (after optional fence)."""
    if not partial:
        return set("`")

    if partial == "`":
        return {"`"}
    if partial == "``":
        return {"`"}
    if partial == "```":
        return {"j", "J"}
    if partial.lower().startswith("```json"):
        rest = partial.lower()
        target = "```json"
        if len(rest) < len(target):
            return {target[len(rest)]}
        after = partial[len("```json") :]
        if not after:
            return {"\n", " "}
        if after in ("\n", "\n "):
            return {"{"}
        if "{" in after and '"tool_calls"' not in after:
            if after.endswith("{"):
                return {'"'}
            if after.endswith('{"'):
                return set("tool_calls")
            if '{"tool_calls"' in after and ":" not in after.split("tool_calls")[-1]:
                return {":", " "}
            if re.search(r'\{"tool_calls"\s*:\s*$', after):
                return {"["}
            if re.search(r'\{"tool_calls"\s*:\s*\[\s*$', after):
                return {"{", "]"}
            if re.search(r'\{"tool_calls"\s*:\s*\[\s*\{\s*$', after):
                return {'"'}
            if re.search(r'"name"\s*:\s*"[^"]*"\s*,\s*$', after):
                return {'"'}
            if re.search(r'"arguments"\s*:\s*\{\s*$', after):
                return {'"', "}"}
            if re.search(r'\}\s*\]\s*\}\s*$', after):
                return set()
            return set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_":, {}[]\n\t')

    return set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_":, {}[]\n\t`')


def build_mcp_tool_prefix_fn(tokenizer: Any) -> Callable[[int, list[int]], list[int]]:
    """
    prefix_allowed_tokens_fn for transformers.generate — masks invalid JSON tokens.
    """
    vocab_size = len(tokenizer)
    special_ids = set(getattr(tokenizer, "all_special_ids", []) or [])

    def _allowed_token_ids(partial_text: str) -> list[int]:
        allowed_chars = _next_allowed_chars(partial_text)
        if not allowed_chars:
            return [tokenizer.eos_token_id] if tokenizer.eos_token_id is not None else [0]

        ids: set[int] = set()
        for tid in range(vocab_size):
            if tid in special_ids:
                continue
            piece = tokenizer.decode([tid], skip_special_tokens=False)
            if not piece:
                continue
            if all(ch in allowed_chars for ch in piece):
                ids.add(tid)
        if not ids:
            return list(range(min(256, vocab_size)))
        return list(ids)

    def prefix_allowed_tokens_fn(batch_id: int, input_ids: list[int]) -> list[int]:
        partial = tokenizer.decode(input_ids, skip_special_tokens=True)
        return _allowed_token_ids(partial)

    return prefix_allowed_tokens_fn


def mcp_tool_grammar_processor(tokenizer: Any) -> Any | None:
    """Optional LogitsProcessor wrapper when prefix_fn is unavailable."""
    try:
        from transformers import LogitsProcessor
    except ImportError:
        return None

    prefix_fn = build_mcp_tool_prefix_fn(tokenizer)

    class McpJsonLogitsProcessor(LogitsProcessor):
        def __call__(self, input_ids, scores):
            import torch

            allowed = prefix_fn(0, input_ids[0].tolist())
            mask = torch.full_like(scores, float("-inf"))
            for tid in allowed:
                if 0 <= tid < scores.shape[-1]:
                    mask[0, tid] = scores[0, tid]
            return mask

    return McpJsonLogitsProcessor()
