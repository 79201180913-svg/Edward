from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012


def test_runtime_bridge_exposes_canonical_path_analysis(monkeypatch):
    candles = [
        Candle(datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for i in range(120)
    ]

    monkeypatch.setattr(
        "edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run",
        lambda ordered: SimpleNamespace(evidence=()),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v088.TradingPathCandidateServiceV088.promote",
        lambda discovery, *, instrument_uid, ticker: (),
    )

    result = AnalysisPathRuntimeServiceV012().analyze_paths(
        instrument_uid="SBER",
        ticker="SBER",
        candles=candles,
    )

    assert result == ()


def test_runtime_bridge_sorts_candles_before_discovery(monkeypatch):
    timestamps = [
        datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        for i in range(120)
    ]
    shuffled = [timestamps[i] for i in (2, 0, 1, *range(3, 120))]
    candles = [Candle(ts, 100.0, 101.0, 99.0, 100.0, 1000.0) for ts in shuffled]
    captured = []

    monkeypatch.setattr(
        "edward.services.conditional_discovery_service_v086.ConditionalDiscoveryServiceV086.run",
        lambda ordered: captured.append(tuple(item.timestamp for item in ordered)) or SimpleNamespace(evidence=()),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_candidate_service_v088.TradingPathCandidateServiceV088.promote",
        lambda discovery, *, instrument_uid, ticker: (),
    )

    AnalysisPathRuntimeServiceV012().analyze_paths(
        instrument_uid="SBER",
        ticker="SBER",
        candles=candles,
    )

    # v0.8.14 discovery is intentionally TRAIN-only; sorting must therefore
    # be asserted against the chronologically ordered TRAIN partition.
    assert captured == [tuple(sorted(timestamps))[:72]]


def test_runtime_executes_nested_wfo_with_train_only_discovery(monkeypatch):
    candles = [
        Candle(
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
            100.0, 101.0, 99.0, 100.0, 1000.0,
        )
        for i in range(180)
    ]
    calls = []

    def fake_discover(train, *, instrument_uid, ticker):
        calls.append((len(train), train[-1].timestamp))
        return ()

    monkeypatch.setattr(
        AnalysisPathRuntimeServiceV012,
        "_discover_train_candidates",
        staticmethod(fake_discover),
    )

    result = AnalysisPathRuntimeServiceV012().analyze_paths(
        instrument_uid="SBER",
        ticker="SBER",
        candles=candles,
    )

    assert result == ()
    assert calls[:4] == [
        (60, candles[59].timestamp),
        (90, candles[89].timestamp),
        (120, candles[119].timestamp),
        (150, candles[149].timestamp),
    ]
    assert calls[4:] == [(108, candles[107].timestamp)]


def test_runtime_attaches_independent_oos_evidence_to_canonical_analysis(monkeypatch):
    candles = [
        Candle(
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
            100.0 + i,
            101.0 + i,
            99.0 + i,
            100.0 + i,
            1000.0,
        )
        for i in range(180)
    ]
    rule = SimpleNamespace(
        instrument_uid="SBER",
        ticker="SBER",
        hypothesis="TEST",
        regime="TREND_UP",
        volatility_bucket="NORMAL",
        direction="LONG",
        horizon=1,
    )
    candidate = SimpleNamespace(rule=rule)
    validation = SimpleNamespace(promotion_status="validated")
    analysis = SimpleNamespace(
        instrument_uid="SBER",
        ticker="SBER",
        strategy_family="TEST",
        hypothesis="TEST",
        regime="TREND_UP",
        volatility_bucket="NORMAL",
        direction="LONG",
        horizon=1,
        evidence=(),
        validation=validation,
        market_context=SimpleNamespace(),
    )
    evidence_marker = SimpleNamespace(status="READY", candidate_key=("SBER", "SBER", "TEST", "TREND_UP", "NORMAL", "LONG", 1))
    captured = {}

    monkeypatch.setattr(
        AnalysisPathRuntimeServiceV012,
        "_discover_train_candidates",
        staticmethod(lambda train, *, instrument_uid, ticker: (candidate,)),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_analysis_builder_v012.TradingPathAnalysisBuilderV012.build",
        lambda *args, **kwargs: (analysis,),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_oos_validation_service_v012.TradingPathOOSValidationServiceV012.validate",
        lambda *args, **kwargs: (SimpleNamespace(start=144, end=180, observations=10, mean_return_pct=2.0, baseline_return_pct=1.0, excess_return_pct=1.0),),
    )

    def fake_evidence_build(**kwargs):
        captured["evidence_args"] = kwargs
        return evidence_marker

    monkeypatch.setattr(
        "edward.services.trading_path_independent_oos_evidence_service_v015.TradingPathIndependentOOSEvidenceServiceV015.build",
        fake_evidence_build,
    )
    monkeypatch.setattr(
        "edward.services.trading_path_expected_value_service_v012.TradingPathExpectedValueServiceV012.calculate",
        lambda *args, **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_risk_service_v012.TradingPathRiskServiceV012.evaluate",
        lambda *args, **kwargs: SimpleNamespace(risk=SimpleNamespace(score=1.0), path_eligible=True),
    )
    opportunity = SimpleNamespace(
        instrument_uid="SBER",
        ticker="SBER",
        strategy_family="TEST",
        hypothesis="TEST",
        regime="TREND_UP",
        volatility_bucket="NORMAL",
        direction="LONG",
        horizon=1,
        evidence=(),
        validation=validation,
        market_context=SimpleNamespace(),
        opportunity=SimpleNamespace(score=1.0, confidence=1.0, expected_value_pct=1.0, risk_score=1.0, risk_gate=True),
        rank=1,
    )
    monkeypatch.setattr(
        "edward.services.trading_path_opportunity_builder_v012.TradingPathOpportunityBuilderV012.build",
        lambda *args, **kwargs: opportunity,
    )
    monkeypatch.setattr(
        "edward.services.trading_path_decision_service_v012.TradingPathDecisionServiceV012.decide",
        lambda *args, **kwargs: SimpleNamespace(current_state="wait", decision="wait", reasons=()),
    )
    monkeypatch.setattr(
        "edward.services.trading_path_walk_forward_service_v015.TradingPathWalkForwardServiceV015.nested_validate",
        lambda *args, **kwargs: SimpleNamespace(folds=(), candidate_summaries=()),
    )

    result = AnalysisPathRuntimeServiceV012().analyze_paths(
        instrument_uid="SBER",
        ticker="SBER",
        candles=candles,
    )

    assert len(result) == 1
    assert result[0].independent_oos_evidence is evidence_marker
    assert captured["evidence_args"]["candidate_key"] == (
        "SBER", "SBER", "TEST", "TREND_UP", "NORMAL", "LONG", 1,
    )
    assert captured["evidence_args"]["validation_start"] == 108
    assert captured["evidence_args"]["validation_end"] == 144
