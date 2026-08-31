from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086


def _candles(count: int = 220) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    result = []
    for i in range(count):
        previous = price
        if i % 37 == 0 and i > 25:
            price *= 1.035
        elif i % 43 == 0 and i > 25:
            price *= 0.965
        else:
            price *= 1.0015 if (i // 12) % 2 == 0 else 0.999
        result.append(Candle(start + timedelta(hours=i), previous, max(previous, price) * 1.002, min(previous, price) * 0.998, price, 1000.0))
    return result


def test_conditional_grid_has_explicit_coverage_accounting():
    result = ConditionalDiscoveryServiceV086.run(_candles())
    total_cells = len(ConditionalDiscoveryServiceV086.REGIMES) * 3 * 2 * 5
    for evidence in result.evidence:
        assert len(evidence.cells) == total_cells
        assert evidence.sufficient_cells + sum(not c.sufficient_sample for c in evidence.cells) == total_cells


def test_coverage_audit_does_not_promote_small_samples():
    result = ConditionalDiscoveryServiceV086.run(_candles())
    for evidence in result.evidence:
        for cell in evidence.cells:
            if cell.observations < result.min_observations:
                assert cell.sufficient_sample is False


def test_no_cell_selection_is_encoded_in_conditional_result():
    result = ConditionalDiscoveryServiceV086.run(_candles())
    assert not hasattr(result, "best_cell")
    assert not hasattr(result, "selected_cell")
    assert not hasattr(result, "recommendation")
