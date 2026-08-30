from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086


def _candles(count: int = 520) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = []
    price = 100.0
    for i in range(count):
        drift = 0.0015 if (i // 25) % 2 == 0 else -0.0005
        previous = price
        price = previous * (1.0 + drift)
        result.append(
            Candle(
                start + timedelta(hours=i),
                previous,
                max(previous, price) * 1.002,
                min(previous, price) * 0.998,
                price,
                1000.0,
            )
        )
    return result


def test_v086_conditional_discovery_is_exposed_only_in_diagnostics():
    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="V086-001",
        ticker="TEST",
        candles=_candles(),
        profile="medium_term",
    )

    diagnostics = service.last_diagnostics
    assert diagnostics is not None
    conditional = diagnostics.conditional_discovery
    assert conditional is not None
    assert conditional.version == "0.8.6"
    assert len(conditional.evidence) == len(ConditionalDiscoveryServiceV086.HYPOTHESES)

    # Conditional Discovery is descriptive evidence only.
    assert not hasattr(result, "conditional_discovery")
    assert not hasattr(result, "best_cell")
    assert not hasattr(result, "selected_cell")


def test_v086_conditional_discovery_cannot_bypass_quality_gate():
    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="V086-002",
        ticker="TEST",
        candles=_candles(),
        profile="medium_term",
    )

    passed = {item.strategy for item in result.strategies if item.quality_gate}
    assert result.recommendation is None or result.recommendation in passed


def test_v086_conditional_discovery_does_not_change_strategy_set():
    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="V086-003",
        ticker="TEST",
        candles=_candles(),
        profile="medium_term",
    )

    assert tuple(item.strategy for item in result.strategies) == AnalysisServiceV08.STRATEGIES
    assert len(result.strategies) == 4
