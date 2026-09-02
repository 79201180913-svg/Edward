from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.trading_path_analysis_builder_v012 import TradingPathAnalysisBuilderV012


def _candles(count=120):
    return [
        Candle(
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
            100.0,
            101.0,
            99.0,
            100.0,
            1000.0,
        )
        for i in range(count)
    ]


def test_runtime_runs_canonical_path_stages(monkeypatch):
    candidate = SimpleNamespace(
        rule=SimpleNamespace(
            instrument_uid="SBER", ticker="SBER", hypothesis="H1", regime="RANGE",
            volatility_bucket="Normal", direction="Positive", horizon=5,
        )
    )
    analysis = SimpleNamespace(
        instrument_uid="SBER", ticker="SBER", strategy_family="H1", hypothesis="H1",
        regime="RANGE", volatility_bucket="Normal", direction="Positive", horizon=5,
        evidence=SimpleNamespace(), validation=SimpleNamespace(promotion_status="validated"),
        market_context=SimpleNamespace(), opportunity=SimpleNamespace(),
        current_state=SimpleNamespace(), decision=SimpleNamespace(), status=SimpleNamespace(), rank=1,
    )
    observations = (SimpleNamespace(index=90, hypothesis="H1", regime="RANGE", volatility_bucket="Normal", direction="Positive"),)
    observation_builds = []

    monkeypatch.setattr(
        "edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run",
        lambda candles: SimpleNamespace(evidence=()),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v088.TradingPathCandidateServiceV088.promote",
        lambda result, **kwargs: (candidate,),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.from_fixed",
        lambda discovery, **kwargs: (candidate,),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v014.TradingPathCandidateServiceV014.combine",
        lambda fixed, adaptive, **kwargs: (candidate,),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_pruning_service_v014.TradingPathCandidatePruningServiceV014.prune",
        lambda candidates, **kwargs: tuple(candidates),
    )
    monkeypatch.setattr(
        TradingPathAnalysisBuilderV012, "build", lambda candidates, candles, **kwargs: (analysis,)
    )
    monkeypatch.setattr(
        "edward.services.event_observation_v086.EventObservationBuilderV086.build",
        lambda candles: observation_builds.append(tuple(candles)) or observations,
    )
    monkeypatch.setattr(
        "edward.services.trading_path_oos_validation_service_v012.TradingPathOOSValidationServiceV012.validate",
        lambda candidate, candles, **kwargs: (),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_expected_value_service_v012.TradingPathExpectedValueServiceV012.calculate",
        lambda candidate, candles, **kwargs: SimpleNamespace(expected_value_pct=1.0, edge_reliability_pct=80.0),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_risk_service_v012.TradingPathRiskServiceV012.evaluate",
        lambda analysis, **kwargs: SimpleNamespace(risk=SimpleNamespace(score=80.0), path_eligible=True),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_opportunity_builder_v012.TradingPathOpportunityBuilderV012.build",
        lambda analysis, **kwargs: SimpleNamespace(**analysis.__dict__) if hasattr(analysis, "__dict__") else analysis,
    )
    monkeypatch.setattr(
        "edward.services.trading_path_decision_service_v012.TradingPathDecisionServiceV012.decide",
        lambda analysis: SimpleNamespace(current_state="entry_ready", decision="buy", status="promotable", reasons=()),
    )

    result = AnalysisPathRuntimeServiceV012().analyze_paths(
        instrument_uid="SBER", ticker="SBER", candles=_candles()
    )

    assert len(result) == 1
    assert result[0].decision == "buy"
    assert len(observation_builds) == 1
