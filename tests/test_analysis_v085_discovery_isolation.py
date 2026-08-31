from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08


def _candles(count: int = 520) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = []
    price = 100.0
    for i in range(count):
        drift = 0.0015 if (i // 25) % 2 == 0 else -0.0005
        previous = price
        price = previous * (1.0 + drift)
        high = max(previous, price) * 1.002
        low = min(previous, price) * 0.998
        result.append(Candle(start + timedelta(hours=i), previous, high, low, price, 1000.0))
    return result


def test_v085_discovery_is_diagnostics_only_and_does_not_change_selection():
    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="TEST-001",
        ticker="TEST",
        candles=_candles(),
        profile="medium_term",
    )

    diagnostics = service.last_diagnostics
    assert diagnostics is not None
    assert diagnostics.research_discovery is not None
    assert len(diagnostics.research_discovery.hypotheses) == 6

    assert len(result.strategies) == 4
    assert {item.strategy for item in result.strategies} == set(AnalysisServiceV08.STRATEGIES)

    passed = [item for item in result.strategies if item.quality_gate]
    assert result.recommendation is None if not passed else result.recommendation in {
        item.strategy for item in passed
    }


def test_v085_discovery_cannot_create_recommendation_outside_qg_pass_set():
    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="TEST-002",
        ticker="TEST",
        candles=_candles(),
        profile="medium_term",
    )

    diagnostics = service.last_diagnostics
    assert diagnostics is not None
    assert diagnostics.research_discovery is not None

    passed = {item.strategy for item in result.strategies if item.quality_gate}
    assert result.recommendation in passed or result.recommendation is None
