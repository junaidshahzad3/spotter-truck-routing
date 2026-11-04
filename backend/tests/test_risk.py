"""Risk engine: every threshold in the table is tested at, just below and just above."""

import pytest

from routing.domain import Weather
from routing.risk import bump, classify, level_for
from routing.risk_rules import DEFAULT_RULES, LEVELS, RiskRules

NEUTRAL_LOAD = 25_000  # neither light nor heavy
CALM = {"wind_mph": 0.0, "gust_mph": 0.0, "rain_in_h": 0.0, "snow_in_h": 0.0}

FIELD_FOR = {
    "wind_mph": DEFAULT_RULES.wind_mph,
    "gust_mph": DEFAULT_RULES.gust_mph,
    "rain_in_h": DEFAULT_RULES.rain_in_h,
    "snow_in_h": DEFAULT_RULES.snow_in_h,
}


def weather(**kw) -> Weather:
    return Weather(**{**CALM, **kw})


def boundary_cases():
    """(field, value, expected) for at / just below / just above every threshold."""
    for field, table in FIELD_FOR.items():
        eps = 0.5 if field.endswith("mph") else 0.005
        rows = list(table)
        for i, (level, minimum) in enumerate(rows):
            below_level = rows[i + 1][0] if i + 1 < len(rows) else "low"
            yield field, minimum, level
            yield field, minimum + eps, level
            yield field, minimum - eps, below_level


@pytest.mark.parametrize(("field", "value", "expected"), list(boundary_cases()))
def test_threshold_boundaries(field, value, expected):
    assert classify(weather(**{field: value}), NEUTRAL_LOAD).level == expected


def test_calm_is_low_with_no_reasons():
    r = classify(weather(), NEUTRAL_LOAD)
    assert (r.level, r.score, r.reasons) == ("low", 0, ())


def test_overall_level_is_worst_factor():
    r = classify(weather(wind_mph=25, rain_in_h=0.35, snow_in_h=1.2), NEUTRAL_LOAD)
    assert r.level == "severe"
    assert r.score == 3
    assert r.reasons[0].startswith("Snow")  # most severe first
    assert len(r.reasons) == 3


def test_negative_and_none_like_values_are_treated_as_zero():
    assert classify(weather(rain_in_h=-1.0), NEUTRAL_LOAD).level == "low"


@pytest.mark.parametrize("field", ["wind_mph", "gust_mph"])
def test_light_load_raises_wind_one_level(field):
    moderate = dict(FIELD_FOR[field])["moderate"]
    light = DEFAULT_RULES.light_load_max_lbs
    r = classify(weather(**{field: moderate}), light)
    assert r.level == "high"
    assert "light load" in r.reasons[0]
    # Same wind on a neutral load stays moderate.
    assert classify(weather(**{field: moderate}), NEUTRAL_LOAD).level == "moderate"


@pytest.mark.parametrize("field", ["rain_in_h", "snow_in_h"])
def test_heavy_load_raises_precip_one_level(field):
    moderate = dict(FIELD_FOR[field])["moderate"]
    heavy = DEFAULT_RULES.heavy_load_min_lbs
    r = classify(weather(**{field: moderate}), heavy)
    assert r.level == "high"
    assert "heavy load" in r.reasons[0]


def test_load_rules_do_not_lift_low_conditions():
    assert classify(weather(wind_mph=10), 0).level == "low"
    assert classify(weather(rain_in_h=0.05), 80_000).level == "low"


def test_load_rules_cap_at_severe():
    r = classify(weather(wind_mph=60), 0)
    assert r.level == "severe"
    assert "raised" not in r.reasons[0]


def test_light_load_does_not_affect_precip_and_heavy_not_wind():
    assert classify(weather(rain_in_h=0.1), 0).level == "moderate"
    assert classify(weather(wind_mph=20), 80_000).level == "moderate"


def test_load_boundaries_are_inclusive():
    rules = DEFAULT_RULES
    w = weather(wind_mph=20)
    assert classify(w, rules.light_load_max_lbs).level == "high"
    assert classify(w, rules.light_load_max_lbs + 1).level == "moderate"
    p = weather(snow_in_h=0.1)
    assert classify(p, rules.heavy_load_min_lbs).level == "high"
    assert classify(p, rules.heavy_load_min_lbs - 1).level == "moderate"


def test_custom_rules_are_respected():
    rules = RiskRules(wind_mph=(("severe", 10.0),))
    assert classify(weather(wind_mph=10), NEUTRAL_LOAD, rules).level == "severe"


def test_helpers():
    assert level_for(0, DEFAULT_RULES.wind_mph) == "low"
    assert [bump(lvl) for lvl in LEVELS] == ["moderate", "high", "severe", "severe"]
