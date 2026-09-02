from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012


def test_runtime_bridge_exposes_canonical_path_analysis(monkeypatch):
    candles = [
        Candle(datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for i in range(120)
    ]

    monkeypatch.setattr(
        "edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run",
        lambda ordered: SimpleNamespace(evidence=()),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v088.TradingPathCandidateServiceV088.promote",
        lambda discovery, *, instrument_uid, ticker: (),
    )

    result = AnalysisPathRuntimeServiceV012().analyze_paths(
        instrument_uid="SBER",
        ticker="SBER",
        candles=candles,
    )

    assert result == ()


def test_runtime_bridge_sorts_candles_before_discovery(monkeypatch):
    timestamps = [
        datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        for i in range(120)
    ]
    shuffled = [timestamps[i] for i in (2, 0, 1, *range(3, 120))]
    candles = [Candle(ts, 100.0, 101.0, 99.0, 100.0, 1000.0) for ts in shuffled]
    captured = []

    monkeypatch.setattr(
        "edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run",
        lambda ordered: captured.append(tuple(item.timestamp for item in ordered)) or SimpleNamespace(evidence=()),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v088.TradingPathCandidateServiceV088.promote",
        lambda discovery, *, instrument_uid, ticker: (),
    )

    AnalysisPathRuntimeServiceV012().analyze_paths(
        instrument_uid="SBER",
        ticker="SBER",
        candles=candles,
    )

    assert captured == [tuple(sorted(timestamps))]
