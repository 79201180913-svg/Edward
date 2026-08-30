from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.research_discovery_service_v085 import ResearchDiscoveryServiceV085


def _candles(closes: list[float], *, opens: list[float] | None = None, highs: list[float] | None = None, lows: list[float] | None = None) -> list[Candle]:
    opens = opens or closes
    highs = highs or [max(o, c) * 1.001 for o, c in zip(opens, closes)]
    lows = lows or [min(o, c) * 0.999 for o, c in zip(opens, closes)]
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [Candle(start + timedelta(days=i), o, h, l, c, 1000.0) for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes))]


def test_discovery_returns_all_predefined_hypotheses_and_horizons():
    closes = [100.0 + i * 0.5 for i in range(80)]
    result = ResearchDiscoveryServiceV085.run(_candles(closes))

    assert result.version == "0.8.5"
    assert result.candles == 80
    assert {item.hypothesis for item in result.hypotheses} == {
        "BREAKOUT_EXPANSION",
        "PULLBACK_RECLAIM",
        "IMPULSE_CONTINUATION",
        "SHOCK_REVERSAL",
        "GAP_REVERSAL",
        "RANGE_BREAK",
    }
    assert all(len(item.horizons) == 5 for item in result.hypotheses)


def test_shock_reversal_event_is_not_selected_as_a_trading_recommendation():
    closes = [100.0] * 30 + [95.0, 96.0, 98.0, 99.0] + [99.5] * 30
    result = ResearchDiscoveryServiceV085.run(_candles(closes))
    shock = next(item for item in result.hypotheses if item.hypothesis == "SHOCK_REVERSAL")

    assert shock.events >= 1
    horizon_3 = next(item for item in shock.horizons if item.horizon == 3)
    assert horizon_3.observations >= 1
    assert isinstance(horizon_3.excess_return_pct, float)


def test_negative_gap_is_detected_using_open_against_previous_close():
    closes = [100.0] * 30 + [100.0, 98.0, 99.0, 100.0] + [100.0] * 30
    opens = closes.copy()
    opens[30] = 96.0
    highs = [max(o, c) * 1.001 for o, c in zip(opens, closes)]
    lows = [min(o, c) * 0.999 for o, c in zip(opens, closes)]
    result = ResearchDiscoveryServiceV085.run(_candles(closes, opens=opens, highs=highs, lows=lows))
    gap = next(item for item in result.hypotheses if item.hypothesis == "GAP_REVERSAL")

    assert gap.events == 1


def test_insufficient_history_is_reported_without_exception():
    result = ResearchDiscoveryServiceV085.run(_candles([100.0] * 20))

    assert result.hypotheses == ()
    assert result.baseline_horizons == ()
