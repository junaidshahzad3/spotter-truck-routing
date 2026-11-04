"""Pure checkpoint sampling: points every N miles along a route, with ETAs."""

from __future__ import annotations

from datetime import datetime, timedelta

from .domain import Checkpoint, Route
from .geo import interpolate, point_at

ALLOWED_INTERVALS = (10, 25, 50)


def sample(route: Route, interval_mi: float, departure: datetime) -> list[Checkpoint]:
    """Checkpoints at mile 0, N, 2N, ... and at the destination.

    Each checkpoint "owns" the stretch of road halfway to its neighbours, so the
    stretches tile the route exactly (sum == route length). That is what the
    Severe/High mile totals are built from.
    """
    if interval_mi <= 0:
        raise ValueError("interval must be positive")
    total = route.cum_miles[-1]
    miles = [0.0]
    m = float(interval_mi)
    # Interior checkpoints; one within half a mile of the end would duplicate the destination.
    while m < total - 0.5:
        miles.append(m)
        m += interval_mi
    if total > 0:
        miles.append(total)

    checkpoints: list[Checkpoint] = []
    for i, mile in enumerate(miles):
        start = 0.0 if i == 0 else (miles[i - 1] + mile) / 2
        end = total if i == len(miles) - 1 else (mile + miles[i + 1]) / 2
        lat, lon = point_at(route.points, route.cum_miles, mile)
        seconds = interpolate(route.cum_seconds, route.cum_miles, mile)
        checkpoints.append(
            Checkpoint(
                index=i,
                mile=round(mile, 3),
                lat=lat,
                lon=lon,
                eta=(departure + timedelta(seconds=seconds)).replace(microsecond=0),
                start_mi=start,
                end_mi=end,
            )
        )
    return checkpoints
