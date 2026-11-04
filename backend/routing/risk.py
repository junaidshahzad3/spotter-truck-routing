"""Pure risk classifier: weather + load weight -> risk level with human-readable reasons."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Weather
from .risk_rules import DEFAULT_RULES, LEVELS, SCORES, RiskRules, Table


@dataclass(frozen=True)
class FactorResult:
    name: str  # "wind" | "gust" | "rain" | "snow"
    value: float
    unit: str
    level: str
    load_adjusted: bool = False


@dataclass(frozen=True)
class RiskResult:
    level: str
    score: int
    reasons: tuple[str, ...]
    factors: tuple[FactorResult, ...]


def level_for(value: float, table: Table) -> str:
    for level, minimum in table:
        if value >= minimum:
            return level
    return "low"


def bump(level: str) -> str:
    return LEVELS[min(SCORES[level] + 1, len(LEVELS) - 1)]


_LABEL = {"wind": "Wind", "gust": "Gusts", "rain": "Rain", "snow": "Snow"}


def _fmt(value: float, unit: str) -> str:
    return f"{value:.0f} {unit}" if unit == "mph" else f"{value:.2f} {unit}"


def classify(weather: Weather, load_lbs: float, rules: RiskRules = DEFAULT_RULES) -> RiskResult:
    """Classify one point in time/space.

    Each factor is graded on its own table, load rules may raise a factor by one
    level (only if that factor is already at least "moderate"), and the overall
    level is the worst factor.
    """
    readings = (
        ("wind", weather.wind_mph, "mph", rules.wind_mph),
        ("gust", weather.gust_mph, "mph", rules.gust_mph),
        ("rain", weather.rain_in_h, "in/h", rules.rain_in_h),
        ("snow", weather.snow_in_h, "in/h", rules.snow_in_h),
    )
    light = load_lbs <= rules.light_load_max_lbs
    heavy = load_lbs >= rules.heavy_load_min_lbs

    factors: list[FactorResult] = []
    reasons: list[tuple[int, str]] = []
    for name, value, unit, table in readings:
        value = max(0.0, float(value or 0.0))
        level = level_for(value, table)
        adjusted = False
        load_applies = (light and name in ("wind", "gust")) or (heavy and name in ("rain", "snow"))
        if level != "low" and load_applies:
            new_level = bump(level)
            adjusted = new_level != level
            level = new_level
        factors.append(FactorResult(name, value, unit, level, adjusted))
        if level != "low":
            text = f"{_LABEL[name]} {_fmt(value, unit)} → {level.capitalize()}"
            if adjusted:
                why = "light load" if name in ("wind", "gust") else "heavy load"
                text += f" (raised for {why}, {load_lbs:,.0f} lbs)"
            reasons.append((SCORES[level], text))

    worst = max(factors, key=lambda f: SCORES[f.level]).level
    # Most severe reasons first (stable sort keeps table order on ties).
    reasons.sort(key=lambda r: -r[0])
    return RiskResult(worst, SCORES[worst], tuple(t for _, t in reasons), tuple(factors))
