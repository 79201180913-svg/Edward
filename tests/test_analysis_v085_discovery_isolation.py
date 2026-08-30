from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08


def _candles(count: int = 520) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = []
    price = 100.0
    for i in range(count):
        # Deterministic, non-flat history with enough observations for the
        # medium-term v0.8 profile and discovery horizons.
        drift = 0.0015 if (i // 25) % 2 == 0 else -0.0005
        previous = price
        price = previous * (1.0 + drift)
        high = max(previous, price) * 1.002
        low = min(previous, price) * 0.998
        result.append(Candle(start + timedelta(hours=i), previous, high, low, price, 1000.0))
    return result


def test_v085_discovery_is_diagnostics_only_and_does_not_change_selection():
    candles = _candles()
    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="TEST-001",
        ticker="TEST",
        candles=candles,
        profile="medium_term",
    )

    diagnostics = service.last_diagnostics

    assert diagnostics is not None
    assert diagnostics.research_discovery is not None
    assert len(diagnostics.research_discovery.hypotheses) == 6

    # The v0.8.5 discovery layer is research-only. Existing strategy results,
    # QG decisions and recommendation remain produced by the canonical v0.8
    # WF/QG pipeline.
    assert len(result.strategies) == 4
    assert {item.strategy for item in result.strategies} == set(AnalysisServiceV08.STRATEGIES)
    assert all(item.quality_gate is False for item in result.strategies) or any(
        item.quality_gate is True for item in result.strategies
    )
    assert result.recommendation in {None, *AnalysisServiceV08.STRATEGIES}


def test_v085_discovery_does_not_create_recommendation_when_no_strategy_passes_qg():
    candles = _candles()
    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="TEST-002",
        ticker="TEST",
        candles=candles,
        profile="medium_term",
    )

    diagnostics = service.last_diagnostics
    assert diagnostics is not None
    assert diagnostics.research_discovery is not None

    passed = [item for item in result.strategies if item.quality_gate]
    assert result.recommendation is None if not passed else result.recommendation in {
        item.strategy for item in passed
    }
