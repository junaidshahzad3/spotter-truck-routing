"""Plain data types shared across the routing pipeline (no Django, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float


@dataclass
class Route:
    """A drivable route with per-shape-point cumulative distance and time."""

    id: str
    points: list[tuple[float, float]]  # (lat, lon)
    cum_miles: list[float]
    cum_seconds: list[float]
    distance_mi: float
    duration_s: float


@dataclass(frozen=True)
class Weather:
    """Hourly conditions at a point. Units: mph and inches per hour."""

    wind_mph: float
    gust_mph: float
    rain_in_h: float
    snow_in_h: float
    time: datetime | None = None


@dataclass
class Checkpoint:
    index: int
    mile: float
    lat: float
    lon: float
    eta: datetime
    start_mi: float  # stretch of road this checkpoint represents
    end_mi: float
    weather: Weather | None = None
    risk: str | None = None  # None means "no forecast available"
    score: int | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def segment_mi(self) -> float:
        return self.end_mi - self.start_mi
