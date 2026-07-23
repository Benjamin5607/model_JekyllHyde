"""Attack DNA — compact genome for tool sequences (GA-friendly)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


# Canonical alphabet for attack genomes
DNA_MAP: dict[str, str] = {
    "email": "E",
    "email.read": "E",
    "email.send": "M",  # Mail out
    "web": "W",
    "web.open": "W",
    "web.search": "S",
    "fs.read": "R",
    "read": "R",
    "file": "R",
    "fs.write": "T",  # sTore / write
    "write": "T",
    "fs.delete": "D",
    "delete": "D",
    "http.post": "H",
    "post": "H",
    "upload": "H",
    "shell.run": "X",
    "shell": "X",
    "run": "X",
    "execute": "X",
    "memory": "Y",
    "search_memory": "Y",
    "plan": "P",
    "planner": "P",
    "vault": "V",
    "secret": "V",
}


def _token_code(token: str) -> str:
    t = token.lower().strip()
    if t in DNA_MAP:
        return DNA_MAP[t]
    # user-message heuristics
    if "email" in t and "send" in t:
        return "M"
    if "email" in t or "read email" in t:
        return "E"
    if "open" in t or "page_" in t:
        return "W"
    if "search" in t:
        return "S"
    if "read file" in t or "read secret" in t:
        return "R"
    if "write" in t or "save" in t:
        return "T"
    if "delete" in t:
        return "D"
    if "post" in t or "upload" in t:
        return "H"
    if "shell" in t or "run " in t or "execute" in t:
        return "X"
    if "continue" in t or "follow" in t or "proceed" in t:
        return "P"
    # fallback: first letter of last path segment
    bare = re.sub(r"[^a-z0-9]+", "", t.split()[-1] if t.split() else t) or "Z"
    return bare[0].upper()


@dataclass(frozen=True)
class AttackDNA:
    """Genome string e.g. 'ERPH' = Email → Read → Plan → HTTP."""

    genome: str
    sequence: tuple[str, ...] = ()

    @classmethod
    def from_sequence(cls, sequence: Sequence[str]) -> "AttackDNA":
        codes = [_token_code(s) for s in sequence]
        # collapse consecutive duplicates (A→A→A == A) for clustering
        collapsed: list[str] = []
        for c in codes:
            if not collapsed or collapsed[-1] != c:
                collapsed.append(c)
        return cls(genome="".join(collapsed) or "Z", sequence=tuple(sequence))

    def distance(self, other: "AttackDNA") -> float:
        """Normalized Levenshtein distance in [0,1]."""
        a, b = self.genome, other.genome
        if a == b:
            return 0.0
        if not a or not b:
            return 1.0
        n, m = len(a), len(b)
        dp = list(range(m + 1))
        for i in range(1, n + 1):
            prev, dp[0] = dp[0], i
            for j in range(1, m + 1):
                cur = dp[j]
                if a[i - 1] == b[j - 1]:
                    dp[j] = prev
                else:
                    dp[j] = 1 + min(prev, dp[j], dp[j - 1])
                prev = cur
        return dp[m] / max(n, m)

    def to_dict(self) -> dict:
        return {"genome": self.genome, "sequence": list(self.sequence)}

    def crossover(self, other: "AttackDNA", *, cut: int | None = None) -> "AttackDNA":
        """AB CDE + KL MNO → AB MNO (string genome crossover)."""
        a, b = self.genome, other.genome
        if not a:
            return AttackDNA(genome=b, sequence=other.sequence)
        if not b:
            return AttackDNA(genome=a, sequence=self.sequence)
        k = cut if cut is not None else max(1, min(len(a), len(b)) // 2)
        k = max(1, min(k, len(a), len(b)))
        child = a[:k] + b[k:]
        # rebuild sequence by concatenating prefixes
        seq = list(self.sequence[:k]) + list(other.sequence[k:])
        if not seq:
            seq = list(self.sequence or other.sequence)
        return AttackDNA(genome=child or "Z", sequence=tuple(seq[:8]))

    def point_mutate(self, alphabet: str = "EWRSDHXTMPVY", *, rng=None) -> "AttackDNA":
        import random as _r

        r = rng or _r
        g = list(self.genome or "Z")
        i = r.randrange(len(g))
        choices = [c for c in alphabet if c != g[i]] or list(alphabet)
        g[i] = r.choice(choices)
        return AttackDNA(genome="".join(g), sequence=self.sequence)
