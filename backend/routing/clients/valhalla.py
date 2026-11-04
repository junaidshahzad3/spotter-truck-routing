"""Valhalla truck routing (public server: valhalla1.openstreetmap.de, max 1 req/s)."""

from __future__ import annotations

import threading
import time
from typing import Any

from django.conf import settings
from django.core.cache import cache

from ..domain import LatLon, Route
from ..geo import cumulative_miles, decode_polyline
from . import UpstreamError, cache_key, http_json

SERVICE = "Valhalla"
LBS_PER_TONNE = 2204.62
# Typical empty tractor + 53' trailer. Valhalla's truck `weight` is gross weight in tonnes.
TARE_WEIGHT_LBS = 33_000
MIN_INTERVAL_S = 1.05

_lock = threading.Lock()
_last_call = 0.0


def _throttle() -> None:
    """Keep this process at <= 1 request/second to the public server."""
    global _last_call
    with _lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def build_request(origin: LatLon, destination: LatLon, load_lbs: float) -> dict[str, Any]:
    gross_tonnes = round((TARE_WEIGHT_LBS + load_lbs) / LBS_PER_TONNE, 2)
    return {
        "locations": [
            {"lat": origin.lat, "lon": origin.lon},
            {"lat": destination.lat, "lon": destination.lon},
        ],
        "costing": "truck",
        "costing_options": {"truck": {"weight": gross_tonnes}},
        "alternates": 2,
        "units": "miles",
        "directions_options": {"units": "miles"},
    }


def parse_trip(trip: dict[str, Any], route_id: str) -> Route:
    """Turn one Valhalla trip into a Route with per-vertex cumulative miles and seconds."""
    points: list[tuple[float, float]] = []
    seconds: list[float] = []
    for leg in trip["legs"]:
        leg_pts = decode_polyline(leg["shape"], 6)
        leg_cum = cumulative_miles(leg_pts)
        leg_sec = [0.0] * len(leg_pts)
        # Spread each maneuver's time over its shape segment in proportion to distance,
        # so ETA follows real road speeds instead of a single average.
        for m in leg["maneuvers"]:
            b, e = m["begin_shape_index"], m["end_shape_index"]
            span = leg_cum[e] - leg_cum[b]
            t0 = leg_sec[b]
            for i in range(b + 1, e + 1):
                frac = (leg_cum[i] - leg_cum[b]) / span if span > 0 else 1.0
                leg_sec[i] = t0 + frac * float(m["time"])
        offset = seconds[-1] if seconds else 0.0
        if points and leg_pts and points[-1] == leg_pts[0]:
            leg_pts, leg_sec = leg_pts[1:], leg_sec[1:]
        points.extend(leg_pts)
        seconds.extend(offset + s for s in leg_sec)

    if len(points) < 2:
        raise UpstreamError(SERVICE, "route has no geometry")

    cum = cumulative_miles(points)
    distance = float(trip["summary"]["length"])
    duration = float(trip["summary"]["time"])
    # Snap haversine distances to Valhalla's reported length so miles add up exactly.
    scale = distance / cum[-1] if cum[-1] > 0 else 1.0
    cum = [c * scale for c in cum]
    # Likewise make the last timestamp equal the summary time.
    if seconds[-1] > 0:
        tscale = duration / seconds[-1]
        seconds = [s * tscale for s in seconds]
    return Route(route_id, points, cum, seconds, distance, duration)


def parse_response(data: dict[str, Any]) -> list[Route]:
    trips = [data["trip"]] + [alt["trip"] for alt in data.get("alternates", [])]
    return [parse_trip(trip, f"r{i + 1}") for i, trip in enumerate(trips)]


def fetch_routes(origin: LatLon, destination: LatLon, load_lbs: float) -> list[Route]:
    body = build_request(origin, destination, load_lbs)
    key = cache_key("valhalla", body)
    data = cache.get(key)
    if data is None:
        _throttle()
        try:
            data = http_json(SERVICE, "POST", settings.VALHALLA_URL, body=body, timeout=30)
        except UpstreamError as exc:
            # Valhalla answers 400 with a JSON error when it cannot route the request
            # (e.g. 442 "No path could be found", 171 "No suitable edges near location").
            if exc.message.startswith("HTTP 400"):
                raise UpstreamError(
                    SERVICE, "no truck route found between these places", status=422
                ) from exc
            raise
        if "trip" not in data:
            raise UpstreamError(SERVICE, "unexpected response")
        cache.set(key, data)
    try:
        return parse_response(data)
    except (KeyError, IndexError, TypeError) as exc:
        raise UpstreamError(SERVICE, "could not parse route") from exc
