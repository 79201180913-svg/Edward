from types import SimpleNamespace

from edward.ui.analysis_ui_v0815 import _pipeline_snapshot, _render_pipeline_summary, _render_projection


class _TextStub:
    def __init__(self):
        self.value = ""
        self.state = None

    def configure(self, **kwargs):
        self.state = kwargs.get("state", self.state)

    def delete(self, *_args):
        self.value = ""

    def insert(self, _index, value):
        self.value = value


def _analysis():
    return SimpleNamespace(
        instrument_uid="uid",
        ticker="SBER",
        hypothesis="ADAPTIVE_RULE:test",
        regime="TREND_UP",
        volatility_bucket="Adaptive",
        direction="Positive",
        horizon=20,
        strategy_family="Adaptive Discovery",
        validation=SimpleNamespace(
            statistical_valid=True,
            overlap_valid=True,
            multiple_testing_valid=True,
            wf_persistence_pct=75.0,
            wf_worst_window_excess_pct=1.8,
            promotion_status="validated",
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
        quality_gate=SimpleNamespace(
            risk_gate=True,
            passed=True,
            reasons=(),
        ),
        current_state="entry_ready",
        decision="buy",
        status="promotable",
    )


def test_canonical_ui_renders_full_v0815_evidence_chain():
    text = _TextStub()

    _render_projection(text, _analysis())

    assert "Statistical Evidence: PASS" in text.value
    assert "WF Persistence: +75.00%" in text.value
    assert "WF Worst Window: +1.80%" in text.value
    assert "Independent OOS Edge: +3.40%" in text.value
    assert "OOS Worst Window: +1.80%" in text.value
    assert "Regime Excess: +2.10%" in text.value
    assert "Market Excess: +1.70%" in text.value
    assert "EV: +2.70%" in text.value
    assert "CI: +0.80% … +4.60%" in text.value
    assert "EV Reliability: +91.00%" in text.value
    assert "Risk Gate: PASS" in text.value
    assert "Current State: entry_ready" in text.value
    assert "QUALITY GATE: PASS" in text.value
    assert "DECISION: BUY" in text.value


def test_canonical_ui_renders_gate_failure_reason():
    analysis = _analysis()
    analysis.quality_gate = SimpleNamespace(
        risk_gate=True,
        passed=False,
        reasons=("OOS_GATE_FAILED", "MARKET_CONTEXT_GATE_FAILED"),
    )
    analysis.current_state = "invalid"
    analysis.decision = "pass"
    analysis.status = "rejected"
    text = _TextStub()

    _render_projection(text, analysis)

    assert "QUALITY GATE: FAIL" in text.value
    assert "REASON: OOS_GATE_FAILED, MARKET_CONTEXT_GATE_FAILED" in text.value
    assert "DECISION: PASS" in text.value
    assert "STATUS: REJECTED" in text.value


def test_canonical_ui_does_not_display_opportunity_as_authoritative_ev():
    analysis = _analysis()
    analysis.opportunity = SimpleNamespace(expected_value_pct=99.0, confidence=1.0)
    text = _TextStub()

    _render_projection(text, analysis)

    assert "EV: +2.70%" in text.value
    assert "EV: +99.00%" not in text.value
    assert "legacy confidence are diagnostic only" in text.value


def test_canonical_pipeline_snapshot_separates_validation_from_wf_stability():
    validated = _analysis()
    rejected = SimpleNamespace(
        instrument_uid="uid",
        ticker="SBER",
        hypothesis="FIXED:test",
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=10,
        strategy_family="Fixed",
        validation=SimpleNamespace(promotion_status="rejected"),
    )
    nested = SimpleNamespace(
        folds=(1, 2, 3, 4),
        candidate_summaries=((validated, SimpleNamespace(passed=False)),),
    )

    snapshot = _pipeline_snapshot((validated, rejected), nested, ())

    assert snapshot["discovered"] == 2
    assert snapshot["validated"] == 1
    assert snapshot["adaptive"] == 1
    assert snapshot["wf_stable"] == 0
    assert snapshot["nested_folds"] == 4
    assert snapshot["nested_candidates"] == 1
    assert snapshot["final"] == 0


def test_canonical_pipeline_summary_explains_zero_final_paths():
    snapshot = {
        "discovered": 26,
        "validated": 9,
        "adaptive": 18,
        "wf_stable": 0,
        "nested_folds": 4,
        "nested_candidates": 31,
        "final": 0,
        "buy": 0,
        "wait": 0,
        "pass": 0,
    }
    text = _TextStub()

    _render_pipeline_summary(text, snapshot)

    assert "Discovery candidates: 26" in text.value
    assert "Statistically validated: 9" in text.value
    assert "Nested WF stable: 0 / 31 evaluated candidates" in text.value
    assert "Nested WF folds: 4" in text.value
    assert "Final paths: 0" in text.value
    assert "validation and final promotion are separate stages" in text.value
