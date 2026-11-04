"""Orchestrates one plan: routes -> checkpoints -> forecasts -> risk -> ranking -> heatmap."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from .checkpoints import sample
from .clients import openmeteo, valhalla
from .domain import Checkpoint, LatLon, Route
from .geo import decimate, index_at
from .heatmap import HOURS, build_grid, build_heatmap
from .ranking import rank, summarize
from .risk import classify

ROUTE_NAMES = ("Route A", "Route B", "Route C")
GEOMETRY_SPACING_MI = 0.2


def _route_geometry(route: Route) -> tuple[list[list[float]], list[float]]:
    pts, cum = decimate(route.points, route.cum_miles, GEOMETRY_SPACING_MI)
    return [[round(lon, 5), round(lat, 5)] for lat, lon in pts], cum


def _checkpoint_json(cp: Checkpoint, cum: list[float]) -> dict:
    w = cp.weather
    return {
        "index": cp.index,
        "mile": round(cp.mile, 1),
        "lat": round(cp.lat, 5),
        "lon": round(cp.lon, 5),
        "eta": cp.eta.isoformat(),
        "start_mi": round(cp.start_mi, 2),
        "end_mi": round(cp.end_mi, 2),
        # Geometry vertex range drawn in this checkpoint's risk colour.
        "geometry_range": [index_at(cum, cp.start_mi), index_at(cum, cp.end_mi) + 1],
        "weather": None
        if w is None
        else {
            "wind_mph": round(w.wind_mph, 1),
            "gust_mph": round(w.gust_mph, 1),
            "rain_in_h": round(w.rain_in_h, 3),
            "snow_in_h": round(w.snow_in_h, 3),
            "forecast_hour": w.time.isoformat() if w.time else None,
        },
        "risk": cp.risk,
        "score": cp.score,
        "reasons": cp.reasons,
    }


def plan_trip(
    origin: LatLon,
    destination: LatLon,
    departure: datetime,
    load_lbs: float,
    interval_mi: int,
    include_heatmap: bool = True,
) -> dict:
    departure = departure.astimezone(UTC)
    warnings: list[str] = []

    routes = valhalla.fetch_routes(origin, destination, load_lbs)
    if len(routes) < 3:
        warnings.append(
            f"Valhalla returned {len(routes)} truck route(s) for this trip "
            "(alternatives are not always available, especially on short trips)."
        )

    checkpoints = {r.id: sample(r, interval_mi, departure) for r in routes}
    all_cps = [cp for cps in checkpoints.values() for cp in cps]
    last_eta = max(cp.eta for cp in all_cps)

    # Heatmap grid over every route's bounding box.
    lats = [p[0] for r in routes for p in r.points]
    lons = [p[1] for r in routes for p in r.points]
    grid = build_grid((min(lats), min(lons), max(lats), max(lons)))
    grid_points = grid.centers() if include_heatmap else []

    series_end = max(last_eta, departure + timedelta(hours=HOURS)) + timedelta(hours=1)
    series = openmeteo.fetch_series(
        [(cp.lat, cp.lon) for cp in all_cps] + grid_points, departure, series_end
    )

    no_forecast = 0
    for cp in all_cps:
        point_series = series.get(openmeteo.point_key(cp.lat, cp.lon))
        cp.weather = point_series.at(cp.eta) if point_series else None
        if cp.weather is None:
            no_forecast += 1
            cp.reasons = ["No forecast available for this ETA"]
            continue
        result = classify(cp.weather, load_lbs)
        cp.risk, cp.score, cp.reasons = result.level, result.score, list(result.reasons)
    if no_forecast:
        warnings.append(
            f"{no_forecast} checkpoint(s) have ETAs beyond the 16-day forecast range; "
            "they are shown as 'No forecast' and excluded from risk totals."
        )

    names = dict(zip((r.id for r in routes), ROUTE_NAMES, strict=False))
    summaries = [
        summarize(r.id, names[r.id], checkpoints[r.id], r.duration_s, r.distance_mi) for r in routes
    ]
    ordered, reason = rank(summaries)
    order = {s.route_id: i for i, s in enumerate(ordered)}

    routes_json = []
    for r in sorted(routes, key=lambda r: order[r.id]):
        coords, cum = _route_geometry(r)
        summary = next(s for s in summaries if s.route_id == r.id)
        routes_json.append(
            {
                "id": r.id,
                "name": names[r.id],
                "rank": order[r.id] + 1,
                "distance_mi": round(r.distance_mi, 1),
                "duration_s": round(r.duration_s),
                "arrival": (departure + timedelta(seconds=r.duration_s)).isoformat(),
                "geometry": coords,
                "summary": {
                    k: v
                    for k, v in asdict(summary).items()
                    if k not in ("route_id", "name", "duration_s", "distance_mi")
                },
                "checkpoints": [_checkpoint_json(cp, cum) for cp in checkpoints[r.id]],
            }
        )

    return {
        "recommended_route_id": ordered[0].route_id,
        "recommendation_reason": reason,
        "departure": departure.isoformat(),
        "load_weight_lbs": load_lbs,
        "interval_miles": interval_mi,
        "routes": routes_json,
        "heatmap": build_heatmap(grid, series, departure, load_lbs) if include_heatmap else None,
        "warnings": warnings,
    }
