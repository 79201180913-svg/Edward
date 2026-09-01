from edward.domain import (
    TradingPathCandidate,
    TradingPathEvidence,
    TradingPathRule,
    TradingPathStatus,
)
from edward.services.analysis_service_v08 import AnalysisV08Diagnostics


def _candidate() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid-1",
            ticker="SBER",
            hypothesis="BREAKOUT_EXPANSION",
            regime="TREND_UP",
            volatility_bucket="Normal",
            direction="Positive",
            horizon=5,
        ),
        evidence=TradingPathEvidence(
            observations=25,
            mean_forward_return_pct=1.4,
            median_forward_return_pct=1.1,
            win_rate_pct=64.0,
            baseline_mean_return_pct=0.3,
            excess_return_pct=1.1,
            sufficient_sample=True,
        ),
    )


def test_analysis_diagnostics_can_carry_trading_path_candidates():
    candidate = _candidate()
    diagnostics = AnalysisV08Diagnostics(
        regime_confidence=82.0,
        regime="TREND_UP",
        robustness_by_strategy={},
        quality_gate_by_strategy={},
        trading_path_candidates=(candidate,),
    )

    assert len(diagnostics.trading_path_candidates) == 1
    assert diagnostics.trading_path_candidates[0].rule.ticker == "SBER"
    assert diagnostics.trading_path_candidates[0].rule.hypothesis == "BREAKOUT_EXPANSION"
    assert diagnostics.trading_path_candidates[0].status is TradingPathStatus.RESEARCH


def test_analysis_diagnostics_default_has_no_candidates():
    diagnostics = AnalysisV08Diagnostics(
        regime_confidence=0.0,
        regime="UNKNOWN",
        robustness_by_strategy={},
        quality_gate_by_strategy={},
    )

    assert diagnostics.trading_path_candidates == ()
