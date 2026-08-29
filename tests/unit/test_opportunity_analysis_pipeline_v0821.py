from dataclasses import dataclass
from types import SimpleNamespace

import edward.services.opportunity_analysis_pipeline_v0821 as adapter_module
from edward.services.opportunity_analysis_pipeline_v0821 import OpportunityAnalysisPipelineV0821
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


@dataclass(frozen=True)
class FakeBase:
    base: str
    opportunity: str = "opportunity"


@dataclass(frozen=True)
class FakePipelineResult:
    base: FakeBase
    analysis: str = "analysis"


class FakeCollector:
    def __init__(self):
        self.calls = []

    def collect(self, instrument_uid):
        self.calls.append(instrument_uid)
        return SimpleNamespace(
            reports=("event",),
            signals=("signal",),
            fundamentals={"roe": 20.0},
            order_book="order-book",
            trades=("trade",),
            dividends=("dividend",),
            insider_transactions=("insider",),
            risk_data="risk-data",
            instrument_risk_metadata="instrument-risk",
            session_name="MOEX_MAIN",
            news=("news",),
        )


class FakePipeline:
    def __init__(self):
        self.calls = []
        self.result = FakePipelineResult(base=FakeBase(base="base-v08"))

    def analyze(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeNews:
    @staticmethod
    def analyze(news, instrument_uid):
        assert news == ("news",)
        assert instrument_uid == "uid"
        return "news-result"


class FakeNewsOverlay:
    @staticmethod
    def apply(base, news_result):
        assert base == "base-v08"
        assert news_result == "news-result"
        return "news-adjusted-base", "overlay"


def test_adapter_reuses_v082_pipeline_and_contract_data(monkeypatch):
    monkeypatch.setattr(adapter_module, "install_client_patch", lambda: None)
    monkeypatch.setattr(adapter_module, "NewsIntelligenceServiceV081", FakeNews)
    monkeypatch.setattr(adapter_module, "NewsOverlayServiceV081", FakeNewsOverlay)

    collector = FakeCollector()
    pipeline = FakePipeline()
    service = OpportunityAnalysisPipelineV0821(
        object(),
        pipeline=pipeline,
        collector=collector,
    )

    result = service.analyze(
        instrument_uid="uid",
        ticker="SBER",
        candles=[1, 2, 3],
        profile="speculative",
        instrument={"ticker": "SBER", "name": "Sberbank"},
    )

    assert collector.calls == ["uid"]
    assert result is not pipeline.result
    call = pipeline.calls[0]
    assert call["instrument_uid"] == "uid"
    assert call["ticker"] == "SBER"
    assert call["profile"] == "speculative"
    assert call["order_book"] == "order-book"
    assert call["trades"] == ("trade",)
    assert call["current_signal"] == "signal"
    assert call["historical_signals"] == ("signal",)
    assert call["event"] == "event"
    assert call["dividend_data"] == ("dividend",)
    assert call["insider_transactions"] == ("insider",)
    assert call["risk_data"] == "risk-data"
    assert call["instrument_risk_metadata"] == "instrument-risk"
    assert call["session_name"] == "MOEX_MAIN"
    assert call["fundamentals"]["roe"] == 20.0
    assert call["fundamentals"]["__instrument_context"]["ticker"] == "SBER"
    assert call["fundamentals"]["__instrument_context"]["name"] == "Sberbank"
    assert result.base.base == "news-adjusted-base"


def test_live_opportunity_service_uses_v0821_adapter(monkeypatch):
    class FakeAdapter:
        def __init__(self, client):
            self.client = client

    monkeypatch.setattr(
        "edward.services.opportunity_search_service_live_v04.OpportunityAnalysisPipelineV0821",
        FakeAdapter,
    )

    service = LiveOpportunitySearchService(object())

    assert isinstance(service.analysis, FakeAdapter)
    assert service.cache_info == {"hits": 0, "misses": 0, "total": 0}
