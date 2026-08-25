from __future__ import annotations

from edward.services.decision_engine import (
    Decision,
    DecisionEngine,
    DecisionRequest,
    DecisionStatus,
    OpportunityContext,
    PositionContextData,
    Scenario,
)


def _new_position_request(**kwargs) -> DecisionRequest:
    opportunity = kwargs.pop(
        "opportunity",
        OpportunityContext(
            opportunity_score=82.0,
            entry_ok=True,
            risk_ok=True,
            strategy_ok=True,
            market_regime_compatible=True,
        ),
    )
    return DecisionRequest(
        scenario=Scenario.SINGLE_INSTRUMENT,
        strategy_name="Momentum",
        strategy_score=86.0,
        strategy_quality=True,
        opportunity=opportunity,
        portfolio_allows_buy=True,
        **kwargs,
    )


def _open_position_request(**kwargs) -> DecisionRequest:
    opportunity = kwargs.pop(
        "opportunity",
        OpportunityContext(
            opportunity_score=80.0,
            entry_ok=True,
            risk_ok=True,
            strategy_ok=True,
            market_regime_compatible=True,
        ),
    )
    return DecisionRequest(
        strategy_name="Momentum",
        strategy_score=86.0,
        strategy_quality=True,
        opportunity=opportunity,
        portfolio_allows_buy=True,
        portfolio_allows_add=True,
        position=PositionContextData(quantity=100, portfolio_weight_pct=5.0, target_weight_pct=10.0),
        **kwargs,
    )


def test_no_position_buy_requires_portfolio_gate():
    result = DecisionEngine.evaluate(_new_position_request())
    assert result.decision == Decision.BUY
    assert result.status == DecisionStatus.VALID

    blocked = DecisionEngine.evaluate(_new_position_request(portfolio_allows_buy=False))
    assert blocked.decision == Decision.PASS
    assert "PORTFOLIO_CONSTRAINT" in blocked.reason_codes


def test_no_position_wait_when_entry_not_ready():
    result = DecisionEngine.evaluate(
        _new_position_request(
            opportunity=OpportunityContext(
                opportunity_score=88.0,
                entry_ok=False,
                risk_ok=True,
                strategy_ok=True,
                market_regime_compatible=True,
            )
        )
    )
    assert result.decision == Decision.WAIT
    assert "ENTRY_NOT_READY" in result.reason_codes


def test_no_position_wait_when_market_regime_is_unfavorable():
    result = DecisionEngine.evaluate(
        _new_position_request(
            opportunity=OpportunityContext(
                opportunity_score=90.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
                market_regime_compatible=False,
            )
        )
    )
    assert result.decision == Decision.WAIT
    assert "MARKET_REGIME_UNFAVORABLE" in result.reason_codes


def test_no_position_pass_without_strategy_is_business_decision():
    result = DecisionEngine.evaluate(
        _new_position_request(
            strategy_name=None,
            strategy_score=42.0,
            strategy_quality=False,
            opportunity=OpportunityContext(
                opportunity_score=35.0,
                entry_ok=False,
                risk_ok=True,
                strategy_ok=False,
                market_regime_compatible=True,
            ),
        )
    )
    assert result.decision == Decision.PASS
    assert result.status == DecisionStatus.VALID


def test_analysis_unavailable_has_no_trading_decision():
    result = DecisionEngine.evaluate(_new_position_request(market_data_available=False))
    assert result.status == DecisionStatus.ANALYSIS_UNAVAILABLE
    assert result.decision is None
    assert "MARKET_DATA_UNAVAILABLE" in result.reason_codes


def test_invalid_profile_is_not_converted_to_trade_decision():
    result = DecisionEngine.evaluate(_new_position_request(profile="unknown"))
    assert result.status == DecisionStatus.ANALYSIS_UNAVAILABLE
    assert result.decision is None
    assert "UNSUPPORTED_PROFILE" in result.reason_codes


def test_open_position_sell_has_priority_over_add():
    result = DecisionEngine.evaluate(_open_position_request(exit_signal=True))
    assert result.decision == Decision.SELL


def test_open_position_critical_risk_has_sell_priority():
    result = DecisionEngine.evaluate(
        _open_position_request(
            opportunity=OpportunityContext(
                opportunity_score=90.0,
                entry_ok=True,
                risk_ok=False,
                strategy_ok=True,
                market_regime_compatible=True,
                critical_risk=True,
            )
        )
    )
    assert result.decision == Decision.SELL
    assert "CRITICAL_RISK" in result.reason_codes


