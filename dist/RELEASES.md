# Release download record

| Version | Date | Assets | Notes |
|---------|------|--------|-------|
| **1.7.0** | 2026-07-11 | `app.zip` + `model.part00–02.gz` | Workforce mesh graph, manager back-off, critic-free local GRPO (RLAIF reward) |
| **1.6.0** | 2026-07-10 | `app.zip` + `model.part00–02.gz` | Gemma 3 4B default, privacy/DP-SGD, MCP mesh, SigLIP vision, iterative RLAIF DPO |
| **1.5.0** | 2026-06-13 | `app.zip` + `model.part00–02.gz` | Dynamic decoding, DPO alignment, grammar MCP JSON |
| **1.4.0** | 2026-06-13 | `app.zip` + `model.part00–02.gz` | Manager-Worker MCP workforce |
| **1.3.1** | 2026-06-13 | `app.zip` + `model.part00–02.gz` | MoE bucket cache, blend UI, RLAIF dashboard, memory consolidation, Elo benchmark |
| **1.3.0** | 2026-06-28 | `app.zip` + `model.part00–02.gz` | LoRA MoE, RLAIF gate, rule memory RAG, MCP tools |
| **1.2.5** | 2026-06-28 | `app.zip` + `model.part00–02.gz` | Gray-zone duel reinforcement loop |
| **1.2.4** | 2026-06-13 | `app.zip` + `model.part00–02.gz` | Ultra-lightweight loop, English-default UI i18n |
| **1.2.3** | 2026-06-28 | `app.zip` + `model.part00–02.gz` | Dual LoRA, auto GGUF, persona routing |
| **1.2.2** | 2026-06-17 | `app.zip` + `model.part00–02.gz` | Data diet, semantic dedup, slim routing |
| **1.2.1** | 2026-06-16 | `app.zip` + `model.part00–02.gz` | Structure cleanup, dist auto-prune |
| **1.2.0** | 2026-06-15 | `app.zip` + `model.part00–02.gz` | Duel middle-ground synthesis |
| **1.1.0** | 2026-06-15 | `app.zip` + `model.part00–02.gz` | 5-stage investment memo pipeline |
| **1.0.0** | 2026-06-14 | `app.zip` + `model.part00–02.gz` | Initial release |

Build: `scripts\build_release.ps1` · Diet: `python scripts\data_diet.py` · Verify: `python scripts\verify_today.py`
