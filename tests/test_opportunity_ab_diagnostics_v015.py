from types import SimpleNamespace

from edward.services.opportunity_ab_diagnostics_v015 import OpportunityABDiagnosticsV015


def _item(*, decision: str, score: float, hypotheses=()):
    paths = tuple(SimpleNamespace(hypothesis=h) for h in hypotheses)
    return SimpleNamespace(
        opportunity_score=score,
        decision=decision,
        status="VALID",
        canonical_opportunity=SimpleNamespace(canonical_results=paths),
    )


def test_ab_metrics_count_canonical_adaptive_and_fixed_paths():
    result = OpportunityABDiagnosticsV015.summarize(
        "canonical",
        [
            _item(decision="BUY", score=80.0, hypotheses=("BREAKOUT_EXPANSION", "ADAPTIVE_RULE:x")),
            _item(decision="WAIT", score=60.0, hypotheses=("PULLBACK_RECLAIM",)),
            _item(decision="PASS", score=30.0),
        ],
    )

    assert result.source == "canonical"
    assert result.instruments == 3
    assert result.analyzed == 3
    assert result.path_count == 3
    assert result.adaptive_paths == 1
    assert result.fixed_paths == 2
    assert result.buy == 1
    assert result.wait == 1
    assert result.pass_count == 1
    assert result.average_opportunity_score == 170.0 / 3.0


def test_ab_comparison_exposes_coverage_paths_and_buy_deltas():
    legacy = [
        _item(decision="WAIT", score=60.0, hypotheses=("BREAKOUT_EXPANSION",)),
    ]
    canonical = [
        _item(decision="BUY", score=80.0, hypotheses=("BREAKOUT_EXPANSION", "ADAPTIVE_RULE:x")),
        _item(decision="WAIT", score=55.0, hypotheses=("ADAPTIVE_RULE:y",)),
    ]

    result = OpportunityABDiagnosticsV015.compare(legacy, canonical)

    assert result.coverage_delta == 1
    assert result.path_delta == 2
    assert result.adaptive_paths_added == 2
    assert result.buy_delta == 1


def test_legacy_results_without_canonical_payload_remain_valid_baseline():
    result = OpportunityABDiagnosticsV015.summarize(
        "legacy",
        [SimpleNamespace(opportunity_score=50.0, decision="PASS", status="VALID", canonical_opportunity=None)],
    )

    assert result.instruments == 1
    assert result.analyzed == 0
    assert result.path_count == 0
    assert result.adaptive_paths == 0
    assert result.fixed_paths == 0
