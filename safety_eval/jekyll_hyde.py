"""Jekyll & Hyde — public names and aliases."""

HYDE = "Hyde"
JEKYLL = "Jekyll"
TAGLINE = "Good and evil co-evolve — Hyde escapes, Jekyll learns"
TAGLINE_KO = "선과 악이 공존하며, 서로를 키워가는 가이드라인 방어 실험"

# Backward-compatible aliases
HydePrompt = None  # set after import to avoid circular deps


def _bind_aliases() -> None:
    global HydePrompt
    from safety_eval.red_team.base import RedTeamPrompt

    HydePrompt = RedTeamPrompt


_bind_aliases()
