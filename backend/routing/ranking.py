"""Pure route ranking, per the brief's "Route Recommendation":

    1. Fewest Severe miles  2. Fewest High miles  3. Lowest average risk  4. Shortest time

The brief's table also defines a "No Travel" level, which is worse than Severe. A
route that crosses No Travel conditions should never beat one that doesn't, so No
Travel miles are compared first and the brief's order follows.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .domain import Checkpoint
from .risk_rules import LEVELS, SCORES

# Differences smaller than these are treated as ties.
MILES_EPS = 0.5
RISK_EPS = 0.005


@dataclass(frozen=True)
class RouteSummary:
    route_id: str
    name: str
    no_travel_mi: float
    severe_mi: float
    high_mi: float
    moderate_mi: float
    low_mi: float
    unknown_mi: float  # no forecast (beyond horizon)
    avg_risk: float  # mile-weighted mean score over forecast-covered miles, 0..4
    max_risk: str | None
    duration_s: float
    distance_mi: float


def summarize(
    route_id: str, name: str, checkpoints: list[Checkpoint], duration_s: float, distance_mi: float
) -> RouteSummary:
    miles: dict[str | None, float] = {level: 0.0 for level in LEVELS} | {None: 0.0}
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
        no_travel_mi=round(miles["no_travel"], 1),
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


def _key(s: RouteSummary) -> tuple[float, ...]:
    return (s.no_travel_mi, s.severe_mi, s.high_mi, s.avg_risk, s.duration_s)


def _miles(v: float) -> str:
    return f"{v:.0f} mi"


def _hours(s: float) -> str:
    return f"{s / 3600:.1f} h"


def _risk(v: float) -> str:
    return f"{v:.2f}"


# (attribute, tie tolerance, phrase, formatter)
_CRITERIA: tuple[tuple[str, float, str, Callable[[float], str]], ...] = (
    ("no_travel_mi", MILES_EPS, "Fewest No Travel miles", _miles),
    ("severe_mi", MILES_EPS, "Fewest Severe miles", _miles),
    ("high_mi", MILES_EPS, "Fewest High miles", _miles),
    ("avg_risk", RISK_EPS, "Lowest average risk (0 = Low … 4 = No Travel)", _risk),
)


def rank(summaries: list[RouteSummary]) -> tuple[list[RouteSummary], str]:
    """Return summaries best-first and a sentence explaining why #1 won."""
    if not summaries:
        return [], ""
    ordered = sorted(summaries, key=_key)
    best = ordered[0]
    if len(ordered) == 1:
        return ordered, "Only one truck route was available."
    others = ordered[1:]
    second = others[0]

    zero: list[str] = []  # criteria where every route has 0 miles
    tied: list[str] = []  # criteria where routes tie on a non-zero amount
    for attr, eps, phrase, fmt in _CRITERIA:
        if getattr(second, attr) - getattr(best, attr) > eps:
            versus = ", ".join(f"{fmt(getattr(o, attr))} ({o.name})" for o in others)
            text = f"{phrase}: {fmt(getattr(best, attr))} vs {versus}."
            return ordered, _finish(zero, tied, text, best)
        if attr != "avg_risk":
            name = phrase.removeprefix("Fewest ").removesuffix(" miles")
            (zero if all(getattr(o, attr) <= eps for o in ordered) else tied).append(name)

    versus = ", ".join(f"{_hours(o.duration_s)} ({o.name})" for o in others)
    text = f"Shortest travel time: {_hours(best.duration_s)} vs {versus}."
    tied.append("average risk")
    return ordered, _finish(zero, tied, text, best)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} or {items[-1]}"


def _finish(zero: list[str], tied: list[str], text: str, best: RouteSummary) -> str:
    parts = []
    if zero:
        parts.append(f"No route has {_join(zero)} miles")
    if tied:
        parts.append(("tied on " if parts else "Tied on ") + " and ".join(tied))
    if parts:
        text = f"{'; '.join(parts)}. {text}"
    if best.no_travel_mi > MILES_EPS:
        text += " Every route crosses No Travel conditions; consider another departure time."
    return text
