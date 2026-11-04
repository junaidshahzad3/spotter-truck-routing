from datetime import UTC, datetime

import pytest

from routing.clients.openmeteo import HourlySeries
from routing.domain import Checkpoint
from routing.heatmap import build_grid, build_heatmap, hour_times
from routing.ranking import rank, summarize

DEP = datetime(2026, 11, 6, 14, tzinfo=UTC)


def cps(risks: list[str | None], seg: float = 25.0) -> list[Checkpoint]:
    return [
        Checkpoint(i, i * seg, 0, 0, DEP, i * seg, (i + 1) * seg, risk=r)
        for i, r in enumerate(risks)
    ]


def route(rid, risks, hours=10.0, seg=25.0):
    distance = seg * len(risks)
    return summarize(rid, f"Route {rid}", cps(risks, seg), hours * 3600, distance)


def test_summary_mile_totals_and_weighted_average():
    s = route("A", ["low", "high", "severe", "moderate", "no_travel"])
    assert (s.no_travel_mi, s.severe_mi, s.high_mi, s.moderate_mi, s.low_mi) == (25,) * 5
    assert s.avg_risk == pytest.approx((0 + 2 + 3 + 1 + 4) / 5)
    assert s.max_risk == "no_travel"


def test_unknown_miles_are_excluded_from_average():
    s = route("A", ["high", None, None])
    assert s.unknown_mi == 50
    assert s.avg_risk == pytest.approx(2.0)


def test_no_travel_miles_rank_before_severe_miles():
    a = route("A", ["no_travel", "low", "low"], hours=8)
    b = route("B", ["severe", "severe", "severe"], hours=12)
    ordered, reason = rank([a, b])
    assert ordered[0].route_id == "B"
    assert reason.startswith("Fewest No Travel miles: 0 mi vs 25 mi (Route A)")


def test_rank_by_severe_miles_first():
    a = route("A", ["severe", "low", "low"], hours=8)
    b = route("B", ["high", "high", "high"], hours=12)
    ordered, reason = rank([a, b])
    assert ordered[0].route_id == "B"
    assert reason.startswith("No route has No Travel miles. Fewest Severe miles")


def test_rank_by_high_miles_when_severe_tied():
    a = route("A", ["severe", "high", "high"], hours=8)
    b = route("B", ["severe", "moderate", "moderate"], hours=12)
    ordered, reason = rank([a, b])
    assert ordered[0].route_id == "B"
    assert reason == (
        "No route has No Travel miles; tied on Severe. Fewest High miles: 0 mi vs 50 mi (Route A)."
    )


def test_rank_by_average_risk_when_severe_and_high_tied():
    a = route("A", ["moderate", "moderate", "low"], hours=8)
    b = route("B", ["moderate", "low", "low"], hours=12)
    ordered, reason = rank([a, b])
    assert ordered[0].route_id == "B"
    assert "Lowest average risk" in reason


def test_rank_by_time_when_risk_equal():
    a = route("A", ["low", "low"], hours=12)
    b = route("B", ["low", "low"], hours=9)
    c = route("C", ["low", "low"], hours=10)
    ordered, reason = rank([a, b, c])
    assert [s.route_id for s in ordered] == ["B", "C", "A"]
    assert reason == (
        "No route has No Travel, Severe or High miles; tied on average risk. "
        "Shortest travel time: 9.0 h vs 10.0 h (Route C), 12.0 h (Route A)."
    )


def test_warns_when_every_route_needs_no_travel():
    a = route("A", ["no_travel", "low"], hours=8)
    b = route("B", ["no_travel", "no_travel"], hours=9)
    _, reason = rank([a, b])
    assert "Every route crosses No Travel conditions" in reason


def test_rank_single_and_empty():
    assert rank([])[0] == []
    assert rank([route("A", ["low"])])[1] == "Only one truck route was available."


def test_grid_respects_cell_cap_and_covers_bbox():
    bbox = (32.0, -105.0, 40.0, -96.0)
    g = build_grid(bbox, max_cells=150)
    assert g.rows * g.cols <= 150
    assert g.lat0 <= 32.0 and g.lat0 + g.rows * g.step >= 40.0
    assert g.lon0 <= -105.0 and g.lon0 + g.cols * g.step >= -96.0


def test_small_bbox_uses_minimum_step():
    g = build_grid((40.0, -100.0, 40.1, -99.9))
    assert g.step == 0.25


def test_heatmap_cells_use_risk_engine():
    g = build_grid((40.0, -100.0, 40.1, -99.9))
    hours = len(hour_times(DEP))
    snow = [2.5] * 72  # Severe snow (2.0-3.0 in/h) every hour
    series = {}
    from routing.clients.openmeteo import point_key

    for lat, lon in g.centers():
        series[point_key(lat, lon)] = HourlySeries(
            datetime(2026, 11, 6, tzinfo=UTC), [0.0] * 72, [0.0] * 72, [0.0] * 72, snow
        )
    hm = build_heatmap(g, series, DEP, 25_000)
    assert len(hm["times"]) == hours == 49
    assert all(cell["risk"] == [3] * 49 for cell in hm["cells"])


def test_heatmap_missing_series_is_none():
    g = build_grid((40.0, -100.0, 40.1, -99.9))
    hm = build_heatmap(g, {}, DEP, 25_000)
    assert hm["cells"][0]["risk"][0] is None