def test_open_position_reduce_on_risk_deterioration():
    result = DecisionEngine.evaluate(
        _open_position_request(
            opportunity=OpportunityContext(
                opportunity_score=80.0,
                entry_ok=True,
                risk_ok=False,
                strategy_ok=True,
                market_regime_compatible=True,
                critical_risk=False,
            )
        )
    )
    assert result.decision == Decision.REDUCE
    assert "RISK_DETERIORATION" in result.reason_codes


def test_open_position_reduce_on_strategy_quality_failure():
    result = DecisionEngine.evaluate(
        _open_position_request(
            strategy_quality=False,
            opportunity=OpportunityContext(
                opportunity_score=80.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=False,
                market_regime_compatible=True,
            ),
        )
    )
    assert result.decision == Decision.REDUCE
    assert "STRATEGY_QUALITY_FAIL" in result.reason_codes


def test_open_position_reduce_on_strategy_quality_degradation():
    result = DecisionEngine.evaluate(_open_position_request(strategy_quality_degraded=True))
    assert result.decision == Decision.REDUCE
    assert "STRATEGY_QUALITY_DEGRADED" in result.reason_codes


def test_open_position_reduce_on_signal_degradation():
    result = DecisionEngine.evaluate(_open_position_request(signal_degraded=True))
    assert result.decision == Decision.REDUCE
    assert "SIGNAL_DEGRADED" in result.reason_codes


def test_open_position_reduce_on_unfavorable_market_regime():
    result = DecisionEngine.evaluate(
        _open_position_request(
            opportunity=OpportunityContext(
                opportunity_score=80.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
                market_regime_compatible=False,
            )
        )
    )
    assert result.decision == Decision.REDUCE
    assert "MARKET_REGIME_UNFAVORABLE" in result.reason_codes


def test_open_position_reduce_when_above_target():
    result = DecisionEngine.evaluate(
        _open_position_request(
            position=PositionContextData(quantity=100, portfolio_weight_pct=18.0, target_weight_pct=10.0)
        )
    )
    assert result.decision == Decision.REDUCE
    assert "POSITION_ABOVE_TARGET" in result.reason_codes


def test_open_position_add_when_below_target():
    result = DecisionEngine.evaluate(
        _open_position_request(
            opportunity=OpportunityContext(
                opportunity_score=84.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
                market_regime_compatible=True,
            )
        )
    )
    assert result.decision == Decision.ADD


def test_open_position_hold_only_when_strategy_and_risk_are_ok():
    result = DecisionEngine.evaluate(
        _open_position_request(
            opportunity=OpportunityContext(
                opportunity_score=58.0,
                entry_ok=False,
                risk_ok=True,
                strategy_ok=True,
                market_regime_compatible=True,
            )
        )
    )
    assert result.decision == Decision.HOLD


def test_open_position_portfolio_context_is_required():
    result = DecisionEngine.evaluate(_open_position_request(portfolio_context_available=False))
    assert result.status == DecisionStatus.ANALYSIS_UNAVAILABLE
    assert result.decision is None
    assert "PORTFOLIO_CONTEXT_UNAVAILABLE" in result.reason_codes


def test_ranking_orders_buy_wait_pass():
    requests = [
        _new_position_request(
            strategy_name="Pass",
            strategy_quality=False,
            opportunity=OpportunityContext(opportunity_score=95.0, risk_ok=True, strategy_ok=False),
        ),
        _new_position_request(
            strategy_name="Wait",
            strategy_quality=True,
            opportunity=OpportunityContext(opportunity_score=55.0, entry_ok=True, risk_ok=True, strategy_ok=True),
        ),
        _new_position_request(
            strategy_name="Buy",
            strategy_quality=True,
            opportunity=OpportunityContext(opportunity_score=90.0, entry_ok=True, risk_ok=True, strategy_ok=True),
        ),
    ]
    results = DecisionEngine.rank_opportunities(requests)
    assert [item.decision for item in results] == [Decision.BUY, Decision.WAIT, Decision.PASS]


def test_main_opportunities_excludes_pass():
    requests = [
        _new_position_request(
            strategy_name="Pass",
            strategy_quality=False,
            opportunity=OpportunityContext(opportunity_score=95.0, risk_ok=True, strategy_ok=False),
        ),
        _new_position_request(
            strategy_name="Wait",
            strategy_quality=True,
            opportunity=OpportunityContext(opportunity_score=55.0, entry_ok=True, risk_ok=True, strategy_ok=True),
        ),
        _new_position_request(
            strategy_name="Buy",
            strategy_quality=True,
            opportunity=OpportunityContext(opportunity_score=90.0, entry_ok=True, risk_ok=True, strategy_ok=True),
        ),
    ]
    results = DecisionEngine.main_opportunities(requests)
    assert [item.decision for item in results] == [Decision.BUY, Decision.WAIT]
