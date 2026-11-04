import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from routing.clients import UpstreamError, openmeteo, valhalla
from routing.domain import LatLon

FIXTURES = Path(__file__).parent / "fixtures"
DALLAS = LatLon(32.7767, -96.797)
DENVER = LatLon(39.7392, -104.9903)


def load(name):
    return json.loads((FIXTURES / name).read_text())


# ---------------------------------------------------------------- Valhalla


def test_parse_real_response_gives_three_consistent_routes():
    routes = valhalla.parse_response(load("valhalla_dallas_denver.json"))
    assert [r.id for r in routes] == ["r1", "r2", "r3"]
    assert [round(r.distance_mi) for r in routes] == [889, 853, 818]
    for r in routes:
        assert r.cum_miles[-1] == pytest.approx(r.distance_mi)
        assert r.cum_seconds[-1] == pytest.approx(r.duration_s)
        assert all(b >= a for a, b in zip(r.cum_seconds, r.cum_seconds[1:], strict=False))
        assert len(r.points) == len(r.cum_miles) == len(r.cum_seconds)
        assert r.points[0] == pytest.approx((DALLAS.lat, DALLAS.lon), abs=0.05)
        assert r.points[-1] == pytest.approx((DENVER.lat, DENVER.lon), abs=0.05)


def test_build_request_is_truck_with_two_alternates_and_gross_weight():
    body = valhalla.build_request(DALLAS, DENVER, 42_000)
    assert body["costing"] == "truck"
    assert body["alternates"] == 2
    assert body["costing_options"]["truck"]["weight"] == pytest.approx(34.02, abs=0.01)


def test_fetch_routes_caches(monkeypatch):
    calls = []

    def fake_http(service, method, url, **kw):
        calls.append(kw["body"])
        return load("valhalla_dallas_denver.json")

    monkeypatch.setattr(valhalla, "http_json", fake_http)
    monkeypatch.setattr(valhalla, "_throttle", lambda: None)
    valhalla.fetch_routes(DALLAS, DENVER, 42_000)
    routes = valhalla.fetch_routes(DALLAS, DENVER, 42_000)
    assert len(routes) == 3
    assert len(calls) == 1


def test_fetch_routes_maps_400_to_no_route(monkeypatch):
    def fake_http(*a, **kw):
        raise UpstreamError("Valhalla", 'HTTP 400: {"error_code":442}')

    monkeypatch.setattr(valhalla, "http_json", fake_http)
    monkeypatch.setattr(valhalla, "_throttle", lambda: None)
    with pytest.raises(UpstreamError) as exc:
        valhalla.fetch_routes(DALLAS, DENVER, 1000)
    assert exc.value.status == 422


def test_throttle_spaces_calls(monkeypatch):
    sleeps = []
    monkeypatch.setattr(valhalla.time, "sleep", sleeps.append)
    valhalla._last_call = 0.0
    valhalla._throttle()
    valhalla._throttle()
    assert sleeps and sleeps[-1] > 1.0


# ---------------------------------------------------------------- Open-Meteo


def series(hours=48, start=datetime(2026, 11, 5, tzinfo=UTC)):
    return openmeteo.HourlySeries(
        start=start,
        wind=[float(h) for h in range(hours)],
        gust=[0.0] * hours,
        rain=[0.0] * hours,
        snow=[0.0] * hours,
    )


def test_series_picks_nearest_hour():
    s = series()
    t = datetime(2026, 11, 5, 10, 29, tzinfo=UTC)
    assert s.at(t).wind_mph == 10
    assert s.at(t + timedelta(minutes=2)).wind_mph == 11  # 10:31 -> 11:00


def test_series_handles_other_timezones():
    t = datetime(2026, 11, 5, 4, 0, tzinfo=UTC).astimezone()  # same instant, local tz
    assert series().at(t).wind_mph == 4


def test_series_out_of_range_and_nulls_are_none():
    s = series(hours=5)
    assert s.at(datetime(2026, 11, 4, 23, tzinfo=UTC)) is None
    assert s.at(datetime(2026, 11, 5, 6, tzinfo=UTC)) is None
    s.rain[2] = None
    assert s.at(datetime(2026, 11, 5, 2, tzinfo=UTC)) is None


def test_fetch_series_parses_multi_location_fixture(monkeypatch):
    seen = []

    def fake_http(service, method, url, params, **kw):
        seen.append(params)
        return load("openmeteo_two_points.json")

    monkeypatch.setattr(openmeteo, "http_json", fake_http)
    monkeypatch.setattr(openmeteo, "horizon_end", lambda: datetime(2026, 11, 20, tzinfo=UTC))
    start = datetime(2026, 11, 5, 3, tzinfo=UTC)
    out = openmeteo.fetch_series([(39.74, -104.99), (44.0, -110.0)], start, start)
    assert set(out) == {(39.74, -104.99), (44.0, -110.0)}
    assert seen[0]["wind_speed_unit"] == "mph"
    assert seen[0]["precipitation_unit"] == "inch"
    assert out[(39.74, -104.99)].at(start) is not None
    # Second call is served from cache.
    openmeteo.fetch_series([(39.74, -104.99)], start, start)
    assert len(seen) == 1


def test_fetch_series_batches_requests(monkeypatch):
    sizes = []

    def fake_http(service, method, url, params, **kw):
        n = len(params["latitude"].split(","))
        sizes.append(n)
        hourly = {v: [0.0] for v in openmeteo.HOURLY_VARS}
        item = {"hourly": {"time": ["2026-11-05T00:00"], **hourly}}
        return [item] * n

    monkeypatch.setattr(openmeteo, "http_json", fake_http)
    pts = [(30 + i * 0.1, -97.0) for i in range(120)]
    day = datetime(2026, 11, 5, tzinfo=UTC)
    openmeteo.fetch_series(pts, day, day)
    assert sizes == [50, 50, 20]


def test_fetch_series_detects_count_mismatch(monkeypatch):
    monkeypatch.setattr(openmeteo, "http_json", lambda *a, **k: [])
    with pytest.raises(UpstreamError):
        openmeteo.fetch_series([(30.0, -97.0)], datetime.now(UTC), datetime.now(UTC))


def test_horizon_end_is_16_days():
    from datetime import date

    assert openmeteo.horizon_end(date(2026, 11, 4)) == datetime(2026, 11, 19, 23, tzinfo=UTC)
