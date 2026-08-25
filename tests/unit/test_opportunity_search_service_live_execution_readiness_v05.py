from types import SimpleNamespace

from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


def result(*, decision="REDUCE", reason="STRATEGY_QUALITY_FAIL", execution_ready=True, risk_reward=-1.58, recommended_quantity=1000):
    plan = SimpleNamespace(risk_reward=risk_reward) if risk_reward is not None else None
    return SimpleNamespace(
        decision=decision,
        reason=reason,
        execution_ready=execution_ready,
        trade_plan=plan,
        recommended_quantity=recommended_quantity,
    )


def test_reduce_with_failed_strategy_and_negative_rr_is_not_execution_ready():
    checked = LiveOpportunitySearchService._enforce_execution_readiness(result())
    assert checked.execution_ready is False


def test_sell_with_zero_reduction_quantity_is_not_execution_ready():
    checked = LiveOpportunitySearchService._enforce_execution_readiness(
        result(decision="SELL", reason="EXIT_SIGNAL", risk_reward=2.0, recommended_quantity=0)
    )
    assert checked.execution_ready is False


def test_positive_actionable_plan_can_remain_execution_ready():
    checked = LiveOpportunitySearchService._enforce_execution_readiness(
        result(decision="REDUCE", reason="EXIT_SIGNAL", risk_reward=1.5, recommended_quantity=100)
    )
    assert checked.execution_ready is True
