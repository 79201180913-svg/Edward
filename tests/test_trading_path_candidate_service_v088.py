from edward.services.conditional_discovery_service_v086 import (
    ConditionalDiscoveryCell,
    ConditionalDiscoveryEvidence,
    ConditionalDiscoveryResult,
)
from edward.services.trading_path_candidate_service_v088 import TradingPathCandidateServiceV088


def _cell(*, sufficient: bool, excess: float = 1.0, hypothesis: str = "BREAKOUT_EXPANSION") -> ConditionalDiscoveryCell:
    return ConditionalDiscoveryCell(hypothesis, "TREND_DOWN", "High", "Positive", 3, 10 if sufficient else 2, 1.2, 1.0, 70.0, 0.2, excess, sufficient)


def _result(*cells: ConditionalDiscoveryCell) -> ConditionalDiscoveryResult:
    return ConditionalDiscoveryResult("0.8.6", 1768, 8, (ConditionalDiscoveryEvidence(cells[0].hypothesis, len(cells), tuple(cells)),))


def test_promotes_only_sufficient_positive_cells():
    candidates = TradingPathCandidateServiceV088.promote(
        _result(_cell(sufficient=True), _cell(sufficient=False, excess=22.4), _cell(sufficient=True, excess=-0.5)),
        instrument_uid="uid-1",
        ticker="SBER",
    )
    assert len(candidates) == 1
    assert candidates[0].status.value == "research"
    assert candidates[0].evidence.observations == 10


def test_promotion_preserves_instrument_and_conditional_dimensions():
    candidate = TradingPathCandidateServiceV088.promote(
        _result(_cell(sufficient=True, hypothesis="GAP_REVERSAL")), instrument_uid="uid-2", ticker="GAZP"
    )[0]
    assert candidate.rule.instrument_uid == "uid-2"
    assert candidate.rule.ticker == "GAZP"
    assert candidate.rule.hypothesis == "GAP_REVERSAL"
    assert candidate.rule.regime == "TREND_DOWN"
    assert candidate.rule.volatility_bucket == "High"
    assert candidate.rule.direction == "Positive"
    assert candidate.rule.horizon == 3


def test_promotion_never_produces_trade_status():
    candidate = TradingPathCandidateServiceV088.promote(
        _result(_cell(sufficient=True, excess=5.0)), instrument_uid="uid-3", ticker="SBER"
    )[0]
    assert candidate.status.value == "research"
