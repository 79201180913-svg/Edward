from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012, TradingPathAnalysisStatus, TradingPathCurrentState, TradingPathDecision
from edward.services.opportunity_consumer_facade_v013 import OpportunityConsumerFacadeV013


def _analysis(uid: str, ticker: str, rank: int, decision: TradingPathDecision):
    return TradingPathAnalysisV012(
        instrument_uid=uid,
        ticker=ticker,
        strategy_family="H1",
        hypothesis="H1",
        regime="RANGE",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=5,
        evidence=SimpleNamespace(),
        validation=SimpleNamespace(),
        market_context=SimpleNamespace(),
        opportunity=SimpleNamespace(score=70.0, confidence=80.0),
        current_state=TradingPathCurrentState.ENTRY_READY,
        decision=decision,
        status=TradingPathAnalysisStatus.PROMOTABLE,
        rank=rank,
    )


def test_facade_returns_one_opportunity_per_instrument():
    result = OpportunityConsumerFacadeV013.from_analyses([
        _analysis("SBER", "SBER", 2, TradingPathDecision.WAIT),
        _analysis("SBER", "SBER", 1, TradingPathDecision.BUY),
        _analysis("GAZP", "GAZP", 1, TradingPathDecision.PASS),
    ])

    assert [(item.instrument_uid, item.decision) for item in result] == [
        ("GAZP", TradingPathDecision.PASS),
        ("SBER", TradingPathDecision.BUY),
    ]


def test_facade_does_not_mutate_or_recalculate_analysis():
    analysis = _analysis("SBER", "SBER", 1, TradingPathDecision.BUY)
    result = OpportunityConsumerFacadeV013.from_analyses([analysis])

    assert result[0].best_path is analysis
    assert result[0].best_path.opportunity.score == 70.0
    assert result[0].decision is analysis.decision
