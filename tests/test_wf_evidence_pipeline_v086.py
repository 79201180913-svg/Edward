from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import (
    ConditionalDiscoveryCell,
    ConditionalDiscoveryEvidence,
    ConditionalDiscoveryResult,
)
from edward.services.wf_evidence_pipeline_v086 import WFEvidencePipelineServiceV086


def test_wf_evidence_pipeline_is_research_only_and_preserves_wf_context():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles = [
        Candle(start + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for i in range(80)
    ]
    observations = (
        SimpleNamespace(hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP", volatility_bucket="High", direction="Positive", index=15, timestamp=candles[15].timestamp, forward_return=lambda horizon: 1.0),
        SimpleNamespace(hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP", volatility_bucket="High", direction="Positive", index=45, timestamp=candles[45].timestamp, forward_return=lambda horizon: -1.0),
    )
    cell = ConditionalDiscoveryCell("BREAKOUT_EXPANSION", "TREND_UP", "High", "Positive", 5, 2, 0.0, 0.0, 50.0, 0.0, 0.0, False)
    discovery = ConditionalDiscoveryResult("0.8.6", len(candles), 8, (ConditionalDiscoveryEvidence("BREAKOUT_EXPANSION", 2, (cell,)),), observations)
    wf = SimpleNamespace(strategy="Breakout", windows=(
        SimpleNamespace(test_start=candles[10].timestamp, test_end=candles[30].timestamp),
        SimpleNamespace(test_start=candles[31].timestamp, test_end=candles[60].timestamp),
    ))

    result = WFEvidencePipelineServiceV086.run(ticker="SBER", conditional_discovery=discovery, wf_result=wf, candles=candles)

    assert result.source_wf_strategy == "Breakout"
    assert result.source_wf_windows == 2
    assert len(result.evidence) == 1
    assert result.evidence[0].wf_windows == 2
    assert result.evidence[0].positive_wf_windows == 1
    assert result.evidence[0].negative_wf_windows == 1
    assert result.evidence[0].wf_persistence_pct == 50.0
