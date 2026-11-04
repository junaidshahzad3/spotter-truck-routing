import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from routing.clients import UpstreamError, UpstreamTimeout, openmeteo, valhalla

FIXTURES = Path(__file__).parent / "fixtures"


def future(hours=3) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).replace(minute=0, second=0).isoformat()


def payload(**overrides):
    body = {
        "origin": {"lat": 32.7767, "lon": -96.797, "label": "Dallas, TX"},
        "destination": {"lat": 39.7392, "lon": -104.9903, "label": "Denver, CO"},
        "departure": future(),
        "load_weight_lbs": 42000,
        "interval_miles": 25,
    }
    body.update(overrides)
    return body


@pytest.fixture
def fake_upstreams(monkeypatch):
    """Real Valhalla fixture + synthetic weather: snow only west of -103 (Colorado)."""
    data = json.loads((FIXTURES / "valhalla_dallas_denver.json").read_text())
    monkeypatch.setattr(valhalla, "fetch_routes", lambda *a: valhalla.parse_response(data))

    def fake_series(points, start, end):
        day = datetime(start.year, start.month, start.day, tzinfo=UTC)
        n = int((end - day).total_seconds() // 3600) + 2
        out = {}
        for lat, lon in points:
            snow = 0.6 if lon < -103 else 0.0
            out[openmeteo.point_key(lat, lon)] = openmeteo.HourlySeries(
                day, [5.0] * n, [8.0] * n, [0.0] * n, [snow] * n
            )
        return out

    monkeypatch.setattr(openmeteo, "fetch_series", fake_series)


def post(client, body):
    return client.post("/api/plan", body, format="json")


def test_health(api_client):
    assert api_client.get("/api/health").json() == {"status": "ok"}


def test_plan_happy_path(api_client, fake_upstreams):
    r = post(api_client, payload())
    assert r.status_code == 200
    d = r.json()
    assert len(d["routes"]) == 3
    assert [rt["rank"] for rt in d["routes"]] == [1, 2, 3]
    assert d["recommended_route_id"] == d["routes"][0]["id"]
    assert d["recommendation_reason"]
    first = d["routes"][0]
    assert first["checkpoints"][0]["mile"] == 0
    assert first["checkpoints"][-1]["mile"] == pytest.approx(first["distance_mi"], abs=0.1)
    # Snow in Colorado at 0.6 in/h is High, raised to Severe by the 42k lb heavy-load rule.
    assert first["summary"]["severe_mi"] > 0
    cp = next(c for c in first["checkpoints"] if c["risk"] == "severe")
    assert "heavy load" in cp["reasons"][0]
    lo, hi = cp["geometry_range"]
    assert 0 <= lo < hi <= len(first["geometry"])
    assert len(d["heatmap"]["cells"]) <= 150
    assert d["heatmap"]["hours"] == list(range(49))
    assert d["warnings"] == []


def test_plan_ranking_matches_summaries(api_client, fake_upstreams):
    d = post(api_client, payload()).json()
    keys = [
        (rt["summary"]["severe_mi"], rt["summary"]["high_mi"], rt["summary"]["avg_risk"])
        for rt in d["routes"]
    ]
    assert keys == sorted(keys)


def test_plan_without_heatmap(api_client, fake_upstreams):
    d = post(api_client, payload(include_heatmap=False)).json()
    assert d["heatmap"] is None


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"interval_miles": 30}, "interval_miles"),
        ({"load_weight_lbs": -1}, "load_weight_lbs"),
        ({"load_weight_lbs": 200000}, "load_weight_lbs"),
        ({"departure": "2020-01-01T00:00:00Z"}, "past"),
        ({"departure": (datetime.now(UTC) + timedelta(days=30)).isoformat()}, "16-day"),
        ({"destination": {"lat": 32.7767, "lon": -96.797}}, "same place"),
        ({"origin": {"lat": 120, "lon": 0}}, "origin"),
    ],
)
def test_plan_validation_errors(api_client, override, fragment):
    r = post(api_client, payload(**override))
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "invalid_request"
    assert fragment in json.dumps(err)


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (UpstreamError("Valhalla", "HTTP 500"), 502, "upstream_error"),
        (UpstreamTimeout("Open-Meteo"), 504, "upstream_timeout"),
        (UpstreamError("Valhalla", "no truck route", status=422), 422, "no_route"),
    ],
)
def test_upstream_failures_map_to_clean_errors(api_client, monkeypatch, exc, status, code):
    def boom(*a):
        raise exc

    monkeypatch.setattr(valhalla, "fetch_routes", boom)
    r = post(api_client, payload())
    assert r.status_code == status
    assert r.json()["error"]["code"] == code


def test_fewer_routes_adds_warning(api_client, fake_upstreams, monkeypatch):
    data = json.loads((FIXTURES / "valhalla_dallas_denver.json").read_text())
    data["alternates"] = []
    monkeypatch.setattr(valhalla, "fetch_routes", lambda *a: valhalla.parse_response(data))
    d = post(api_client, payload()).json()
    assert len(d["routes"]) == 1
    assert "1 truck route" in d["warnings"][0]
