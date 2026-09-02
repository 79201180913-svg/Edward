from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.trading_path_analysis_builder_v012 import TradingPathAnalysisBuilderV012


class HashableNamespace(SimpleNamespace):
    __hash__ = object.__hash__


def _candles(count=120, *, oos_close=100.0):
    candles = []
    for i in range(count):
        close = 100.0 if i < 96 else oos_close
        candles.append(
            Candle(
                datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
                close,
                close + 1.0,
                close - 1.0,
                close,
                1000.0,
            )
        )
    return candles


def test_runtime_runs_canonical_path_stages(monkeypatch):
    candidate = HashableNamespace(rule=SimpleNamespace(instrument_uid="SBER", ticker="SBER", hypothesis="H1", regime="RANGE", volatility_bucket="Normal", direction="Positive", horizon=5))
    analysis = SimpleNamespace(instrument_uid="SBER", ticker="SBER", strategy_family="H1", hypothesis="H1", regime="RANGE", volatility_bucket="Normal", direction="Positive", horizon=5, evidence=SimpleNamespace(), validation=SimpleNamespace(promotion_status="validated", wf_persistence_pct=None, robustness_score=None, positive_oos_windows_pct=None), market_context=SimpleNamespace(), opportunity=SimpleNamespace(), current_state=SimpleNamespace(), decision=SimpleNamespace(), status=SimpleNamespace(), rank=1)
    observations = (SimpleNamespace(index=90, hypothesis="H1", regime="RANGE", volatility_bucket="Normal", direction="Positive"),)
    observation_builds = []
    monkeypatch.setattr("edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run", lambda candles: SimpleNamespace(evidence=()))
    monkeypatch.setattr("edward.services.trading_path_candidate_service_v088.TradingPathCandidateServiceV088.promote", lambda result, **kwargs: (candidate,))
    monkeypatch.setattr("edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.from_fixed", lambda discovery, **kwargs: (candidate,))
    monkeypatch.setattr("edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.combine", lambda fixed, adaptive, **kwargs: (candidate,))
    monkeypatch.setattr("edward.services.trading_path_candidate_pruning_service_v014.TradingPathCandidatePruningServiceV014.prune", lambda candidates, **kwargs: tuple(candidates))
    monkeypatch.setattr(TradingPathAnalysisBuilderV012, "build", lambda candidates, candles, **kwargs: (analysis,))
    monkeypatch.setattr("edward.services.event_observation_v086.EventObservationBuilderV086.build", lambda candles: observation_builds.append(tuple(candles)) or observations)
    monkeypatch.setattr("edward.services.trading_path_oos_validation_service_v012.TradingPathOOSValidationServiceV012.validate", lambda candidate, candles, **kwargs: ())
    monkeypatch.setattr("edward.services.trading_path_expected_value_service_v012.TradingPathExpectedValueServiceV012.calculate", lambda candidate, candles, **kwargs: SimpleNamespace(expected_value_pct=1.0, edge_reliability_pct=80.0))
    monkeypatch.setattr("edward.services.trading_path_risk_service_v012.TradingPathRiskServiceV012.evaluate", lambda analysis, **kwargs: SimpleNamespace(risk=SimpleNamespace(score=80.0), path_eligible=True))
    monkeypatch.setattr("edward.services.trading_path_opportunity_builder_v012.TradingPathOpportunityBuilderV012.build", lambda analysis, **kwargs: SimpleNamespace(**analysis.__dict__) if hasattr(analysis, "__dict__") else analysis)
    monkeypatch.setattr("edward.services.trading_path_decision_service_v012.TradingPathDecisionServiceV012.decide", lambda analysis: SimpleNamespace(current_state="entry_ready", decision="buy", status="promotable", reasons=()))
    result = AnalysisPathRuntimeServiceV012().analyze_paths(instrument_uid="SBER", ticker="SBER", candles=_candles())
    assert len(result) == 1
    assert result[0].decision == "buy"
    assert len(observation_builds) == 1


