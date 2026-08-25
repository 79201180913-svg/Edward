from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle, StrategyResult
from edward.services.risk_engine import RiskEngine


def _candles(count: int = 260, daily_return: float = 0.001) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    result: list[Candle] = []
    for index in range(count):
        previous = price
        price *= 1.0 + daily_return
        result.append(Candle(start + timedelta(days=index), previous, price, previous, price, 1000.0))
    return result


def _strategy(*, dd: float = 8.0, sharpe: float = 1.0) -> StrategyResult:
    return StrategyResult("Momentum", {"lookback": 20}, 12.0, dd, sharpe, 20, 70.0, True, 72.0)


def test_risk_engine_passes_reasonable_strategy_and_portfolio():
    result = RiskEngine.evaluate(
        strategy_result=_strategy(),
        candles=_candles(),
        profile="medium_term",
        position_weight_pct=5.0,
        target_weight_pct=10.0,
        max_position_weight_pct=15.0,
        portfolio_available=True,
        available_cash=100000.0,
        estimated_trade_value=5000.0,
    )

    assert result.gate is True
    assert result.critical is False
    assert result.score >= 50.0
    assert result.portfolio_fit_score == 100.0


def test_risk_engine_blocks_excessive_drawdown():
    result = RiskEngine.evaluate(
        strategy_result=_strategy(dd=35.0),
        candles=_candles(),
        profile="medium_term",
        position_weight_pct=5.0,
        target_weight_pct=10.0,
        max_position_weight_pct=15.0,
        portfolio_available=True,
    )

    assert result.gate is False
    assert "MAX_DRAWDOWN_LIMIT" in result.reasons


def test_risk_engine_blocks_position_weight_limit():
    result = RiskEngine.evaluate(
        strategy_result=_strategy(),
        candles=_candles(),
        profile="medium_term",
        position_weight_pct=25.0,
        target_weight_pct=10.0,
        max_position_weight_pct=15.0,
        portfolio_available=True,
    )

    assert result.gate is False
    assert "POSITION_WEIGHT_LIMIT" in result.reasons
