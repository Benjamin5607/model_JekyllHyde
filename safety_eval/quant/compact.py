"""Compact quant context for LLM prompts (token savings)."""

from __future__ import annotations

from safety_eval.quant.analyzer import QuantContext
from safety_eval.quant.formatting import fmt_krw_price, ko_display_name
from safety_eval.quant.market import analysis_anchor


def compact_quant_digest(ctx: QuantContext, *, max_headlines: int = 3) -> str:
    """Numbers + short headline titles only — no full research dossier."""
    anchor = analysis_anchor()
    lines = [
        f"DATA AS OF {anchor['date']} | QTR {anchor['quarter']}",
    ]
    for s in ctx.snapshots[:4]:
        if s.price is None and not s.fundamentals.quarterly_rows:
            continue
        name = ko_display_name(s.ticker, s.name)
        chg = f"{s.change_pct:+.1f}%" if s.change_pct is not None else "N/A"
        q = ""
        if s.fundamentals.quarterly_rows:
            r = s.fundamentals.quarterly_rows[0]
            q = f" | latest Q rev trend"
        lines.append(
            f"{name}({s.ticker}): {fmt_krw_price(s.price)} {chg} "
            f"PER={s.fundamentals.per} PBR={s.fundamentals.pbr}{q}"
        )
    n = 0
    for d in ctx.dossiers:
        for h in d.hits[:max_headlines]:
            if n >= max_headlines:
                break
            lines.append(f"H{n + 1}: [{h.date}] {h.title[:120]}")
            n += 1
    lines.append("Use exact prices above. Not financial advice.")
    return "\n".join(lines)
