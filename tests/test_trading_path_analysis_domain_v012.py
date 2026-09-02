import pytest

from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathAnalysisV012,
    TradingPathCurrentState,
    TradingPathDecision,
    TradingPathMarketContext,
    TradingPathOpportunity,
    TradingPathValidationSummary,
)


def test_v012_analysis_contract_is_path_centric():
    evidence = object()
    result = TradingPathAnalysisV012(
        instrument_uid="uid-1",
        ticker="SBER",
        strategy_family="Momentum",
        hypothesis="IMPULSE_CONTINUATION",
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=5,
        evidence=evidence,
        validation=TradingPathValidationSummary(
            wf_persistence_pct=81.0,
            robustness_score=72.0,
            positive_oos_windows_pct=80.0,
        ),
        market_context=TradingPathMarketContext(
            benchmark_id="IMOEX",
            baseline_rank=2,
            context_rank=1,
            rank_delta=1,
        ),
        opportunity=TradingPathOpportunity(
            score=74.0,
            confidence=68.0,
            expected_value_pct=0.82,
            risk_score=31.0,
            risk_gate=True,
        ),
        current_state=TradingPathCurrentState.ENTRY_READY,
        decision=TradingPathDecision.BUY,
        status=TradingPathAnalysisStatus.PROMOTABLE,
        rank=1,
    )

    assert result.strategy_family == "Momentum"
    assert result.hypothesis == "IMPULSE_CONTINUATION"
    assert result.direction == "Positive"
    assert result.horizon == 5
    assert result.market_context.context_rank == 1
    assert result.opportunity.expected_value_pct == pytest.approx(0.82)
    assert result.decision is TradingPathDecision.BUY


def test_v012_statistical_integrity_snapshot_is_exposed():
    result = TradingPathAnalysisV012(
        instrument_uid="uid-stat",
        ticker="SBER",
        strategy_family="Adaptive Discovery",
        hypothesis="ADAPTIVE_RULE:regime=TREND_UP AND return_5 >= 1.5",
        regime="TREND_UP",
        volatility_bucket="Adaptive",
        direction="Positive",
        horizon=5,
        evidence=object(),
        validation=TradingPathValidationSummary(
            statistical_valid=True,
            overlap_valid=True,
            multiple_testing_valid=True,
            effective_sample_size=18.0,
            overlap_ratio_pct=80.0,
            standard_error_pct=0.42,
            z_score=2.15,
            p_value_one_sided=0.016,
            adjusted_p_value=0.032,
            hypotheses_tested=24,
        ),
    )

    assert result.validation.statistical_valid is True
    assert result.validation.overlap_valid is True
    assert result.validation.multiple_testing_valid is True
    assert result.validation.effective_sample_size == pytest.approx(18.0)
    assert result.validation.overlap_ratio_pct == pytest.approx(80.0)
    assert result.validation.standard_error_pct == pytest.approx(0.42)
    assert result.validation.z_score == pytest.approx(2.15)
    assert result.validation.p_value_one_sided == pytest.approx(0.016)
    assert result.validation.adjusted_p_value == pytest.approx(0.032)
    assert result.validation.hypotheses_tested == 24


def test_v012_defaults_do_not_create_a_trading_signal():
    result = TradingPathAnalysisV012(
        instrument_uid="uid-2",
        ticker="GAZP",
        strategy_family="Breakout",
        hypothesis="BREAKOUT_EXPANSION",
        regime="TREND_UP",
        volatility_bucket="High",
        direction="Positive",
        horizon=3,
        evidence=object(),
    )

    assert result.status is TradingPathAnalysisStatus.DISCOVERED
    assert result.current_state is TradingPathCurrentState.WAIT
    assert result.decision is TradingPathDecision.WAIT
    assert result.opportunity.score is None


def test_v012_contract_is_immutable():
    result = TradingPathAnalysisV012(
        instrument_uid="uid-3",
        ticker="RANGE",
        strategy_family="Mean Reversion",
        hypothesis="RANGE_REVERSAL",
        regime="RANGE",
        volatility_bucket="Low",
        direction="Positive",
        horizon=10,
        evidence=object(),
    )

    with pytest.raises((AttributeError, TypeError)):
        result.ticker = "OTHER"
