"""Pure risk classifier: weather + load weight -> risk level with human-readable reasons."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Weather
from .risk_rules import DEFAULT_RULES, LABELS, SCORES, RiskRules, Table


@dataclass(frozen=True)
class FactorResult:
    name: str  # "wind" | "rain" | "snow"
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
    for level, threshold, strict in table:
        if value > threshold if strict else value >= threshold:
            return level
    return "low"


def worse(a: str, b: str) -> str:
    return a if SCORES[a] >= SCORES[b] else b


_LABEL = {"wind": "Wind", "rain": "Rain", "snow": "Snow"}


def _fmt(value: float, unit: str) -> str:
    if unit == "mph":  # one decimal, so 54.6 mph isn't shown as "55 mph → Severe"
        return f"{value:.1f}".removesuffix(".0") + " mph"
    return f"{value:.2f} {unit}"


def classify(weather: Weather, load_lbs: float, rules: RiskRules = DEFAULT_RULES) -> RiskResult:
    """Classify one checkpoint at its ETA.

    Wind, rain and snow are each graded on the brief's table. The load rules can
    raise the wind level (never lower it). The overall level is the worst factor.
    """
    readings = (
        ("wind", weather.wind_mph, "mph", rules.wind_mph),
        ("rain", weather.rain_in_h, "in/h", rules.rain_in_h),
        ("snow", weather.snow_in_h, "in/h", rules.snow_in_h),
    )

    factors: list[FactorResult] = []
    reasons: list[tuple[int, str]] = []
    for name, raw, unit, table in readings:
        value = max(0.0, float(raw or 0.0))
        level = level_for(value, table)
        text = f"{_LABEL[name]} {_fmt(value, unit)} → {LABELS[level]}"
        adjusted = False
        if name == "wind":
            for rule in rules.load_rules:
                if rule.min_mph <= value < rule.max_mph and load_lbs > rule.over_lbs:
                    if SCORES[rule.level] > SCORES[level]:
                        level, adjusted = rule.level, True
                        text = (
                            f"Wind {_fmt(value, unit)} with {load_lbs:,.0f} lb load "
                            f"(over {rule.over_lbs:,.0f} lb) → {LABELS[level]}"
                        )
                    break
        factors.append(FactorResult(name, value, unit, level, adjusted))
        if level != "low":
            reasons.append((SCORES[level], text))

    overall = "low"
    for f in factors:
        overall = worse(f.level, overall)
    # Most severe reasons first (stable sort keeps wind/rain/snow order on ties).
    reasons.sort(key=lambda r: -r[0])
    return RiskResult(overall, SCORES[overall], tuple(t for _, t in reasons), tuple(factors))
