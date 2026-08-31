from types import SimpleNamespace

import pytest

from edward.services.research_evidence_report_v086 import ResearchEvidenceReportServiceV086


def _evidence(*, excess, win_rate, sufficient=True):
    return SimpleNamespace(
        hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP", volatility_bucket="High",
        direction="Positive", horizon=5, excess_return_pct=excess,
        win_rate_pct=win_rate, sufficient_sample=sufficient,
    )


def _wf(value, strategy="Breakout"):
    return SimpleNamespace(
        strategy=strategy, hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP",
        volatility_bucket="High", direction="Positive", horizon=5,
        wf_persistence_pct=value,
    )


def test_report_ranks_magnitude_consistency_and_wf_stability_separately():
    evidence = [_evidence(excess=2.0, win_rate=60.0), _evidence(excess=1.0, win_rate=80.0)]
    wf = [_wf(50.0)]
    rows = ResearchEvidenceReportServiceV086.build(evidence, wf, strategy_context="Breakout")
    assert rows[0].magnitude_rank == 1
    assert rows[0].consistency_rank == 2
    assert rows[0].stability_rank == 1


def test_report_requires_explicit_strategy_context():
    with pytest.raises(ValueError, match="strategy_context"):
        ResearchEvidenceReportServiceV086.build([_evidence(excess=1.0, win_rate=60.0)])


def test_report_marks_low_sample_without_promoting_it():
    rows = ResearchEvidenceReportServiceV086.build(
        [_evidence(excess=10.0, win_rate=100.0, sufficient=False)],
        strategy_context="Breakout",
    )
    assert rows[0].research_flag == "LOW_SAMPLE"


def test_report_does_not_create_trading_decision_field():
    rows = ResearchEvidenceReportServiceV086.build(
        [_evidence(excess=3.0, win_rate=70.0)],
        strategy_context="Breakout",
    )
    assert rows[0].research_flag == "INTERESTING"
    assert not hasattr(rows[0], "recommendation")


def test_report_preserves_multiple_strategy_contexts_for_same_cell():
    evidence = [_evidence(excess=2.0, win_rate=70.0)]
    contexts = (
        ("Breakout", (_wf(80.0, "Breakout"),)),
        ("Momentum", (_wf(60.0, "Momentum"),)),
    )
    rows = ResearchEvidenceReportServiceV086.build_from_wf_contexts(evidence, contexts)
    assert len(rows) == 2
    assert {row.strategy_context for row in rows} == {"Breakout", "Momentum"}
    assert {row.wf.wf_persistence_pct for row in rows} == {80.0, 60.0}
