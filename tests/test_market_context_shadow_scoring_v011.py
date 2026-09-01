from types import SimpleNamespace

from edward.services.market_context_shadow_scoring_v011 import MarketContextShadowScoringServiceV011


def _ranked(hypothesis, regime="TREND_UP", volatility="Normal", score=50.0):
    rule = SimpleNamespace(
        hypothesis=hypothesis,
        regime=regime,
        volatility_bucket=volatility,
        direction="Positive",
        horizon=5,
    )
    candidate = SimpleNamespace(rule=rule)
    return SimpleNamespace(candidate=candidate, score=score)


def _snapshot(market_regime="RANGE", relative_classification="OUTPERFORMING", excess=2.3, volatility="LOWER_THAN_MARKET"):
    regime_result = SimpleNamespace(
        regime=market_regime,
        strategy_compatibility={
            "Trend Following": 25.0,
            "Momentum": 30.0,
            "Breakout": 20.0,
            "Mean Reversion": 100.0,
        },
    )
    relative = SimpleNamespace(classification=relative_classification, excess_return_pct=excess)
    vol = SimpleNamespace(classification=volatility, relative_volatility=0.26)
    return SimpleNamespace(
        context_status="FULL",
        benchmark_id="IMOEX",
        market_regime=SimpleNamespace(result=regime_result),
        relative_strength=relative,
        volatility=vol,
    )


def test_shadow_scoring_does_not_mutate_baseline_ranked_items():
    ranked = (
        _ranked("IMPULSE_CONTINUATION", score=60.0),
        _ranked("PULLBACK_RECLAIM", score=59.0),
    )
    original_scores = tuple(item.score for item in ranked)
    original_order = tuple(item.candidate.rule.hypothesis for item in ranked)

    shadow = MarketContextShadowScoringServiceV011.rank(ranked, _snapshot())

    assert tuple(item.score for item in ranked) == original_scores
    assert tuple(item.candidate.rule.hypothesis for item in ranked) == original_order
    assert len(shadow) == 2


def test_range_market_prefers_mean_reversion_over_momentum_in_shadow():
    ranked = (
        _ranked("IMPULSE_CONTINUATION", score=60.0),
        _ranked("PULLBACK_RECLAIM", score=60.0),
    )

    shadow = MarketContextShadowScoringServiceV011.rank(ranked, _snapshot())
    by_hypothesis = {item.candidate.rule.hypothesis: score for item, score in shadow}

    assert by_hypothesis["PULLBACK_RECLAIM"].context_adjusted_score > by_hypothesis["IMPULSE_CONTINUATION"].context_adjusted_score


def test_outperformance_and_lower_volatility_are_visible_as_positive_shadow_evidence():
    ranked = (_ranked("IMPULSE_CONTINUATION", volatility="Normal", score=50.0),)
    shadow = MarketContextShadowScoringServiceV011.rank(ranked, _snapshot())
    score = shadow[0][1]

    assert score.score_delta > 0.0
    assert score.relative_strength_component > 0.0
    assert score.volatility_component > 0.0
    assert score.confidence_hint_delta > 0.0


def test_unavailable_context_produces_no_shadow_result():
    ranked = (_ranked("IMPULSE_CONTINUATION", score=50.0),)
    unavailable = SimpleNamespace(context_status="UNAVAILABLE")

    assert MarketContextShadowScoringServiceV011.rank(ranked, unavailable) == ()
