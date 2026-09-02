from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.domain import TradingPathValidationSummary
from edward.services.analysis_service import Candle
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012


class HashableNamespace(SimpleNamespace):
    __hash__ = object.__hash__


def test_runtime_propagates_statistical_integrity_snapshot_to_final_analysis(monkeypatch):
    candles = [
        Candle(datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for i in range(120)
    ]
    candidate = HashableNamespace(
        rule=SimpleNamespace(
            instrument_uid="SBER",
            ticker="SBER",
            hypothesis="ADAPTIVE_RULE:regime=Trend AND return_5>=0.0",
            regime="Trend",
            volatility_bucket="Adaptive",
            direction="Positive",
            horizon=5,
        )
    )
    validation = TradingPathValidationSummary(
        wf_persistence_pct=75.0,
        robustness_score=0.8,
        positive_oos_windows_pct=100.0,
        promotion_status="validated",
    )
    analysis = SimpleNamespace(
        instrument_uid="SBER",
        ticker="SBER",
        strategy_family="Adaptive Discovery",
        hypothesis=candidate.rule.hypothesis,
        regime=candidate.rule.regime,
        volatility_bucket=candidate.rule.volatility_bucket,
        direction=candidate.rule.direction,
        horizon=candidate.rule.horizon,
        evidence=SimpleNamespace(),
        validation=validation,
        market_context=SimpleNamespace(),
        opportunity=SimpleNamespace(),
        rank=1,
    )
    integrity = SimpleNamespace(
        statistically_valid=True,
        overlap_valid=True,
        multiple_testing_valid=True,
        effective_sample_size=18.5,
        overlap_ratio_pct=75.0,
        standard_error_pct=0.42,
        z_score=2.15,
        p_value_one_sided=0.015,
        adjusted_p_value=0.03,
        hypotheses_tested=12,
    )

    monkeypatch.setattr(
        "edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run",
        lambda ordered: SimpleNamespace(evidence=()),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.from_fixed",
        lambda discovery, *, instrument_uid, ticker: (),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_adaptive_discovery_service_v014.TradingPathAdaptiveDiscoveryServiceV014.run",
        lambda train: SimpleNamespace(candidates=(SimpleNamespace(),)),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.from_adaptive",
        lambda discovery, *, instrument_uid, ticker: (candidate,),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.combine",
        lambda fixed, adaptive, *, ticker: (candidate,),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_adaptive_oos_service_v014.TradingPathAdaptiveOOSServiceV014.returns_in_range",
        lambda candidate, candles, *, start, end: (1.0, 2.0, 1.5),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_statistical_integrity_service_v014.TradingPathStatisticalIntegrityServiceV014.evaluate_candidate_returns",
        lambda *args, **kwargs: {candidate: integrity},
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_pruning_service_v014.TradingPathCandidatePruningServiceV014.prune",
        lambda combined, *, config, statistical_integrity: (candidate,),
    )
    monkeypatch.setattr(
        "edward.services.event_observation_v086.EventObservationBuilderV086.build",
        lambda ordered: (),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_analysis_builder_v012.TradingPathAnalysisBuilderV012.build",
        lambda candidates, ordered, **kwargs: (analysis,),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_oos_validation_service_v012.TradingPathOOSValidationServiceV012.validate",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_expected_value_service_v012.TradingPathExpectedValueServiceV012.calculate",
        lambda *args, **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_risk_service_v012.TradingPathRiskServiceV012.evaluate",
        lambda *args, **kwargs: SimpleNamespace(risk=SimpleNamespace(score=0.2), path_eligible=True),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_opportunity_builder_v012.TradingPathOpportunityBuilderV012.build",
        lambda analysis, **kwargs: analysis,
    )
    monkeypatch.setattr(
        "edward.services.trading_path_decision_service_v012.TradingPathDecisionServiceV012.decide",
        lambda analysis: SimpleNamespace(current_state="wait", decision="wait", status="validated", reasons=()),
    )

    result = AnalysisPathRuntimeServiceV012().analyze_paths(
        instrument_uid="SBER",
        ticker="SBER",
        candles=candles,
    )

    assert len(result) == 1
    snapshot = result[0].validation
    assert snapshot.statistical_valid is True
    assert snapshot.overlap_valid is True
    assert snapshot.multiple_testing_valid is True
    assert snapshot.effective_sample_size == 18.5
    assert snapshot.overlap_ratio_pct == 75.0
    assert snapshot.standard_error_pct == 0.42
    assert snapshot.z_score == 2.15
    assert snapshot.p_value_one_sided == 0.015
    assert snapshot.adjusted_p_value == 0.03
    assert snapshot.hypotheses_tested == 12
    assert snapshot.promotion_status == "validated"
