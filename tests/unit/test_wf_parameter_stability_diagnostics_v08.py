from __future__ import annotations

from types import SimpleNamespace

from edward.services.wf_parameter_stability_diagnostics_v08 import (
    neighborhood_stability_pct,
    parameter_key,
    selection_confidence,
    winner_margin_pct,
)


def result(excess: float):
    return SimpleNamespace(excess_return_pct=excess)


def test_parameter_key_is_stable():
    assert parameter_key({"slow": 50, "fast": 20}) == (("fast", 20), ("slow", 50))


def test_winner_margin_is_zero_when_top_two_are_equal():
    candidates = [({"p": 1}, result(10.0)), ({"p": 2}, result(10.0))]
    assert winner_margin_pct(candidates) == 0.0


def test_winner_margin_rewards_clear_winner():
    candidates = [({"p": 1}, result(20.0)), ({"p": 2}, result(10.0))]
    assert winner_margin_pct(candidates) == 50.0


def test_neighborhood_stability_detects_supporting_neighbors():
    candidates = [
        ({"lookback": 20}, result(10.0)),
        ({"lookback": 30}, result(9.0)),
        ({"lookback": 40}, result(8.0)),
    ]
    stability, count = neighborhood_stability_pct({"lookback": 20}, candidates)
    assert count == 1
    assert stability == 90.0


def test_selection_confidence_is_mean_of_margin_and_neighborhood():
    assert selection_confidence(80.0, 60.0) == 70.0
