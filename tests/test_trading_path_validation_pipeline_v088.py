from datetime import datetime, timedelta, timezone

import pytest

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.economic_validation_v088 import TradingCostModelV088
from edward.services.event_observation_v086 import EventObservationV086
from edward.services.trading_path_validation_pipeline_v088 import TradingPathValidationPipelineV088


def _candidate() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule("uid", "SBER", "BREAKOUT_EXPANSION", "TREND_UP", "High", "Positive", 2),
        evidence=TradingPathEvidence(1, 1.0, 1.0, 100.0, 0.0, 1.0, True, 100.0),
    )


def _candles():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    values = ((99.0, 100.0), (100.0, 101.0), (101.0, 103.0), (103.0, 104.0))
    return tuple(
        Candle(start + timedelta(days=index), open_price, high, low, close, 1000.0)
        for index, (open_price, close) in enumerate(values)
        for high, low in [(max(open_price, close), min(open_price, close))]
    )


def _observation():
    return EventObservationV086(
        hypothesis="BREAKOUT_EXPANSION",
        index=0,
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        regime="TREND_UP",
        volatility_bucket="High",
        direction="Positive",
        forward_returns_pct=((2, 3.0),),
    )


def test_pipeline_composes_backtest_economics_and_statistics():
    result = TradingPathValidationPipelineV088.run(
        _candidate(), _candles(), (_observation(),),
        TradingCostModelV088(commission_pct_per_side=0.1, slippage_pct_per_side=0.05),
    )
    assert result.trades == 1
    assert result.gross_return_pct == pytest.approx(3.0)
    assert result.net_return_pct == pytest.approx(2.7)
    assert result.statistical_evidence.mean_return_pct == pytest.approx(3.0)


def test_pipeline_does_not_promote_candidate():
    result = TradingPathValidationPipelineV088.run(_candidate(), _candles(), (_observation(),))
    assert result.candidate.status.value == "research"
