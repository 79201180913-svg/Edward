from dataclasses import dataclass

from edward.services.analysis_pipeline_service_v082 import (
    ANALYSIS_PIPELINE_V082_VERSION,
    AnalysisPipelineServiceV082,
)


@dataclass
class FakePipelineResult:
    base_marker: str = "v081"

    @property
    def analysis(self):
        return "analysis"

    @property
    def opportunity(self):
        return "opportunity"

    @property
    def expected_value(self):
        return "expected"

    @property
    def portfolio_impact(self):
        return "portfolio"

    @property
    def confidence(self):
        return "confidence"


class FakeBasePipeline:
    def __init__(self):
        self.calls = []

    def analyze(self, **kwargs):
        self.calls.append(kwargs)
        return FakePipelineResult()


def test_version_is_082():
    assert ANALYSIS_PIPELINE_V082_VERSION == "0.8.2"


def test_pipeline_calculates_fundamental_result_without_changing_base_result():
    base = FakeBasePipeline()
    service = AnalysisPipelineServiceV082(base_pipeline=base)

    result = service.analyze(
        instrument_uid="uid",
        ticker="TEST",
        candles=[],
        fundamentals={
            "roe": 20,
            "revenue_growth": 10,
            "current_ratio": 1.8,
        },
    )

    assert result.version == "0.8.2"
    assert result.base.base_marker == "v081"
    assert result.analysis == "analysis"
    assert result.opportunity == "opportunity"
    assert result.fundamental.status == "PARTIAL"
    assert result.fundamental.coverage > 0
    assert result.fundamental.business_quality.score > 0
    assert base.calls[0]["fundamentals"] == {
        "roe": 20,
        "revenue_growth": 10,
        "current_ratio": 1.8,
    }


def test_pipeline_preserves_unavailable_fundamental_state():
    base = FakeBasePipeline()
    result = AnalysisPipelineServiceV082(base_pipeline=base).analyze(
        instrument_uid="uid",
        ticker="TEST",
        candles=[],
        fundamentals=None,
    )

    assert result.fundamental.status == "UNAVAILABLE"
    assert result.fundamental.coverage == 0
    assert result.fundamental.confidence == 0
