"""Risk thresholds: the ONE place the classification table lives.

!! These values must match the assessment brief's wind/rain/snow table and load rules.
!! The brief was not available in the repo when this was written, so the numbers below
!! are documented working defaults. Edit them here only; tests in
!! tests/test_risk.py read the same table, so boundary tests follow automatically.

Each table lists (level, minimum value) from most to least severe. A reading at or
above the minimum gets that level; anything below every row is "low".
"""

from __future__ import annotations

from dataclasses import dataclass

LEVELS: tuple[str, ...] = ("low", "moderate", "high", "severe")
SCORES: dict[str, int] = {level: i for i, level in enumerate(LEVELS)}

Table = tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class RiskRules:
    # Sustained 10 m wind speed, mph.
    wind_mph: Table = (("severe", 45.0), ("high", 35.0), ("moderate", 20.0))
    # Gusts, mph (gusts are what tip high-profile trailers).
    gust_mph: Table = (("severe", 60.0), ("high", 50.0), ("moderate", 35.0))
    # Liquid rain rate, inches per hour.
    rain_in_h: Table = (("severe", 0.50), ("high", 0.30), ("moderate", 0.10))
    # Snowfall rate, inches per hour.
    snow_in_h: Table = (("severe", 1.00), ("high", 0.50), ("moderate", 0.10))

    # Load rules.
    # Light / empty trailers are prone to blow-over: wind & gust risk +1 level.
    light_load_max_lbs: float = 10_000
    # Heavy loads need longer stopping distances: rain & snow risk +1 level.
    heavy_load_min_lbs: float = 40_000


DEFAULT_RULES = RiskRules()
