from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086
from edward.services.regime_engine_v08 import RegimeEngine


def _candles(closes: list[float], opens: list[float] | None = None) -> list[Candle]:
    opens = opens or closes
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(start + timedelta(hours=i), o, max(o, c) * 1.001, min(o, c) * 0.999, c, 1000.0)
        for i, (o, c) in enumerate(zip(opens, closes))
    ]


def test_v086_uses_canonical_regime_taxonomy():
    assert ConditionalDiscoveryServiceV086.REGIMES == RegimeEngine.REGIMES
    assert "TRANSITION" in ConditionalDiscoveryServiceV086.REGIMES
    assert "TREND_UP" in ConditionalDiscoveryServiceV086.REGIMES
    assert "TREND_DOWN" in ConditionalDiscoveryServiceV086.REGIMES


def test_v086_returns_full_conditional_cell_grid():
    closes = [100.0 * (1.001 ** i) for i in range(140)]
    result = ConditionalDiscoveryServiceV086.run(_candles(closes))
    assert result.version == "0.8.6"
    assert len(result.evidence) == 6
    expected_cells = len(RegimeEngine.REGIMES) * 3 * 2 * 5
    assert all(len(item.cells) == expected_cells for item in result.evidence)


def test_v086_marks_small_samples_insufficient():
    closes = [100.0] * 80
    result = ConditionalDiscoveryServiceV086.run(_candles(closes))
    assert result.evidence
    assert all(not cell.sufficient_sample for item in result.evidence for cell in item.cells)


def test_v086_forward_return_never_uses_pre_event_prices():
    candles = _candles([100.0, 110.0, 120.0, 130.0, 140.0])
    assert ConditionalDiscoveryServiceV086._forward_return(candles, 1, 2) == (130.0 / 110.0) - 1.0
    assert ConditionalDiscoveryServiceV086._forward_return(candles, 1, 3) == (140.0 / 110.0) - 1.0
    assert ConditionalDiscoveryServiceV086._forward_return(candles, 1, 4) is None


def test_v086_gap_event_is_classified_with_event_direction():
    closes = [100.0] * 30 + [98.0] + [99.0] * 40
    opens = closes.copy()
    opens[30] = 96.0
    result = ConditionalDiscoveryServiceV086.run(_candles(closes, opens))
    gap = next(item for item in result.evidence if item.hypothesis == "GAP_REVERSAL")
    assert gap.events == 1
    matching = [cell for cell in gap.cells if cell.direction == "Negative" and cell.horizon == 1]
    assert matching
    assert matching[0].observations >= 0
