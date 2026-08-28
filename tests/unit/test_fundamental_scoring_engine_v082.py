from edward.services.fundamental_scoring_engine_v082 import FundamentalScoringEngineV082


def test_growth_is_bounded():
    assert FundamentalScoringEngineV082.growth(1000) == 100.0
    assert FundamentalScoringEngineV082.growth(-1000) == 0.0


def test_high_roe_with_high_leverage_is_penalized():
    assert FundamentalScoringEngineV082.roe_quality_adjustment(30.0, 0.5) == 0.0
    assert FundamentalScoringEngineV082.roe_quality_adjustment(30.0, 3.0) == 5.0


def test_profitability_metrics_have_metric_specific_scales():
    assert FundamentalScoringEngineV082.profitability(20.0, kind="roe") == 74.0
    assert FundamentalScoringEngineV082.profitability(20.0, kind="roic") == 78.0
    assert FundamentalScoringEngineV082.profitability(10.0, kind="roa") == 75.0
    assert FundamentalScoringEngineV082.profitability(10.0, kind="net_margin") == 64.0


def test_profitability_handles_negative_and_extreme_values():
    assert FundamentalScoringEngineV082.profitability(-100.0, kind="roe") == 15.0
    assert FundamentalScoringEngineV082.profitability(1000.0, kind="roic") == 98.0


def test_unknown_profitability_metric_is_rejected():
    try:
        FundamentalScoringEngineV082.profitability(10.0, kind="unknown")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported profitability metric must raise ValueError")


def test_growth_acceleration_uses_available_period_pairs():
    assert FundamentalScoringEngineV082.growth_acceleration(5.0, 10.0, 20.0) == 7.5
    assert FundamentalScoringEngineV082.growth_acceleration(None, 10.0, 20.0) == 10.0


def test_momentum_does_not_equal_raw_growth_average():
    score = FundamentalScoringEngineV082.momentum(5.0, 10.0, 20.0, 15.0, 18.0)
    assert score > 50.0
    assert score != (FundamentalScoringEngineV082.growth(5.0) + FundamentalScoringEngineV082.growth(10.0) + FundamentalScoringEngineV082.growth(20.0)) / 3


def test_acceleration_classification():
    assert FundamentalScoringEngineV082.classify_acceleration(4.0) == "FUNDAMENTAL_ACCELERATION"
    assert FundamentalScoringEngineV082.classify_acceleration(-4.0) == "FUNDAMENTAL_DECELERATION"
    assert FundamentalScoringEngineV082.classify_acceleration(1.0) == "FUNDAMENTAL_STABLE"
