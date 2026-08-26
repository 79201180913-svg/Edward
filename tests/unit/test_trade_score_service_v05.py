import pytest

from edward.services.trade_score_service import TradeScoreInput, TradeScoreService


def _data(**overrides):
    values = dict(
        strategy_score=80,
        forecast_score=70,
        risk_score=60,
        opportunity_score=90,
        portfolio_fit_score=75,
        confidence_score=80,
        forecast_quality_pass=True,
    )
    values.update(overrides)
    return TradeScoreInput(**values)


def test_trade_score_uses_all_components():
    result = TradeScoreService.calculate(_data())

    assert result.score > 0
    assert result.forecast_used is True
    assert result.blocked is False
    assert result.reasons == ()
    assert result.strategy_component > 0
    assert result.forecast_component > 0
    assert result.risk_component > 0


def test_forecast_gate_fail_blocks_forecast_usage():
    result = TradeScoreService.calculate(_data(forecast_quality_pass=False, forecast_score=99))

    assert result.forecast_used is False
    assert result.blocked is True
    assert result.forecast_component == 0
    assert result.score < TradeScoreService.calculate(_data(forecast_quality_pass=True, forecast_score=99)).score
    assert result.reasons == ("FORECAST_QUALITY_GATE_FAIL",)


def test_custom_weights_are_normalized():
    result = TradeScoreService.calculate(
        _data(),
        weights={"strategy": 1, "forecast": 1, "risk": 0, "opportunity": 0, "portfolio_fit": 0, "confidence": 0},
    )

    assert result.score == pytest.approx(75.0)


def test_negative_weight_is_rejected():
    with pytest.raises(ValueError, match="не может быть отрицательным"):
        TradeScoreService.calculate(_data(), weights={"risk": -1})


def test_zero_total_weight_is_rejected():
    with pytest.raises(ValueError, match="положительной"):
        TradeScoreService.calculate(
            _data(),
            weights={
                "strategy": 0,
                "forecast": 0,
                "risk": 0,
                "opportunity": 0,
                "portfolio_fit": 0,
                "confidence": 0,
            },
        )


def test_inputs_are_clamped_to_score_range():
    result = TradeScoreService.calculate(
        _data(
            strategy_score=150,
            forecast_score=-10,
            risk_score=120,
            opportunity_score=-5,
            portfolio_fit_score=200,
            confidence_score=-20,
        )
    )

    assert 0 <= result.score <= 100
