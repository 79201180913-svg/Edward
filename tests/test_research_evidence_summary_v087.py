from types import SimpleNamespace

from edward.services.research_evidence_summary_v087 import ResearchEvidenceSummaryServiceV087


def _row(excess: float, win_rate: float, persistence: float | None, flag: str = "INTERESTING"):
    wf = None if persistence is None else SimpleNamespace(wf_persistence_pct=persistence)
    evidence = SimpleNamespace(excess_return_pct=excess, win_rate_pct=win_rate)
    return SimpleNamespace(evidence=evidence, wf=wf, research_flag=flag)


def test_summary_separates_magnitude_consistency_and_stability():
    rows = [_row(3.0, 60.0, 40.0), _row(2.0, 80.0, 90.0), _row(1.0, 70.0, None)]
    summary = ResearchEvidenceSummaryServiceV087.build(rows)
    assert summary.total_cells == 3
    assert summary.top_magnitude[0].evidence.excess_return_pct == 3.0
    assert summary.top_consistency[0].evidence.win_rate_pct == 80.0
    assert summary.top_stability[0].wf.wf_persistence_pct == 90.0


def test_summary_counts_research_flags_without_filtering_data():
    rows = [_row(3.0, 70.0, 80.0), _row(10.0, 100.0, 100.0, "LOW_SAMPLE"), _row(-1.0, 30.0, 20.0, "NO_POSITIVE_EXCESS")]
    summary = ResearchEvidenceSummaryServiceV087.build(rows)
    assert summary.interesting == 1
    assert summary.low_sample == 1
    assert summary.no_positive_excess == 1
    assert summary.total_cells == 3


def test_summary_limit_is_bounded():
    rows = [_row(float(index), 50.0, float(index)) for index in range(20)]
    summary = ResearchEvidenceSummaryServiceV087.build(rows, limit=5)
    assert len(summary.top_magnitude) == 5
    assert len(summary.top_consistency) == 5
    assert len(summary.top_stability) == 5
