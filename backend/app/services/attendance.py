from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CategoryRule:
    category: str
    fill_factor: float
    fallback_attendance: int


DEFAULT_FALLBACK = 100


def estimate_expected_attendance(
    category: str,
    venue_capacity: Optional[int],
    rules_map: dict[str, dict],
) -> int:
    rule_data = rules_map.get(category.lower()) if category else None
    if not rule_data:
        return max(venue_capacity or DEFAULT_FALLBACK, 1)
    rule = CategoryRule(
        category=rule_data["category"],
        fill_factor=float(rule_data["fill_factor"]),
        fallback_attendance=int(rule_data["fallback_attendance"]),
    )
    if venue_capacity:
        estimated = int(round(venue_capacity * rule.fill_factor))
        return max(estimated, 1)
    return max(rule.fallback_attendance, 1)
