"""Risk engine against the assessment brief's table and load rules.

Every band edge is tested at, just below and just above the threshold. The expected
values are written out by hand from the brief (not derived from risk_rules.py), so a
typo in the rules file can't make its own tests pass.
"""

import pytest

from routing.domain import Weather
from routing.risk import classify, level_for
from routing.risk_rules import DEFAULT_RULES, LEVELS, LoadRule, RiskRules

LIGHT = 10_000  # below every load rule
CALM = {"wind_mph": 0.0, "gust_mph": 0.0, "rain_in_h": 0.0, "snow_in_h": 0.0}


def weather(**kw) -> Weather:
    return Weather(**{**CALM, **kw})


# ---- Brief table: Wind <25 | 25-34 | 35-44 | 45-54 | >=55 mph
WIND = [
    (0, "low"),
    (24.9, "low"),
    (25, "moderate"),
    (34.9, "moderate"),
    (35, "high"),
    (44.9, "high"),
    (45, "severe"),
    (54.9, "severe"),
    (55, "no_travel"),
    (80, "no_travel"),
]

# ---- Rain <0.10 | 0.10-0.25 | 0.25-0.50 | 0.50-1.00 | >1.00 in/hr
RAIN = [
    (0.0, "low"),
    (0.099, "low"),
    (0.10, "moderate"),
    (0.249, "moderate"),
    (0.25, "high"),
    (0.499, "high"),
    (0.50, "severe"),
    (1.00, "severe"),  # ">1.00" is strict
    (1.001, "no_travel"),
]

# ---- Snow <0.5 | 0.5-1.0 | 1.0-2.0 | 2.0-3.0 | >3.0 in/hr
SNOW = [
    (0.0, "low"),
    (0.49, "low"),
    (0.5, "moderate"),
    (0.99, "moderate"),
    (1.0, "high"),
    (1.99, "high"),
    (2.0, "severe"),
    (3.0, "severe"),  # ">3.0" is strict
    (3.01, "no_travel"),
]


@pytest.mark.parametrize(("mph", "expected"), WIND)
def test_wind_bands(mph, expected):
    assert classify(weather(wind_mph=mph), LIGHT).level == expected


@pytest.mark.parametrize(("rate", "expected"), RAIN)
def test_rain_bands(rate, expected):
    assert classify(weather(rain_in_h=rate), LIGHT).level == expected


@pytest.mark.parametrize(("rate", "expected"), SNOW)
def test_snow_bands(rate, expected):
    assert classify(weather(snow_in_h=rate), LIGHT).level == expected


# ---- Load rules
@pytest.mark.parametrize(
    ("mph", "load", "expected"),
    [
        # >=55 mph -> No Travel for any load
        (55, 0, "no_travel"),
        (60, 80_000, "no_travel"),
        # 45-54 mph + >30,000 lb -> No Travel
        (45, 30_001, "no_travel"),
        (54.9, 45_000, "no_travel"),
        (45, 30_000, "severe"),  # "> 30,000" is strict
        (50, 20_000, "severe"),
        # 35-44 mph + >40,000 lb -> Severe
        (35, 40_001, "severe"),
        (44.9, 60_000, "severe"),
        (35, 40_000, "high"),  # "> 40,000" is strict
        (40, 35_000, "high"),
        # Below 35 mph, load doesn't matter
        (34.9, 80_000, "moderate"),
        (10, 80_000, "low"),
    ],
)
def test_load_rules(mph, load, expected):
    assert classify(weather(wind_mph=mph), load).level == expected


def test_load_rule_reason_mentions_load():
    r = classify(weather(wind_mph=48), 35_000)
    assert r.level == "no_travel"
    assert "35,000 lb" in r.reasons[0] and "over 30,000" in r.reasons[0]
    assert r.factors[0].load_adjusted


def test_load_rules_never_lower_a_level():
    rules = RiskRules(load_rules=(LoadRule(45, 55, 0, "moderate"),))
    assert classify(weather(wind_mph=50), 50_000, rules).level == "severe"


def test_load_rules_only_touch_wind():
    assert classify(weather(rain_in_h=0.3), 80_000).level == "high"
    assert classify(weather(snow_in_h=1.5), 80_000).level == "high"


def test_overall_is_worst_factor_and_reasons_sorted():
    r = classify(weather(wind_mph=26, rain_in_h=0.3, snow_in_h=2.5), LIGHT)
    assert r.level == "severe"
    assert r.score == 3
    assert r.reasons[0].startswith("Snow")
    assert [lvl.split("→ ")[1] for lvl in r.reasons] == ["Severe", "High", "Moderate"]


def test_gusts_are_not_scored():
    assert classify(weather(gust_mph=90), LIGHT).level == "low"


def test_calm_is_low_with_no_reasons():
    r = classify(weather(), LIGHT)
    assert (r.level, r.score, r.reasons) == ("low", 0, ())


def test_negative_values_are_treated_as_zero():
    assert classify(weather(rain_in_h=-1.0), LIGHT).level == "low"


def test_reason_shows_one_decimal_mph():
    assert classify(weather(wind_mph=54.6), LIGHT).reasons[0] == "Wind 54.6 mph → Severe"


def test_levels_and_helper():
    assert LEVELS == ("low", "moderate", "high", "severe", "no_travel")
    assert level_for(0, DEFAULT_RULES.wind_mph) == "low"
