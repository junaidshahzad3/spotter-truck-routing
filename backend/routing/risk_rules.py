"""Risk thresholds from the assessment brief: the ONE place the classification table lives.

Brief, "Risk Rules":

| Condition | Low        | Moderate  | High      | Severe    | No Travel |
|-----------|------------|-----------|-----------|-----------|-----------|
| Wind      | <25 mph    | 25-34     | 35-44     | 45-54     | >=55 mph  |
| Rain      | <0.10 in/h | 0.10-0.25 | 0.25-0.50 | 0.50-1.00 | >1.00     |
| Snow      | <0.5 in/h  | 0.5-1.0   | 1.0-2.0   | 2.0-3.0   | >3.0      |

Load rules:
  * >=55 mph -> No Travel for any load
  * 45-54 mph + >30,000 lb -> No Travel
  * 35-44 mph + >40,000 lb -> Severe

Band edges: each band includes its lower bound ("0.10-0.25" then "0.25-0.50" means
0.25 is High). The No Travel edges for rain and snow are strict (">1.00", ">3.0"), so
exactly 1.00 in/h of rain is Severe, while wind uses ">=55".

Wind means the sustained 10 m wind speed. Gusts are shown in the UI but not scored,
because the brief's table doesn't mention them.
"""

from __future__ import annotations

from dataclasses import dataclass

LEVELS: tuple[str, ...] = ("low", "moderate", "high", "severe", "no_travel")
SCORES: dict[str, int] = {level: i for i, level in enumerate(LEVELS)}
LABELS: dict[str, str] = {
    "low": "Low",
    "moderate": "Moderate",
    "high": "High",
    "severe": "Severe",
    "no_travel": "No Travel",
}

# (level, threshold, strict): the reading qualifies if value > threshold (strict)
# or value >= threshold (not strict). Rows run from most to least severe.
Row = tuple[str, float, bool]
Table = tuple[Row, ...]


@dataclass(frozen=True)
class LoadRule:
    """If wind is in [min_mph, max_mph) and load > over_lbs, the level becomes `level`."""

    min_mph: float
    max_mph: float
    over_lbs: float
    level: str


@dataclass(frozen=True)
class RiskRules:
    wind_mph: Table = (
        ("no_travel", 55.0, False),
        ("severe", 45.0, False),
        ("high", 35.0, False),
        ("moderate", 25.0, False),
    )
    rain_in_h: Table = (
        ("no_travel", 1.00, True),
        ("severe", 0.50, False),
        ("high", 0.25, False),
        ("moderate", 0.10, False),
    )
    snow_in_h: Table = (
        ("no_travel", 3.0, True),
        ("severe", 2.0, False),
        ("high", 1.0, False),
        ("moderate", 0.5, False),
    )
    load_rules: tuple[LoadRule, ...] = (
        LoadRule(45.0, 55.0, 30_000, "no_travel"),
        LoadRule(35.0, 45.0, 40_000, "severe"),
    )


DEFAULT_RULES = RiskRules()
