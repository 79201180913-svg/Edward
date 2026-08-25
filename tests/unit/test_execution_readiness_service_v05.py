import pytest

from edward.services.execution_readiness_service import (
    ExecutionReadinessInput,
    ExecutionReadinessService,
)


def base_input(**overrides):
    data = dict(
        decision="BUY",
        forecast_quality_pass=True,
        risk_ok=True,
        portfolio_available=True,
        trading_status_ok=True,
        position_size_ready=True,
        entry_ready=True,
        target_ready=True,
        stop_ready=True,
        liquidity_ok=True,
        strategy_quality_pass=True,
        risk_reward_ok=True,
    )
    data.update(overrides)
    return ExecutionReadinessInput(**data)


def test_execution_is_ready_when_all_gates_pass():
    result = ExecutionReadinessService.evaluate(base_input())
    assert result.execution_ready is True
    assert result.reasons == ()


@pytest.mark.parametrize(
    "field,reason",
    [
        ("forecast_quality_pass", "FORECAST_QUALITY_GATE_FAIL"),
        ("risk_ok", "RISK_NOT_OK"),
        ("portfolio_available", "PORTFOLIO_NOT_AVAILABLE"),
        ("trading_status_ok", "TRADING_STATUS_NOT_OK"),
        ("position_size_ready", "POSITION_SIZE_NOT_READY"),
        ("entry_ready", "ENTRY_NOT_READY"),
        ("target_ready", "TARGET_NOT_READY"),
        ("stop_ready", "STOP_NOT_READY"),
        ("liquidity_ok", "LIQUIDITY_NOT_OK"),
        ("strategy_quality_pass", "STRATEGY_QUALITY_GATE_FAIL"),
        ("risk_reward_ok", "RISK_REWARD_NOT_ACCEPTABLE"),
    ],
)
def test_each_blocking_gate_is_reported(field, reason):
    result = ExecutionReadinessService.evaluate(base_input(**{field: False}))
    assert result.execution_ready is False
    assert reason in result.reasons


def test_hold_does_not_require_trade_entry_and_target_or_stop():
    result = ExecutionReadinessService.evaluate(
        base_input(
            decision="HOLD",
            entry_ready=False,
            target_ready=False,
            stop_ready=False,
            position_size_ready=False,
            liquidity_ok=False,
            strategy_quality_pass=False,
            risk_reward_ok=False,
        )
    )
    assert result.execution_ready is True


def test_sell_does_not_require_forecast_quality_or_portfolio_available():
    result = ExecutionReadinessService.evaluate(
        base_input(
            decision="SELL",
            forecast_quality_pass=False,
            portfolio_available=False,
        )
    )
    assert result.execution_ready is True


def test_sell_requires_strategy_quality_and_positive_risk_reward():
    result = ExecutionReadinessService.evaluate(
        base_input(
            decision="SELL",
            strategy_quality_pass=False,
            risk_reward_ok=False,
        )
    )
    assert result.execution_ready is False
    assert "STRATEGY_QUALITY_GATE_FAIL" in result.reasons
    assert "RISK_REWARD_NOT_ACCEPTABLE" in result.reasons


def test_invalid_decision_is_rejected():
    result = ExecutionReadinessService.evaluate(base_input(decision="WAIT"))
    assert result.execution_ready is False
    assert "INVALID_DECISION" in result.reasons
