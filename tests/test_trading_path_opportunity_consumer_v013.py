from types import SimpleNamespace

from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathCurrentState,
    TradingPathDecision,
    TradingPathAnalysisV012,
    TradingPathOpportunity,
)
from edward.services.trading_path_opportunity_consumer_v013 import (
    TradingPathOpportunityConsumerV013,
)


def _analysis(*, rank, status=TradingPathAnalysisStatus.VALIDATED, decision=TradingPathDecision.WAIT, score=None, hypothesis="H1"):
    return TradingPathAnalysisV012(
        instrument_uid="SBER",
        ticker="SBER",
        strategy_family=hypothesis,
        hypothesis=hypothesis,
        regime="RANGE",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=5,
        evidence=SimpleNamespace(),
        opportunity=TradingPathOpportunity(score=score),
        current_state=TradingPathCurrentState.WAIT,
        decision=decision,
        status=status,
        rank=rank,
    )


def test_consumer_aggregates_paths_per_instrument_and_keeps_best_path():
    result = TradingPathOpportunityConsumerV013.build(
        [
            _analysis(rank=2, decision=TradingPathDecision.PASS, score=80.0, hypothesis="H2"),
            _analysis(rank=1, decision=TradingPathDecision.BUY, score=70.0, hypothesis="H1"),
            _analysis(rank=3, status=TradingPathAnalysisStatus.REJECTED, decision=TradingPathDecision.PASS),
        ]
    )

    assert len(result) == 1
    item = result[0]
    assert item.instrument_uid == "SBER"
    assert item.total_paths == 3
    assert item.best_path.hypothesis == "H1"
    assert item.decision is TradingPathDecision.BUY
    assert item.buy_paths == 1
    assert item.pass_paths == 2
    assert item.rejected_paths == 1


def test_consumer_does_not_recalculate_opportunity_or_decision():
    path = _analysis(rank=1, decision=TradingPathDecision.WAIT, score=42.0)
    result = TradingPathOpportunityConsumerV013.build([path])[0]

    assert result.best_path is path
    assert result.best_path.opportunity.score == 42.0
    assert result.decision is path.decision
