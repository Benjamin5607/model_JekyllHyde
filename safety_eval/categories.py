"""Content moderation category taxonomy."""

CATEGORIES: dict[str, str] = {
    "violence": "Physical harm, weapons, or instructions to injure",
    "self_harm": "Suicide, self-injury, or eating disorders",
    "sexual": "Explicit sexual content or CSAM-related requests",
    "hate": "Slurs, dehumanization, or targeted harassment",
    "illegal": "Crime instructions, fraud, or illicit trade",
    "privacy": "Doxxing, stalking, or unauthorized access",
    "misinformation": "Deliberate false claims presented as fact",
    "manipulation": "Social engineering, scams, or coercion",
    "benign": "Safe content that should not be blocked",
    "edge_case": "Borderline content requiring nuanced judgment",
}

EVASION_TAGS = frozenset(
    {
        "euphemism",
        "obfuscation",
        "roleplay_wrap",
        "translation",
        "hypothetical",
        "encoding",
        "multi_turn_hint",
    }
)

FALSE_POSITIVE_TAGS = frozenset(
    {
        "fiction",
        "education",
        "news",
        "medical",
        "security_research",
        "historical",
    }
)
