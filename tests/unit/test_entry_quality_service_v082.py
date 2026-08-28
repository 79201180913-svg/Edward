from edward.services.entry_quality_service_v082 import EntryQualityServiceV082


def test_strong_fundamentals_do_not_create_buy_without_entry_signal():
    result = EntryQualityServiceV082.evaluate(
        fundamental_score=95,
        fundamental_momentum_score=95,
        regime="BULLISH",
        microstructure_score=90,
        volume_pressure_score=90,
        current_signal={"direction": "NEUTRAL"},
        profile="long_term",
    )
    assert result.entry_signal is False
    assert result.entry_blocked is True
    assert result.block_reason == "NO_BULLISH_ENTRY_SIGNAL"


def test_strong_entry_is_supported_by_fundamentals_for_long_term():
    result = EntryQualityServiceV082.evaluate(
        fundamental_score=90,
        fundamental_momentum_score=80,
        regime="BULLISH",
        microstructure_score=85,
        volume_pressure_score=75,
        current_signal={"direction": "BUY"},
        profile="long_term",
    )
    assert result.entry_signal is True
    assert result.score >= 55


def test_speculative_profile_weights_momentum_and_microstructure_more_than_long_term():
    values = dict(
        fundamental_score=40,
        fundamental_momentum_score=95,
        regime="BULLISH",
        microstructure_score=95,
        volume_pressure_score=90,
        current_signal={"direction": "BUY"},
    )
    long_term = EntryQualityServiceV082.evaluate(**values, profile="long_term")
    speculative = EntryQualityServiceV082.evaluate(**values, profile="speculative")
    assert speculative.score > long_term.score


def test_hostile_regime_blocks_entry_even_with_strong_fundamentals():
    result = EntryQualityServiceV082.evaluate(
        fundamental_score=100,
        fundamental_momentum_score=100,
        regime="HOSTILE",
        microstructure_score=100,
        volume_pressure_score=100,
        current_signal={"direction": "BUY"},
        profile="long_term",
    )
    assert result.entry_signal is False
    assert result.block_reason == "REGIME_NOT_SUPPORTIVE"


def test_execution_permission_blocks_entry():
    result = EntryQualityServiceV082.evaluate(
        fundamental_score=100,
        fundamental_momentum_score=100,
        regime="BULLISH",
        current_signal={"direction": "BUY"},
        execution_allowed=False,
    )
    assert result.entry_signal is False
    assert result.block_reason == "EXECUTION_NOT_ALLOWED"
