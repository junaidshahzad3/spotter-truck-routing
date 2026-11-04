"""Open-Meteo hourly forecasts for many points (batched multi-coordinate requests)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from django.conf import settings
from django.core.cache import cache

from ..domain import Weather
from . import UpstreamError, cache_key, http_json

SERVICE = "Open-Meteo"
HOURLY_VARS = ("wind_speed_10m", "wind_gusts_10m", "rain", "snowfall")
BATCH_SIZE = 50
FORECAST_DAYS = 16  # Open-Meteo maximum


@dataclass
class HourlySeries:
    start: datetime  # UTC, on the hour
    wind: list[float | None]
    gust: list[float | None]
    rain: list[float | None]
    snow: list[float | None]

    def at(self, when: datetime) -> Weather | None:
        """Weather for the hour nearest to `when` (UTC), or None if outside the series."""
        hour = round_to_hour(when)
        i = int((hour - self.start).total_seconds() // 3600)
        if i < 0 or i >= len(self.wind):
            return None
        values = (self.wind[i], self.gust[i], self.rain[i], self.snow[i])
        if any(v is None for v in values):
            return None
        return Weather(*(float(v) for v in values), time=hour)


def round_to_hour(when: datetime) -> datetime:
    when = when.astimezone(UTC)
    base = when.replace(minute=0, second=0, microsecond=0)
    return base + timedelta(hours=1) if when - base >= timedelta(minutes=30) else base


def horizon_end(today: date | None = None) -> datetime:
    """Last forecast hour Open-Meteo can return (end of day today+15, UTC)."""
    today = today or datetime.now(UTC).date()
    last_day = today + timedelta(days=FORECAST_DAYS - 1)
    return datetime(last_day.year, last_day.month, last_day.day, 23, tzinfo=UTC)


def point_key(lat: float, lon: float) -> tuple[float, float]:
    # ~1 km: well below the model grid spacing, and lets overlapping routes share requests.
    return round(lat, 2), round(lon, 2)


def _parse_location(item: dict, start: datetime) -> HourlySeries:
    hourly = item["hourly"]
    times = hourly["time"]
    first = datetime.fromisoformat(times[0]).replace(tzinfo=UTC)
    if first != start:
        raise UpstreamError(SERVICE, "unexpected time axis")
    return HourlySeries(
        start=first,
        wind=hourly["wind_speed_10m"],
        gust=hourly["wind_gusts_10m"],
        rain=hourly["rain"],
        snow=hourly["snowfall"],
    )


def fetch_series(
    points: list[tuple[float, float]], start: datetime, end: datetime
) -> dict[tuple[float, float], HourlySeries]:
    """Hourly series covering [start, end] (UTC) for each distinct point.

    The range is clamped to the forecast horizon; hours past it are simply absent,
    and `HourlySeries.at` returns None for them.
    """
    start_day = start.astimezone(UTC).date()
    end = min(end.astimezone(UTC), horizon_end())
    end_day = max(start_day, end.date())
    day_start = datetime(start_day.year, start_day.month, start_day.day, tzinfo=UTC)

    keys = sorted({point_key(lat, lon) for lat, lon in points})
    result: dict[tuple[float, float], HourlySeries] = {}
    missing: list[tuple[float, float]] = []
    for k in keys:
        cached = cache.get(cache_key("om", [k, str(start_day), str(end_day)]))
        if cached is not None:
            result[k] = cached
        else:
            missing.append(k)

    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i : i + BATCH_SIZE]
        params = {
            "latitude": ",".join(f"{k[0]:.2f}" for k in batch),
            "longitude": ",".join(f"{k[1]:.2f}" for k in batch),
            "hourly": ",".join(HOURLY_VARS),
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",  # also makes snowfall inches
            "timezone": "UTC",
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),
        }
        data = http_json(SERVICE, "GET", settings.OPEN_METEO_URL, params=params, timeout=20)
        items = data if isinstance(data, list) else [data]
        if len(items) != len(batch):
            raise UpstreamError(SERVICE, "location count mismatch")
        try:
            for k, item in zip(batch, items, strict=True):
                series = _parse_location(item, day_start)
                result[k] = series
                cache.set(cache_key("om", [k, str(start_day), str(end_day)]), series, 3600)
        except (KeyError, IndexError, ValueError) as exc:
            raise UpstreamError(SERVICE, "could not parse forecast") from exc
    return result
