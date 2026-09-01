from edward.domain.strategy_family import (
    STRATEGY_FAMILY_BY_HYPOTHESIS,
    StrategyFamily,
    strategy_family_for_hypothesis,
)


def test_four_legacy_strategies_are_explicit_strategy_families():
    assert StrategyFamily.values() == (
        "Trend Following",
        "Momentum",
        "Breakout",
        "Mean Reversion",
    )


def test_known_hypotheses_map_to_one_strategy_family():
    assert strategy_family_for_hypothesis("BREAKOUT_EXPANSION") is StrategyFamily.BREAKOUT
    assert strategy_family_for_hypothesis("RANGE_BREAK") is StrategyFamily.BREAKOUT
    assert strategy_family_for_hypothesis("IMPULSE_CONTINUATION") is StrategyFamily.MOMENTUM
    assert strategy_family_for_hypothesis("PULLBACK_RECLAIM") is StrategyFamily.MEAN_REVERSION
    assert strategy_family_for_hypothesis("SHOCK_REVERSAL") is StrategyFamily.MEAN_REVERSION
    assert strategy_family_for_hypothesis("GAP_REVERSAL") is StrategyFamily.MEAN_REVERSION


def test_hypothesis_mapping_is_case_insensitive():
    assert strategy_family_for_hypothesis("breakout_expansion") is StrategyFamily.BREAKOUT


def test_unknown_hypothesis_does_not_become_a_tradeable_family():
    assert strategy_family_for_hypothesis("UNKNOWN_HYPOTHESIS") is None


def test_mapping_contains_only_explicitly_supported_hypotheses():
    assert set(STRATEGY_FAMILY_BY_HYPOTHESIS) == {
        "BREAKOUT_EXPANSION",
        "RANGE_BREAK",
        "IMPULSE_CONTINUATION",
        "PULLBACK_RECLAIM",
        "SHOCK_REVERSAL",
        "GAP_REVERSAL",
    }
