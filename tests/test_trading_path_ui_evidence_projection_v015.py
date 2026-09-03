from types import SimpleNamespace

from edward.services.trading_path_ui_evidence_projection_v015 import (
    TradingPathUIEvidenceProjectionServiceV015,
)


def _analysis(**overrides):
    values = dict(
        validation=SimpleNamespace(
            statistical_valid=True,
            overlap_valid=True,
            multiple_testing_valid=True,
            wf_persistence_pct=75.0,
        ),
        independent_oos_evidence=SimpleNamespace(
            excess_return_pct=3.4,
            worst_window_excess_pct=1.8,
        ),
        market_context=SimpleNamespace(
            regime_excess_pct=2.1,
            market_excess_pct=1.7,
            relative_strength_pct=1.9,
        ),
        ev_evidence=SimpleNamespace(
            expected_value_pct=2.7,
            ev_ci_low_pct=0.8,
            ev_ci_high_pct=4.6,
            edge_reliability_pct=91.0,
            confidence_score=86.0,
        ),
        opportunity=SimpleNamespace(expected_value_pct=2.7, confidence=86.0),
        quality_gate=SimpleNamespace(
            risk_gate=True,
            passed=True,
            reasons=(),
        ),
        current_state="entry_ready",
        decision="buy",
        status="promotable",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_projection_reads_canonical_evidence_without_recomputing_it():
    result = TradingPathUIEvidenceProjectionServiceV015.build(_analysis())

    assert result.statistical_gate is True
    assert result.wf_persistence_pct == 75.0
    assert result.oos_excess_pct == 3.4
    assert result.oos_worst_window_excess_pct == 1.8
    assert result.regime_excess_pct == 2.1
    assert result.market_excess_pct == 1.7
    assert result.ev_pct == 2.7
    assert result.ev_ci_low_pct == 0.8
    assert result.ev_ci_high_pct == 4.6
    assert result.ev_reliability_pct == 91.0
    assert result.confidence_score == 86.0
    assert result.risk_gate is True
    assert result.quality_gate_passed is True
    assert result.decision == "buy"
    assert result.status == "promotable"
    assert result.quality_gate_reasons == ()


def test_projection_preserves_quality_gate_failure_and_reason():
    result = TradingPathUIEvidenceProjectionServiceV015.build(
        _analysis(
            quality_gate=SimpleNamespace(
                risk_gate=True,
                passed=False,
                reasons=("OOS_GATE_FAILED", "MARKET_CONTEXT_GATE_FAILED"),
            ),
            current_state="invalid",
            decision="pass",
            status="rejected",
        )
    )

    assert result.quality_gate_passed is False
    assert result.quality_gate_reasons == (
        "OOS_GATE_FAILED",
        "MARKET_CONTEXT_GATE_FAILED",
    )
    assert result.current_state == "invalid"
    assert result.decision == "pass"
    assert result.status == "rejected"


def test_projection_falls_back_to_canonical_validation_wf_persistence():
    analysis = _analysis()
    delattr(analysis, "wf_summary") if hasattr(analysis, "wf_summary") else None

    result = TradingPathUIEvidenceProjectionServiceV015.build(analysis)

    assert result.wf_persistence_pct == 75.0


def test_projection_does_not_use_opportunity_ev_when_ev_evidence_exists():
    result = TradingPathUIEvidenceProjectionServiceV015.build(
        _analysis(
            ev_evidence=SimpleNamespace(
                expected_value_pct=3.5,
                ev_ci_low_pct=1.0,
                ev_ci_high_pct=5.0,
                edge_reliability_pct=95.0,
                confidence_score=90.0,
            ),
            opportunity=SimpleNamespace(expected_value_pct=99.0, confidence=1.0),
        )
    )

    assert result.ev_pct == 3.5
    assert result.confidence_score == 90.0
