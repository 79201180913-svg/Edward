from datetime import datetime, timedelta, timezone

import pytest

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.economic_validation_v088 import TradingCostModelV088
from edward.services.event_observation_v086 import EventObservationV086
from edward.services.trading_path_validation_v088 import TradingPathValidationServiceV088


def _candidate() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule("uid", "SBER", "BREAKOUT_EXPANSION", "TREND_DOWN", "High", "Positive", 2),
        evidence=TradingPathEvidence(10, 1.0, 0.9, 70.0, 0.2, 0.5, True, 80.0),
    )


def _candles() -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    prices = [(100, 100), (101, 101), (102, 104), (104, 106), (106, 108)]
    return [Candle(start + timedelta(hours=i), open_, open_, open_, close) for i, (open_, close) in enumerate(prices)]


def _observation() -> EventObservationV086:
    return EventObservationV086(
        hypothesis="BREAKOUT_EXPANSION",
        index=1,
        timestamp=datetime(2025, 1, 1, 1, tzinfo=timezone.utc),
        regime="TREND_DOWN",
        volatility_bucket="High",
        direction="Positive",
        forward_returns_pct=((1, 1.0), (3, 2.0), (5, 3.0), (10, 4.0), (20, 5.0)),
    )


def test_validation_connects_rule_backtest_and_economics():
    result = TradingPathValidationServiceV088.validate(
        _candidate(), _candles(), (_observation(),), TradingCostModelV088()
    )
    assert result.rule.ticker == "SBER"
    assert len(result.backtest.trades) == 1
    assert result.economics.trades == 1
    assert result.economics.net_return_pct == pytest.approx(result.backtest.trades[0].return_pct)


def test_validation_does_not_promote_candidate():
    result = TradingPathValidationServiceV088.validate(
        _candidate(), _candles(), (_observation(),), TradingCostModelV088()
    )
    assert result.candidate.status.value == "research"


def test_validation_uses_cost_model_after_backtest():
    result = TradingPathValidationServiceV088.validate(
        _candidate(), _candles(), (_observation(),), TradingCostModelV088(commission_pct_per_side=0.1)
    )
    assert result.economics.net_return_pct < result.economics.gross_return_pct
