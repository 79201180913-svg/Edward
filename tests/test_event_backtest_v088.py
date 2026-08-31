from datetime import datetime, timezone

from edward.services.analysis_service import Candle
from edward.services.event_backtest_v088 import EventBacktestV088
from edward.services.event_observation_v086 import EventObservationV086
from edward.services.trading_rule_builder_v088 import TradingRuleBuilderV088
from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule


def _candidate(direction: str = "Positive", horizon: int = 2) -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule("uid", "SBER", "BREAKOUT_EXPANSION", "TREND_UP", "High", direction, horizon),
        evidence=TradingPathEvidence(10, 2.0, 2.0, 70.0, 0.0, 2.0, True),
    )


def _obs(index: int = 1, direction: str = "Positive") -> EventObservationV086:
    return EventObservationV086(
        hypothesis="BREAKOUT_EXPANSION",
        index=index,
        timestamp=datetime(2025, 1, index + 1, tzinfo=timezone.utc),
        regime="TREND_UP",
        volatility_bucket="High",
        direction=direction,
        forward_returns_pct=((1, 1.0), (2, 2.0)),
    )


def _candles():
    closes = [100.0, 101.0, 110.0, 120.0, 130.0]
    return [Candle(datetime(2025, 1, i + 1, tzinfo=timezone.utc), c - 1, c, c - 2, c, 0) for i, c in enumerate(closes)]


def test_event_backtest_enters_next_open_not_event_close():
    rule = TradingRuleBuilderV088.build(_candidate(horizon=2))
    result = EventBacktestV088.run(_candles(), (_obs(1),), rule)
    trade = result.trades[0]
    assert trade.event_index == 1
    assert trade.entry_index == 2
    assert trade.exit_index == 3
    assert trade.entry_price == _candles()[2].open


def test_event_backtest_applies_short_direction():
    rule = TradingRuleBuilderV088.build(_candidate(direction="Negative", horizon=2))
    result = EventBacktestV088.run(_candles(), (_obs(1, direction="Negative"),), rule)
    assert result.trades[0].return_pct < 0


def test_event_backtest_skips_out_of_range_events():
    rule = TradingRuleBuilderV088.build(_candidate(horizon=20))
    result = EventBacktestV088.run(_candles(), (_obs(1),), rule)
    assert result.trades == ()