def test_runtime_sends_adaptive_candidate_through_same_downstream_pipeline(monkeypatch):
    adaptive_candidate = TradingPathCandidate(rule=TradingPathRule(instrument_uid="SBER", ticker="SBER", hypothesis="ADAPTIVE_RULE:regime=RANGE AND return_5 >= 0.0", regime="RANGE", volatility_bucket="Adaptive", direction="Positive", horizon=5), evidence=TradingPathEvidence(observations=20, mean_forward_return_pct=1.0, median_forward_return_pct=1.0, win_rate_pct=60.0, baseline_mean_return_pct=0.0, excess_return_pct=1.0, sufficient_sample=True), source_version="0.8.14")
    analysis = SimpleNamespace(instrument_uid="SBER", ticker="SBER", strategy_family="Adaptive Discovery", hypothesis=adaptive_candidate.rule.hypothesis, regime="RANGE", volatility_bucket="Adaptive", direction="Positive", horizon=5, evidence=SimpleNamespace(), validation=SimpleNamespace(promotion_status="validated", wf_persistence_pct=None, robustness_score=None, positive_oos_windows_pct=None), market_context=SimpleNamespace(), opportunity=SimpleNamespace(), current_state=SimpleNamespace(), decision=SimpleNamespace(), status=SimpleNamespace(), rank=1)
    calls = {"oos": [], "ev": [], "risk": [], "opportunity": [], "decision": []}
    monkeypatch.setattr("edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run", lambda candles: SimpleNamespace(evidence=()))
    monkeypatch.setattr("edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.from_fixed", lambda discovery, **kwargs: ())
    monkeypatch.setattr("edward.services.trading_path_adaptive_discovery_service_v014.TradingPathAdaptiveDiscoveryServiceV014.run", lambda candles: SimpleNamespace(candidates=(SimpleNamespace(),)))
    monkeypatch.setattr("edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.from_adaptive", lambda discovery, **kwargs: (adaptive_candidate,))
    monkeypatch.setattr("edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.combine", lambda fixed, adaptive, **kwargs: tuple(fixed) + tuple(adaptive))
    monkeypatch.setattr("edward.services.trading_path_candidate_pruning_service_v014.TradingPathCandidatePruningServiceV014.prune", lambda candidates, **kwargs: tuple(candidates))
    monkeypatch.setattr(TradingPathAnalysisBuilderV012, "build", lambda candidates, candles, **kwargs: (analysis,))
    monkeypatch.setattr("edward.services.event_observation_v086.EventObservationBuilderV086.build", lambda candles: ())
    monkeypatch.setattr("edward.services.trading_path_adaptive_oos_service_v014.TradingPathAdaptiveOOSServiceV014.returns_in_range", lambda candidate, candles, *, start, end: (1.0, 2.0))
    monkeypatch.setattr("edward.services.trading_path_oos_validation_service_v012.TradingPathOOSValidationServiceV012.validate", lambda candidate, candles, **kwargs: calls["oos"].append(kwargs) or ())
    monkeypatch.setattr("edward.services.trading_path_expected_value_service_v012.TradingPathExpectedValueServiceV012.calculate", lambda candidate, candles, **kwargs: calls["ev"].append(kwargs) or SimpleNamespace(expected_value_pct=1.0, edge_reliability_pct=80.0))
    monkeypatch.setattr("edward.services.trading_path_risk_service_v012.TradingPathRiskServiceV012.evaluate", lambda analysis_arg, **kwargs: calls["risk"].append(kwargs) or SimpleNamespace(risk=SimpleNamespace(score=80.0), path_eligible=True))
    monkeypatch.setattr("edward.services.trading_path_opportunity_builder_v012.TradingPathOpportunityBuilderV012.build", lambda analysis_arg, **kwargs: calls["opportunity"].append(kwargs) or analysis_arg)
    monkeypatch.setattr("edward.services.trading_path_decision_service_v012.TradingPathDecisionServiceV012.decide", lambda analysis_arg: calls["decision"].append(analysis_arg) or SimpleNamespace(current_state="entry_ready", decision="buy", status="promotable", reasons=()))
    result = AnalysisPathRuntimeServiceV012().analyze_paths(instrument_uid="SBER", ticker="SBER", candles=_candles())
    assert len(result) == 1
    assert result[0].hypothesis.startswith("ADAPTIVE_RULE:")
    assert len(calls["oos"]) == len(calls["ev"]) == len(calls["risk"]) == len(calls["opportunity"]) == len(calls["decision"]) == 1
    assert calls["oos"][0]["evaluation_start"] == 96
    assert calls["oos"][0]["evaluation_end"] == 120
    assert calls["ev"][0]["evaluation_start"] == 96
    assert calls["ev"][0]["evaluation_end"] == 120
    assert calls["risk"][0]["oos_windows"] == ()
    assert calls["opportunity"][0]["oos_windows"] == ()


