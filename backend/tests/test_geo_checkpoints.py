from datetime import UTC, datetime, timedelta

import pytest

from routing.checkpoints import sample
from routing.domain import Route
from routing.geo import (
    cumulative_miles,
    decimate,
    decode_polyline,
    haversine_mi,
    index_at,
    interpolate,
)

DEP = datetime(2026, 11, 6, 14, 0, tzinfo=UTC)


def straight_route(total_mi: float = 100.0, mph: float = 50.0, n: int = 101) -> Route:
    """A synthetic north-south line with constant speed (easy exact expectations)."""
    pts = [(30.0 + i * 0.01, -97.0) for i in range(n)]
    raw = cumulative_miles(pts)
    cum = [c * total_mi / raw[-1] for c in raw]
    secs = [c / mph * 3600 for c in cum]
    return Route("r1", pts, cum, secs, total_mi, secs[-1])


def test_decode_polyline_reference_vector():
    # Google's documented example, precision 5.
    pts = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@", precision=5)
    assert pts == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_haversine_dallas_denver():
    assert haversine_mi((32.7767, -96.797), (39.7392, -104.9903)) == pytest.approx(663, abs=3)


def test_interpolate_and_index():
    cum = [0.0, 10.0, 20.0]
    assert interpolate([0.0, 100.0, 300.0], cum, 15) == pytest.approx(200)
    assert interpolate([0.0, 100.0, 300.0], cum, -5) == 0
    assert interpolate([0.0, 100.0, 300.0], cum, 99) == 300
    assert index_at(cum, 15) == 1
    assert index_at(cum, 20) == 2


def test_decimate_keeps_ends_and_spacing():
    pts = [(0.0, float(i)) for i in range(11)]
    cum = [float(i) * 0.1 for i in range(11)]
    kept, kept_cum = decimate(pts, cum, 0.35)
    assert kept[0] == pts[0] and kept[-1] == pts[-1]
    assert all(b - a >= 0.35 - 1e-9 for a, b in zip(kept_cum[:-2], kept_cum[1:-1], strict=False))


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_checkpoints_every_interval_plus_destination(interval):
    cps = sample(straight_route(100), interval, DEP)
    miles = [cp.mile for cp in cps]
    expected = [float(m) for m in range(0, 100, interval)] + [100.0]
    assert miles == pytest.approx(expected)


def test_stretches_tile_the_route_exactly():
    cps = sample(straight_route(103.7), 25, DEP)
    assert cps[0].start_mi == 0
    assert cps[-1].end_mi == pytest.approx(103.7)
    for a, b in zip(cps, cps[1:], strict=False):
        assert a.end_mi == pytest.approx(b.start_mi)
    assert sum(cp.segment_mi for cp in cps) == pytest.approx(103.7)
    # Interior checkpoints represent one full interval.
    assert cps[1].segment_mi == pytest.approx(25)


def test_eta_follows_cumulative_drive_time():
    cps = sample(straight_route(100, mph=50), 25, DEP)
    assert cps[0].eta == DEP
    assert cps[1].eta == DEP + timedelta(minutes=30)  # 25 mi at 50 mph
    assert cps[-1].eta == DEP + timedelta(hours=2)


def test_no_duplicate_checkpoint_right_before_destination():
    cps = sample(straight_route(50.3), 25, DEP)
    assert [cp.mile for cp in cps] == pytest.approx([0, 25, 50.3])


def test_positions_are_on_the_line():
    route = straight_route(100)
    cp = sample(route, 50, DEP)[1]
    assert cp.lon == pytest.approx(-97.0)
    assert route.points[0][0] < cp.lat < route.points[-1][0]


def test_rejects_non_positive_interval():
    with pytest.raises(ValueError):
        sample(straight_route(), 0, DEP)
