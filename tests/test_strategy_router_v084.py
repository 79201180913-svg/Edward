from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.regime_engine_v08 import RegimeEngine, RegimeResult
from edward.services.strategy_router_v084 import StrategyRouterV084


def _regime(name: str, confidence: float = 70.0) -> RegimeResult:
    return RegimeResult(name, 0.0, 1.0, 50.0, confidence)


def test_trend_up_prioritizes_trend_strategies() -> None:
    result = StrategyRouterV084.route(_regime("TREND_UP"))
    assert result.ordered_strategies[0] == "Trend Following"
    assert result.ordered_strategies[-1] == "Mean Reversion"
    decisions = {item.strategy: item for item in result.decisions}
    assert decisions["Trend Following"].priority == "HIGH"
    assert decisions["Mean Reversion"].priority == "LOW"
    assert decisions["Trend Following"].eligible is True


def test_range_prioritizes_mean_reversion() -> None:
    result = StrategyRouterV084.route(_regime("RANGE"))
    assert result.ordered_strategies[0] == "Mean Reversion"
    decision = next(item for item in result.decisions if item.strategy == "Mean Reversion")
    assert decision.compatibility == 100.0
    assert decision.priority == "HIGH"


def test_transition_does_not_hard_disable_strategies() -> None:
    result = StrategyRouterV084.route(_regime("TRANSITION"))
    assert all(item.eligible for item in result.decisions)
    assert all(item.evidence_multiplier < 1.0 for item in result.decisions)
    assert all(item.priority != "HIGH" for item in result.decisions)


def test_unknown_regime_is_not_trade_eligible() -> None:
    result = StrategyRouterV084.route(_regime("UNKNOWN"))
    assert all(item.eligible is False for item in result.decisions)
    assert all(item.evidence_multiplier < 1.0 for item in result.decisions)


def test_router_uses_existing_regime_compatibility_table() -> None:
    result = StrategyRouterV084.route(_regime("HIGH_VOLATILITY"))
    expected = {strategy: RegimeEngine.compatibility("HIGH_VOLATILITY", strategy) for strategy in StrategyRouterV084.STRATEGIES}
    actual = {item.strategy: item.compatibility for item in result.decisions}
    assert actual == expected
