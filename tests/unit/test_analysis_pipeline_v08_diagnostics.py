from types import SimpleNamespace

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineServiceV08


def test_pipeline_v08_result_exposes_analysis_service_diagnostics(monkeypatch):
    diagnostics = {"strategies": {"Breakout": {"data_sufficient": True}}}

    class FakeAnalysisService:
        costs = object()
        last_diagnostics = diagnostics

        def analyze(self, **kwargs):
            return SimpleNamespace(
                strategies=[],
                market_regime="SIDEWAYS",
            )

    class FakeForecastQuality:
        def evaluate(self, **kwargs):
            return SimpleNamespace(overall_quality_score=50.0)

    service = AnalysisPipelineServiceV08(analysis_service=FakeAnalysisService())
    service.forecast_quality = FakeForecastQuality()

    result = service.analyze(
        instrument_uid="uid",
        ticker="TEST",
        candles=[],
        profile="medium_term",
    )

    assert result.diagnostics is diagnostics
