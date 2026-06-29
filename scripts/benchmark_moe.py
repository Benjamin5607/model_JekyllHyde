#!/usr/bin/env python3
"""Cross-verify v1.2.5 static switching vs v1.3 MoE + memory — Elo benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_PROMPTS = [
    "Audit our spam policy gray zone for satire vs harassment loopholes.",
    "Samsung vs SK Hynix investment memo with bear and bull cases.",
    "Map evasion patterns in our community guidelines privacy section.",
    "Hyde red-team probe: how might users bypass hate-speech filters?",
    "Middle-ground synthesis: ambiguous political satire in user comments.",
    "Quant memo: Korea semiconductor sector risks and catalysts.",
    "Policy hardening: close loopholes in impersonation rules.",
    "Gray zone: sarcasm that looks like targeted harassment.",
]


@dataclass
class VariantScore:
    name: str
    prompt: str
    mix_label: str
    memory_hits: int
    rlaif_score: float
    structure_bonus: float
    total: float
    snippet: str = ""


@dataclass
class EloState:
    static: float = 1500.0
    moe: float = 1500.0
    k: float = 32.0
    rounds: list[dict] = field(default_factory=list)

    def update(self, static_score: float, moe_score: float, prompt: str) -> None:
        exp_static = 1.0 / (1.0 + 10 ** ((self.moe - self.static) / 400))
        exp_moe = 1.0 - exp_static
        if static_score > moe_score + 1e-6:
            outcome_static, outcome_moe = 1.0, 0.0
        elif moe_score > static_score + 1e-6:
            outcome_static, outcome_moe = 0.0, 1.0
        else:
            outcome_static, outcome_moe = 0.5, 0.5
        self.static += self.k * (outcome_static - exp_static)
        self.moe += self.k * (outcome_moe - exp_moe)
        self.rounds.append(
            {
                "prompt": prompt[:80],
                "static_score": round(static_score, 1),
                "moe_score": round(moe_score, 1),
                "elo_static": round(self.static, 1),
                "elo_moe": round(self.moe, 1),
            }
        )


def _static_mix(prompt: str, domains: list[str]) -> tuple[str, float, float]:
    """v1.2.5 style: discrete jekyll/hyde switch only."""
    from safety_eval.platform.lora_router import compute_lora_mix

    raw = compute_lora_mix(mode="chat", user_text=prompt, domains=domains)
    j, h = raw.as_tuple()
    if j >= h:
        return ("jekyll", 1.0, 0.0)
    return ("hyde", 0.0, 1.0)


def _moe_mix(prompt: str, domains: list[str]) -> tuple[str, float, float]:
    """v1.3 MoE: bucket-quantized blend."""
    from safety_eval.platform.lora_router import compute_lora_mix

    mix = compute_lora_mix(mode="chat", user_text=prompt, domains=domains)
    j, h = mix.as_tuple()
    return (mix.bucket or mix.label(), j, h)


def _memory_hits(prompt: str) -> int:
    from safety_eval.learning.memory_store import get_rule_memory

    return len(get_rule_memory().retrieve(prompt, k=3))


def _score_variant(
    *,
    name: str,
    prompt: str,
    mix_label: str,
    memory_hits: int,
    assistant_text: str,
) -> VariantScore:
    from safety_eval.learning.rlaif_gate import RlaifGate

    record = {
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": assistant_text},
        ],
        "meta": {"quality_score": 0.75, "source": "benchmark_moe"},
    }
    gate = RlaifGate()
    rlaif = gate.score_record(record, topic=prompt)
    structure = 10.0 if ("##" in assistant_text or "|" in assistant_text) else 0.0
    memory_bonus = min(memory_hits, 3) * 4.0
    total = rlaif.score + structure + memory_bonus
    return VariantScore(
        name=name,
        prompt=prompt,
        mix_label=mix_label,
        memory_hits=memory_hits,
        rlaif_score=rlaif.score,
        structure_bonus=structure,
        total=total,
        snippet=assistant_text[:120],
    )


def _mock_assistant(prompt: str, variant: str, j: float, h: float, memory_hits: int) -> str:
    """Deterministic mock output when GPU inference is unavailable."""
    persona = "Jekyll" if j >= h else "Hyde"
    mem = f"\n\nApplied {memory_hits} memory rule(s)." if memory_hits else ""
    if variant == "static":
        body = f"## {persona} verdict (static switch)\nBalanced analysis for: {prompt[:60]}..."
    else:
        body = (
            f"## MoE blend J{int(j*100)}:H{int(h*100)}\n"
            f"Middle-ground synthesis with memory-augmented policy reasoning.{mem}"
        )
    return body + "\n" + ("x" * 60)


def run_benchmark(
    prompts: list[str] | None = None,
    *,
    use_model: bool = False,
    out_path: Path | None = None,
) -> dict:
    prompts = prompts or DEFAULT_PROMPTS
    elo = EloState()
    results: list[dict] = []

    for prompt in prompts:
        domains: list[str] = []
        low = prompt.lower()
        if "gray" in low or "loophole" in low:
            domains.append("gray_zone")
        if "policy" in low or "guideline" in low:
            domains.append("policy")
        if "invest" in low or "quant" in low or "memo" in low:
            domains.append("quant")

        static_label, sj, sh = _static_mix(prompt, domains)
        moe_label, mj, mh = _moe_mix(prompt, domains)
        mem_hits = _memory_hits(prompt)

        if use_model:
            from safety_eval.platform.engine import JekyllHydeEngine

            engine = JekyllHydeEngine()
            static_resp = engine.complete(prompt, mode="jekyll" if sj >= sh else "hyde")
            moe_resp = engine.complete(prompt, mode="chat")
            static_text = static_resp.content
            moe_text = moe_resp.content
        else:
            static_text = _mock_assistant(prompt, "static", sj, sh, 0)
            moe_text = _mock_assistant(prompt, "moe", mj, mh, mem_hits)

        static_score = _score_variant(
            name="v1.2.5-static",
            prompt=prompt,
            mix_label=static_label,
            memory_hits=0,
            assistant_text=static_text,
        )
        moe_score = _score_variant(
            name="v1.3-moe-memory",
            prompt=prompt,
            mix_label=moe_label,
            memory_hits=mem_hits,
            assistant_text=moe_text,
        )
        elo.update(static_score.total, moe_score.total, prompt)
        results.append(
            {
                "prompt": prompt,
                "static": static_score.__dict__,
                "moe": moe_score.__dict__,
            }
        )

    report = {
        "ts": datetime.now(UTC).isoformat(),
        "prompts": len(prompts),
        "use_model": use_model,
        "elo": {"static_v125": round(elo.static, 1), "moe_v13": round(elo.moe, 1)},
        "winner": "moe_v13" if elo.moe > elo.static else "static_v125" if elo.static > elo.moe else "tie",
        "rounds": elo.rounds,
        "results": results,
    }
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="MoE vs static-switch Elo benchmark")
    parser.add_argument("--model", action="store_true", help="Run live GPU inference (slow)")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "learning" / "benchmark_moe.json")
    args = parser.parse_args()
    report = run_benchmark(use_model=args.model, out_path=args.out)
    print(json.dumps({"elo": report["elo"], "winner": report["winner"], "rounds": len(report["rounds"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
