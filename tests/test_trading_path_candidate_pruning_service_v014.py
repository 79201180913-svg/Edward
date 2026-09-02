from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.trading_path_candidate_pruning_service_v014 import (
    CandidatePruningConfigV014,
    TradingPathCandidatePruningServiceV014,
)
from edward.services.trading_path_statistical_integrity_service_v014 import (
    StatisticalIntegrityResultV014,
)


def candidate(
    hypothesis: str,
    *,
    regime: str = "TREND_UP",
    horizon: int = 5,
    observations: int = 20,
    excess: float = 1.0,
    win_rate: float = 60.0,
) -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule("uid", "TEST", hypothesis, regime, "Adaptive", "Positive", horizon),
        evidence=TradingPathEvidence(
            observations, 1.0, 0.8, win_rate, 0.2, excess, True,
        ),
        source_version="0.8.14",
    )


def fixed_candidate() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule("uid", "TEST", "BREAKOUT_EXPANSION", "TREND_UP", "Normal", "Positive", 5),
        evidence=TradingPathEvidence(8, 1.0, 0.8, 60.0, 0.2, 0.8, True),
        source_version="fixed:0.8.6",
    )


def integrity(*, valid: bool) -> StatisticalIntegrityResultV014:
    return StatisticalIntegrityResultV014(
        observations=20,
        effective_sample_size=4.0,
        overlap_ratio_pct=80.0,
        mean_return_pct=1.0,
        baseline_return_pct=0.0,
        excess_return_pct=1.0,
        standard_error_pct=0.2,
        z_score=5.0,
        p_value_one_sided=0.000001,
        hypotheses_tested=100,
        adjusted_p_value=0.0001 if valid else 0.1,
        multiple_testing_valid=valid,
        overlap_valid=valid,
        statistically_valid=valid,
    )


def test_fixed_candidates_are_never_pruned():
    fixed = fixed_candidate()
    result = TradingPathCandidatePruningServiceV014.prune([fixed])
    assert result == (fixed,)


def test_weak_adaptive_candidates_are_pruned():
    weak_sample = candidate("ADAPTIVE_RULE:return_20 >= 0.05", observations=11)
    weak_excess = candidate("ADAPTIVE_RULE:return_10 >= 0.03", excess=0.0)
    result = TradingPathCandidatePruningServiceV014.prune([weak_sample, weak_excess])
    assert result == ()


def test_complex_adaptive_rule_is_pruned():
    rule = "ADAPTIVE_RULE:return_20 >= 0.05 AND return_10 >= 0.02 AND body_ratio <= 0.5 AND gap_pct >= 0.1"
    result = TradingPathCandidatePruningServiceV014.prune([candidate(rule)])
    assert result == ()


def test_duplicate_adaptive_rules_are_deduplicated_deterministically():
    first = candidate("ADAPTIVE_RULE:return_20 >= 0.05", excess=1.0)
    second = candidate("ADAPTIVE_RULE:return_20 >= 0.05", excess=0.5)
    result = TradingPathCandidatePruningServiceV014.prune([first, second])
    assert result == (first,)


def test_context_cap_keeps_best_adaptive_candidates():
    candidates = [
        candidate(f"ADAPTIVE_RULE:return_20 >= 0.0{i}", excess=float(i))
        for i in range(1, 7)
    ]
    result = TradingPathCandidatePruningServiceV014.prune(
        candidates,
        config=CandidatePruningConfigV014(max_adaptive_per_context=2),
    )
    assert len(result) == 2
    assert [item.evidence.excess_return_pct for item in result] == [6.0, 5.0]


def test_pruning_does_not_use_oos_persistence():
    item = candidate("ADAPTIVE_RULE:return_20 >= 0.05")
    item = TradingPathCandidate(
        rule=item.rule,
        evidence=TradingPathEvidence(20, 1.0, 0.8, 60.0, 0.2, 1.0, True, wf_persistence_pct=0.0),
        source_version=item.source_version,
    )
    result = TradingPathCandidatePruningServiceV014.prune([item])
    assert result == (item,)


def test_statistical_gate_drops_invalid_adaptive_candidates():
    item = candidate("ADAPTIVE_RULE:return_20 >= 0.05")
    result = TradingPathCandidatePruningServiceV014.prune(
        [item],
        config=CandidatePruningConfigV014(require_statistical_integrity=True),
        statistical_integrity={item: integrity(valid=False)},
    )
    assert result == ()


def test_statistical_gate_keeps_valid_adaptive_candidates():
    item = candidate("ADAPTIVE_RULE:return_20 >= 0.05")
    result = TradingPathCandidatePruningServiceV014.prune(
        [item],
        config=CandidatePruningConfigV014(require_statistical_integrity=True),
        statistical_integrity={item: integrity(valid=True)},
    )
    assert result == (item,)


def test_statistical_gate_requires_integrity_map_when_enabled():
    item = candidate("ADAPTIVE_RULE:return_20 >= 0.05")
    try:
        TradingPathCandidatePruningServiceV014.prune(
            [item],
            config=CandidatePruningConfigV014(require_statistical_integrity=True),
        )
    except ValueError as exc:
        assert "statistical_integrity is required" in str(exc)
    else:
        raise AssertionError("expected statistical integrity map requirement")
