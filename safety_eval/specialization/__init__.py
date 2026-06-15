"""Domain specialization — quant, policy, gray-zone, hardening."""

from safety_eval.specialization.domains import (
    build_specialization_block,
    detect_domains,
    primary_domain,
)

__all__ = [
    "build_specialization_block",
    "detect_domains",
    "primary_domain",
]
