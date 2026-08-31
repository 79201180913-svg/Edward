from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_pipeline_service_v011 import AnalysisPipelineServiceV011
from edward.services.analysis_pipeline_service_v082 import AnalysisPipelineServiceV082
from edward.services.analysis_service import Candle


def _candles(count: int = 320, start_price: float = 100.0):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(days=i),
            open=start_price + i,
            high=start_price + i + 1,
            low=start_price + i - 1,
            close=start_price + i,
            volume=1000,
        )
        for i in range(count)
    ]


def test_pipeline_attaches_market_context_without_changing_baseline():
    candles = _candles()
    pipeline = AnalysisPipelineServiceV011(base_pipeline=AnalysisPipelineServiceV082())

    result = pipeline.analyze(
        instrument_uid="instrument",
        ticker="TEST",
        candles=candles,
        instrument_metadata={"instrument_type": "STOCK", "market": "MOEX"},
        market_candles=candles,
    )

    baseline = AnalysisPipelineServiceV082().analyze(
        instrument_uid="instrument",
        ticker="TEST",
        candles=candles,
    )

    assert result.benchmark.benchmark_id == "IMOEX"
    assert result.market_context.instrument_id == "IMOEX"
    assert result.market_context.source_candles == len(candles)
    assert result.analysis == baseline.analysis
    assert result.opportunity == baseline.opportunity
    assert result.forecast_quality_score == baseline.forecast_quality_score


def test_pipeline_rejects_missing_market_candles():
    pipeline = AnalysisPipelineServiceV011()
    with pytest.raises(ValueError, match="market_candles are required"):
        pipeline.analyze(
            instrument_uid="instrument",
            ticker="TEST",
            candles=_candles(),
            instrument_metadata={"instrument_type": "STOCK", "market": "MOEX"},
        )
