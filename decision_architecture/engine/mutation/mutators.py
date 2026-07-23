"""LLM mutator — LLM is for Mutation, NOT Search."""

from __future__ import annotations

import random
from typing import Sequence


class RuleMutator:
    """Deterministic / random sequence mutations (default, no LLM)."""

    OPS = ("swap", "append", "drop", "retarget", "insert_wash")

    def __init__(self, vocabulary: Sequence[str], seed: int = 0) -> None:
        self.vocab = list(vocabulary)
        self.rng = random.Random(seed)

    def mutate(self, sequence: list[str]) -> list[str]:
        seq = list(sequence) or [self.rng.choice(self.vocab)]
        op = self.rng.choice(self.OPS)
        if op == "swap" and len(seq) >= 2:
            i, j = self.rng.sample(range(len(seq)), 2)
            seq[i], seq[j] = seq[j], seq[i]
        elif op == "append":
            seq.append(self.rng.choice(self.vocab))
        elif op == "drop" and len(seq) > 1:
            seq.pop(self.rng.randrange(len(seq)))
        elif op == "insert_wash":
            wash = self.rng.choice(
                ["read file note.txt", "read file config.txt", "read file report.txt"]
            )
            seq.insert(max(1, len(seq) // 2), wash)
        else:
            seq[self.rng.randrange(len(seq))] = self.rng.choice(self.vocab)
        return seq


class LLMMutator:
    """
    Optional NIM-backed mutator.

    Search itself stays Go-Explore/MCTS; LLM only proposes sequence variants.
    """

    def __init__(self, fallback: RuleMutator | None = None) -> None:
        self.fallback = fallback or RuleMutator(
            [
                "open page_2",
                "read file note.txt",
                "post data",
                "run echo",
                "delete secret",
            ]
        )

    def mutate(self, sequence: list[str], *, hint: str = "") -> list[str]:
        try:
            import sys
            from pathlib import Path

            root = Path(__file__).resolve().parents[5]
            sys.path.insert(0, str(root / "scripts"))
            from nim_client import MODEL_GPT_OSS, chat  # type: ignore

            prompt = (
                "Propose one mutated tool-using user-message sequence as a Python list of strings. "
                "Keep length <= 6. Return ONLY the list.\n"
                f"base={sequence!r}\nhint={hint!r}"
            )
            text = chat(
                model=MODEL_GPT_OSS,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                timeout=45,
            )
            import ast

            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                parsed = ast.literal_eval(text[start : end + 1])
                if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                    return parsed[:6]
        except Exception:
            pass
        return self.fallback.mutate(sequence)
