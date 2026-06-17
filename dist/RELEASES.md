# Release download record

| Version | Date | Assets | Notes |
|---------|------|--------|-------|
| **1.2.1** | 2026-06-16 | `app.zip` + `model.part00–02.gz` | Structure cleanup, dist auto-prune, dead code removed |
| **1.2.0** | 2026-06-15 | `app.zip` + `model.part00–02.gz` | Duel middle-ground synthesis |
| **1.1.0** | 2026-06-15 | `app.zip` + `model.part00–02.gz` | 5-stage investment memo pipeline |
| **1.0.0** | 2026-06-14 | `app.zip` + `model.part00–02.gz` | Initial release |

Build: `scripts\build_release.ps1` · Cleanup: `python -m safety_eval.storage.optimizer` · Verify: `python scripts\verify_today.py`
