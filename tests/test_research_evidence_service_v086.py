from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryResult
from edward.services.research_evidence_service_v086 import ResearchEvidenceServiceV086


def test_research_evidence_aggregates_all_wf_strategy_contexts(monkeypatch):
    calls = []

    def fake_run(*, ticker, conditional_discovery, wf_result, candles):
        calls.append(wf_result.strategy)
        return SimpleNamespace(
            evidence=(SimpleNamespace(observations=2),),
            source_wf_strategy=wf_result.strategy,
            source_wf_windows=len(wf_result.windows),
        )

    monkeypatch.setattr(
        "edward.services.research_evidence_service_v086.WFEvidencePipelineServiceV086.run",
        fake_run,
    )
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles = tuple(
        Candle(start + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for i in range(20)
    )
    wf_results = {
        "Trend Following": SimpleNamespace(strategy="Trend Following", windows=(1, 2)),
        "Breakout": SimpleNamespace(strategy="Breakout", windows=(1, 2, 3)),
    }

    result = ResearchEvidenceServiceV086.run(
        ticker="SBER",
        conditional_discovery=SimpleNamespace(spec=ConditionalDiscoveryResult),
        wf_results=wf_results,
        candles=candles,
    )

    assert calls == ["Trend Following", "Breakout"]
    assert set(result.by_strategy) == {"Trend Following", "Breakout"}
    assert result.total_cells == 2
    assert result.total_observations == 4
