from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08


def test_v087_research_fields_do_not_change_empty_recommendation(monkeypatch):
    service = AnalysisServiceV08()
    candles = [
        Candle(datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for i in range(400)
    ]
    from types import SimpleNamespace

    monkeypatch.setattr(
        "edward.services.analysis_service_v08.RegimeEngine.classify",
        lambda ordered: SimpleNamespace(regime="RANGE", confidence=70.0),
    )
    monkeypatch.setattr(
        "edward.services.analysis_service_v08.ResearchDiscoveryServiceV085.run",
        lambda ordered: SimpleNamespace(hypotheses=()),
    )
    monkeypatch.setattr(
        "edward.services.analysis_service_v08.ConditionalDiscoveryServiceV086.run",
        lambda ordered: SimpleNamespace(evidence=(), observations=(), min_observations=8),
    )
    monkeypatch.setattr(
        "edward.services.analysis_service_v08.EvidenceAuditServiceV086.audit",
        lambda result: (),
    )
    monkeypatch.setattr(
        "edward.services.analysis_service_v08.EvidenceAuditServiceV086.audit_wf",
        lambda result, wf_result, ordered: (),
    )
    captured_contexts = []

    def fake_build_from_wf_contexts(evidence, contexts):
        captured_contexts.extend(contexts)
        return ()

    monkeypatch.setattr(
        "edward.services.analysis_service_v08.ResearchEvidenceReportServiceV086.build_from_wf_contexts",
        fake_build_from_wf_contexts,
    )
    monkeypatch.setattr(
        "edward.services.analysis_service_v08.ResearchEvidenceSummaryServiceV087.build",
        lambda rows: SimpleNamespace(
            total_cells=0,
            interesting=0,
            low_sample=0,
            no_positive_excess=0,
            low_wf_persistence=0,
            top_magnitude=(),
            top_consistency=(),
            top_stability=(),
        ),
    )
    monkeypatch.setattr(
        service,
        "_robust",
        lambda ordered, strategy, profile: SimpleNamespace(
            strategy=strategy,
            windows=(),
            robustness_score=0.0,
            mean_test_return_pct=0.0,
            mean_test_drawdown_pct=0.0,
            mean_test_sharpe=0.0,
            positive_return_windows=0,
            risk_ok_windows=0,
            positive_sharpe_windows=0,
            return_consistency_pct=0.0,
            risk_consistency_pct=0.0,
            sharpe_consistency_pct=0.0,
        ),
    )
    monkeypatch.setattr(
        "edward.services.analysis_service_v08.QualityGateDiagnosticsServiceV0822.evaluate",
        lambda result, profile: SimpleNamespace(passed=False, failed_checks=(), failure_reason=None, checks=()),
    )

    result = service.analyze(instrument_uid="SBER", ticker="SBER", candles=candles)

    assert result.recommendation is None
    assert result.analysis_version == "0.8.7"
    assert service.last_diagnostics is not None
    assert service.last_diagnostics.research_summary is not None
    assert service.last_diagnostics.research_summary.total_cells == 0
    assert [strategy for strategy, _ in captured_contexts] == list(service.STRATEGIES)