def test_runtime_oos_changes_cannot_change_pre_oos_pipeline(monkeypatch):
    candidate = TradingPathCandidate(rule=TradingPathRule(instrument_uid="SBER", ticker="SBER", hypothesis="H1", regime="RANGE", volatility_bucket="Normal", direction="Positive", horizon=5), evidence=TradingPathEvidence(observations=20, mean_forward_return_pct=1.0, median_forward_return_pct=1.0, win_rate_pct=60.0, baseline_mean_return_pct=0.0, excess_return_pct=1.0, sufficient_sample=True), source_version="fixed:0.8.6")
    analysis = SimpleNamespace(instrument_uid="SBER", ticker="SBER", strategy_family="H1", hypothesis="H1", regime="RANGE", volatility_bucket="Normal", direction="Positive", horizon=5, evidence=SimpleNamespace(), validation=SimpleNamespace(promotion_status="validated"), market_context=SimpleNamespace(), opportunity=SimpleNamespace(), current_state=SimpleNamespace(), decision=SimpleNamespace(), status=SimpleNamespace(), rank=1)
    discovery_inputs, adaptive_inputs, validation_inputs = [], [], []
    monkeypatch.setattr("edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run", lambda candles: discovery_inputs.append(tuple(candles)) or SimpleNamespace(evidence=()))
    monkeypatch.setattr("edward.services.trading_path_adaptive_discovery_service_v014.TradingPathAdaptiveDiscoveryServiceV014.run", lambda candles: adaptive_inputs.append(tuple(candles)) or SimpleNamespace(candidates=(), version="0.8.14"))
    monkeypatch.setattr("edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.from_fixed", lambda discovery, **kwargs: (candidate,))
    monkeypatch.setattr("edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.combine", lambda fixed, adaptive, **kwargs: tuple(fixed) + tuple(adaptive))
    monkeypatch.setattr("edward.services.trading_path_candidate_pruning_service_v014.TradingPathCandidatePruningServiceV014.prune", lambda candidates, **kwargs: tuple(candidates))

    def fake_build(candidates, candles, **kwargs):
        key = tuple((item.rule.hypothesis, item.rule.regime, item.rule.volatility_bucket, item.rule.direction, item.rule.horizon) for item in candidates)
        validation_inputs.append((key, kwargs.get("validation_start"), kwargs.get("validation_end")))
        return (analysis,)

    monkeypatch.setattr(TradingPathAnalysisBuilderV012, "build", fake_build)
    monkeypatch.setattr("edward.services.event_observation_v086.EventObservationBuilderV086.build", lambda candles: ())
    monkeypatch.setattr("edward.services.trading_path_oos_validation_service_v012.TradingPathOOSValidationServiceV012.validate", lambda candidate, candles, **kwargs: ())
    monkeypatch.setattr("edward.services.trading_path_expected_value_service_v012.TradingPathExpectedValueServiceV012.calculate", lambda candidate, candles, **kwargs: SimpleNamespace(expected_value_pct=1.0, edge_reliability_pct=80.0))
    monkeypatch.setattr("edward.services.trading_path_risk_service_v012.TradingPathRiskServiceV012.evaluate", lambda analysis, **kwargs: SimpleNamespace(risk=SimpleNamespace(score=80.0), path_eligible=True))
    monkeypatch.setattr("edward.services.trading_path_opportunity_builder_v012.TradingPathOpportunityBuilderV012.build", lambda analysis, **kwargs: analysis)
    monkeypatch.setattr("edward.services.trading_path_decision_service_v012.TradingPathDecisionServiceV012.decide", lambda analysis: SimpleNamespace(current_state="entry_ready", decision="buy", status="promotable", reasons=()))

    runtime = AnalysisPathRuntimeServiceV012()
    runtime.analyze_paths(instrument_uid="SBER", ticker="SBER", candles=_candles(oos_close=100.0))
    first = (tuple(discovery_inputs), tuple(adaptive_inputs), tuple(validation_inputs))
    discovery_inputs.clear(); adaptive_inputs.clear(); validation_inputs.clear()
    runtime.analyze_paths(instrument_uid="SBER", ticker="SBER", candles=_candles(oos_close=150.0))
    second = (tuple(discovery_inputs), tuple(adaptive_inputs), tuple(validation_inputs))

    assert first == second
    assert discovery_inputs[0] == tuple(_candles()[:72])
    assert adaptive_inputs[0] == tuple(_candles()[:72])
    assert validation_inputs[0][1] == 72
    assert validation_inputs[0][2] == 96
