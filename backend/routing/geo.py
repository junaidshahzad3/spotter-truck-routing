"""Pure geometry helpers: polyline decoding, distances, interpolation along a line."""

from __future__ import annotations

import math
from bisect import bisect_right

EARTH_RADIUS_MI = 3958.7613


def decode_polyline(encoded: str, precision: int = 6) -> list[tuple[float, float]]:
    """Decode a Google-style encoded polyline into (lat, lon) pairs.

    Valhalla uses precision 6 (1e-6 degrees).
    """
    factor = 10**precision
    points: list[tuple[float, float]] = []
    index = lat = lon = 0
    length = len(encoded)
    while index < length:
        deltas = []
        for _ in range(2):
            result = shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append((lat / factor, lon / factor))
    return points


def haversine_mi(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def cumulative_miles(points: list[tuple[float, float]]) -> list[float]:
    cum = [0.0]
    for prev, cur in zip(points, points[1:], strict=False):
        cum.append(cum[-1] + haversine_mi(prev, cur))
    return cum


def interpolate(values: list[float], cum: list[float], target: float) -> float:
    """Linearly interpolate `values` (aligned with `cum`) at distance `target`."""
    if target <= cum[0]:
        return values[0]
    if target >= cum[-1]:
        return values[-1]
    i = bisect_right(cum, target) - 1
    span = cum[i + 1] - cum[i]
    frac = 0.0 if span == 0 else (target - cum[i]) / span
    return values[i] + frac * (values[i + 1] - values[i])


def point_at(
    points: list[tuple[float, float]], cum: list[float], target: float
) -> tuple[float, float]:
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return interpolate(lats, cum, target), interpolate(lons, cum, target)


def index_at(cum: list[float], target: float) -> int:
    """Index of the last vertex at or before `target` miles."""
    return max(0, min(len(cum) - 1, bisect_right(cum, target) - 1))


def decimate(
    points: list[tuple[float, float]], cum: list[float], min_spacing_mi: float
) -> tuple[list[tuple[float, float]], list[float]]:
    """Drop vertices closer than `min_spacing_mi` to the previous kept one.

    Always keeps the first and last vertex. Used to shrink the JSON payload.
    """
    if len(points) <= 2:
        return list(points), list(cum)
    kept_pts = [points[0]]
    kept_cum = [cum[0]]
    for p, c in zip(points[1:-1], cum[1:-1], strict=False):
        if c - kept_cum[-1] >= min_spacing_mi:
            kept_pts.append(p)
            kept_cum.append(c)
    kept_pts.append(points[-1])
    kept_cum.append(cum[-1])
    return kept_pts, kept_cum
