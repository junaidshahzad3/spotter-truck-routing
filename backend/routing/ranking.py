"""Pure route ranking.

Order: fewest Severe miles -> fewest High miles -> lowest average risk -> shortest time.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Checkpoint
from .risk_rules import SCORES

# Differences smaller than these are treated as ties.
MILES_EPS = 0.5
RISK_EPS = 0.005
TIME_EPS_S = 60


@dataclass(frozen=True)
class RouteSummary:
    route_id: str
    name: str
    severe_mi: float
    high_mi: float
    moderate_mi: float
    low_mi: float
    unknown_mi: float  # no forecast (beyond horizon)
    avg_risk: float  # mile-weighted mean score over forecast-covered miles, 0..3
    max_risk: str | None
    duration_s: float
    distance_mi: float


def summarize(
    route_id: str, name: str, checkpoints: list[Checkpoint], duration_s: float, distance_mi: float
) -> RouteSummary:
    miles = {"severe": 0.0, "high": 0.0, "moderate": 0.0, "low": 0.0, None: 0.0}
    weighted = 0.0
    for cp in checkpoints:
        miles[cp.risk] += cp.segment_mi
        if cp.risk is not None:
            weighted += SCORES[cp.risk] * cp.segment_mi
    covered = sum(v for k, v in miles.items() if k is not None)
    known = [cp.risk for cp in checkpoints if cp.risk is not None]
    return RouteSummary(
        route_id=route_id,
        name=name,
        severe_mi=round(miles["severe"], 1),
        high_mi=round(miles["high"], 1),
        moderate_mi=round(miles["moderate"], 1),
        low_mi=round(miles["low"], 1),
        unknown_mi=round(miles[None], 1),
        avg_risk=round(weighted / covered, 3) if covered > 0 else 0.0,
        max_risk=max(known, key=SCORES.__getitem__) if known else None,
        duration_s=duration_s,
        distance_mi=distance_mi,
    )


def _key(s: RouteSummary) -> tuple[float, float, float, float]:
    return (s.severe_mi, s.high_mi, s.avg_risk, s.duration_s)


def rank(summaries: list[RouteSummary]) -> tuple[list[RouteSummary], str]:
    """Return summaries best-first and a sentence explaining why #1 won."""
    if not summaries:
        return [], ""
    ordered = sorted(summaries, key=_key)
    best = ordered[0]
    if len(ordered) == 1:
        return ordered, "Only one truck route was available."
    others = ordered[1:]

    def listing(attr: str, fmt) -> str:
        return ", ".join(f"{fmt(getattr(o, attr))} ({o.name})" for o in others)

    def hours(s: float) -> str:
        return f"{s / 3600:.1f} h"

    def miles(v: float) -> str:
        return f"{v:.0f} mi"

    second = others[0]
    if second.severe_mi - best.severe_mi > MILES_EPS:
        return ordered, (
            f"Fewest Severe-risk miles: {miles(best.severe_mi)} vs {listing('severe_mi', miles)}."
        )
    if second.high_mi - best.high_mi > MILES_EPS:
        no_severe = all(o.severe_mi <= MILES_EPS for o in ordered)
        tie = "No Severe miles on any route; " if no_severe else "Tied on Severe miles; "
        return ordered, (
            f"{tie}fewest High-risk miles: {miles(best.high_mi)} vs {listing('high_mi', miles)}."
        )
    if second.avg_risk - best.avg_risk > RISK_EPS:
        return ordered, (
            "Tied on Severe and High miles; lowest average risk: "
            f"{best.avg_risk:.2f} vs {listing('avg_risk', lambda v: f'{v:.2f}')} "
            "(0 = Low, 3 = Severe)."
        )
    return ordered, (
        f"Weather risk is equivalent on all routes; fastest: {hours(best.duration_s)} vs "
        f"{listing('duration_s', hours)}."
    )
