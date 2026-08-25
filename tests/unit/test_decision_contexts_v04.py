from edward.services.decision_engine import (
    Decision,
    DecisionEngine,
    DecisionRequest,
    DecisionStatus,
    InstrumentContextData,
    MarketContextData,
    OpportunityContext,
    PortfolioContextData,
    PositionContextData,
    RiskContextData,
    Scenario,
    StrategyContextData,
)


def _context_request(**kwargs) -> DecisionRequest:
    values = {
        "scenario": Scenario.SINGLE_INSTRUMENT,
        "instrument": InstrumentContextData(
            instrument_uid="uid-1",
            ticker="TEST",
            buy_available=True,
            sell_available=True,
        ),
        "market": MarketContextData(
            current_price=100.0,
            close_price=99.0,
            market_regime="Trend",
            trend="UP",
            momentum="POSITIVE",
            volatility=0.02,
            entry_level=100.0,
            stop_level=95.0,
            target_level=115.0,
            regime_compatible=True,
            entry_ok=True,
        ),
        "strategy": StrategyContextData(
            strategy_id="momentum-v1",
            strategy_name="Momentum",
            strategy_score=86.0,
            walk_forward_score=84.0,
            stability_score=82.0,
            confidence="High",
            quality_gate=True,
            entry_signal=True,
            exit_signal=False,
        ),
        "risk": RiskContextData(
            risk_gate=True,
            critical_risk=False,
            risk_score=18.0,
            max_drawdown_pct=12.0,
            risk_reward=2.5,
        ),
        "position": PositionContextData(),
        "portfolio": PortfolioContextData(
            portfolio_value=100000.0,
            available_cash=50000.0,
            blocked_cash=0.0,
            current_weight_pct=0.0,
            target_weight_pct=10.0,
            max_position_weight_pct=15.0,
            allows_buy=True,
            allows_add=True,
        ),
        "opportunity": OpportunityContext(
            opportunity_score=82.0,
            entry_ok=True,
            risk_ok=True,
            strategy_ok=True,
            market_regime_compatible=True,
            critical_risk=False,
        ),
        "portfolio_allows_buy": True,
        "portfolio_allows_add": True,
    }
    values.update(kwargs)
    return DecisionRequest(**values)


def test_structured_contexts_can_drive_buy():
    result = DecisionEngine.evaluate(_context_request())
    assert result.decision == Decision.BUY
    assert result.status == DecisionStatus.VALID
    assert result.strategy_name == "Momentum"
    assert result.strategy_score == 86.0
    assert result.opportunity_score == 82.0


def test_market_context_blocks_new_position_with_wait():
    result = DecisionEngine.evaluate(
        _context_request(
            market=MarketContextData(
                current_price=100.0,
                market_regime="Range",
                trend="FLAT",
                momentum="NEUTRAL",
                volatility=0.01,
                regime_compatible=False,
                entry_ok=True,
            ),
            opportunity=OpportunityContext(
                opportunity_score=90.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
                market_regime_compatible=False,
            ),
        )
    )
    assert result.decision == Decision.WAIT
    assert "MARKET_REGIME_UNFAVORABLE" in result.reason_codes


def test_risk_context_has_sell_priority_for_open_position():
    result = DecisionEngine.evaluate(
        _context_request(
            position=PositionContextData(quantity=100, portfolio_weight_pct=8.0, target_weight_pct=10.0),
            risk=RiskContextData(risk_gate=False, critical_risk=True, risk_score=95.0),
            opportunity=OpportunityContext(
                opportunity_score=85.0,
                entry_ok=True,
                risk_ok=False,
                strategy_ok=True,
                market_regime_compatible=True,
                critical_risk=True,
            ),
        )
    )
    assert result.decision == Decision.SELL
    assert "CRITICAL_RISK" in result.reason_codes


def test_strategy_context_degradation_reduces_open_position():
    result = DecisionEngine.evaluate(
        _context_request(
            position=PositionContextData(quantity=100, portfolio_weight_pct=8.0, target_weight_pct=10.0),
            strategy=StrategyContextData(
                strategy_id="momentum-v1",
                strategy_name="Momentum",
                strategy_score=62.0,
                quality_gate=True,
                quality_degraded=True,
                signal_degraded=False,
            ),
            opportunity=OpportunityContext(
                opportunity_score=72.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
                market_regime_compatible=True,
            ),
        )
    )
    assert result.decision == Decision.REDUCE
    assert "STRATEGY_QUALITY_DEGRADED" in result.reason_codes


def test_portfolio_context_limits_position_size():
    result = DecisionEngine.evaluate(
        _context_request(
            position=PositionContextData(quantity=100, portfolio_weight_pct=16.0, target_weight_pct=10.0),
            portfolio=PortfolioContextData(
                portfolio_value=100000.0,
                available_cash=20000.0,
                current_weight_pct=16.0,
                target_weight_pct=10.0,
                max_position_weight_pct=15.0,
                allows_buy=True,
                allows_add=False,
            ),
            portfolio_allows_add=False,
        )
    )
    assert result.decision == Decision.REDUCE
    assert "POSITION_ABOVE_TARGET" in result.reason_codes


def test_instrument_buy_unavailable_blocks_buy():
    result = DecisionEngine.evaluate(
        _context_request(
            instrument=InstrumentContextData(
                instrument_uid="uid-1",
                ticker="TEST",
                buy_available=False,
                sell_available=True,
            )
        )
    )
    assert result.decision == Decision.PASS
    assert "INSTRUMENT_BUY_UNAVAILABLE" in result.reason_codes


def test_nested_market_unavailable_returns_technical_state():
    result = DecisionEngine.evaluate(
        _context_request(
            market=MarketContextData(available=False),
            market_data_available=True,
        )
    )
    assert result.status == DecisionStatus.ANALYSIS_UNAVAILABLE
    assert result.decision is None
    assert "MARKET_DATA_UNAVAILABLE" in result.reason_codes


def test_open_position_without_portfolio_context_is_unavailable():
    result = DecisionEngine.evaluate(
        _context_request(
            position=PositionContextData(quantity=50),
            portfolio=PortfolioContextData(available=False),
        )
    )
    assert result.status == DecisionStatus.ANALYSIS_UNAVAILABLE
    assert result.decision is None
    assert "PORTFOLIO_CONTEXT_UNAVAILABLE" in result.reason_codes
