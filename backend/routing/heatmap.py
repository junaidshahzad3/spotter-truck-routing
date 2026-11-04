"""Weather-risk heatmap: a coarse grid over the routes' area, risk per hour for 0-48 h."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from .clients.openmeteo import HourlySeries, point_key
from .risk import classify

HOURS = 48
MAX_CELLS = 150
MIN_STEP_DEG = 0.25  # ~ the forecast model's useful resolution
PAD_DEG = 0.5


@dataclass(frozen=True)
class GridSpec:
    lat0: float
    lon0: float
    step: float
    rows: int
    cols: int

    def centers(self) -> list[tuple[float, float]]:
        return [
            (self.lat0 + (r + 0.5) * self.step, self.lon0 + (c + 0.5) * self.step)
            for r in range(self.rows)
            for c in range(self.cols)
        ]


def build_grid(bbox: tuple[float, float, float, float], max_cells: int = MAX_CELLS) -> GridSpec:
    """Square cells covering bbox (min_lat, min_lon, max_lat, max_lon) plus padding.

    The step grows until the cell count fits under `max_cells` (API budget).
    """
    min_lat, min_lon, max_lat, max_lon = bbox
    min_lat, min_lon = min_lat - PAD_DEG, min_lon - PAD_DEG
    max_lat, max_lon = max_lat + PAD_DEG, max_lon + PAD_DEG
    height, width = max_lat - min_lat, max_lon - min_lon
    step = max(MIN_STEP_DEG, math.sqrt(height * width / max_cells))
    while math.ceil(height / step) * math.ceil(width / step) > max_cells:
        step *= 1.05
    step = round(step, 4)
    return GridSpec(min_lat, min_lon, step, math.ceil(height / step), math.ceil(width / step))


def hour_times(departure: datetime, hours: int = HOURS) -> list[datetime]:
    start = departure.replace(minute=0, second=0, microsecond=0)
    return [start + timedelta(hours=h) for h in range(hours + 1)]


def cell_risks(
    series: HourlySeries | None, times: list[datetime], load_lbs: float
) -> list[int | None]:
    out: list[int | None] = []
    for t in times:
        w = series.at(t) if series else None
        out.append(None if w is None else classify(w, load_lbs).score)
    return out


def build_heatmap(
    grid: GridSpec,
    series_by_point: dict[tuple[float, float], HourlySeries],
    departure: datetime,
    load_lbs: float,
) -> dict:
    times = hour_times(departure)
    cells = []
    for lat, lon in grid.centers():
        risks = cell_risks(series_by_point.get(point_key(lat, lon)), times, load_lbs)
        cells.append({"lat": round(lat, 4), "lon": round(lon, 4), "risk": risks})
    return {
        "step_deg": grid.step,
        "hours": list(range(len(times))),
        "times": [t.isoformat() for t in times],
        "cells": cells,
    }
