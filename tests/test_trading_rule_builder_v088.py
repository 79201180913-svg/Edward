import pytest

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.trading_rule_builder_v088 import (
    EntryTriggerV088,
    ExitTriggerV088,
    TradingRuleBuilderV088,
)


def _candidate(horizon: int = 5) -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule("uid", "SBER", "BREAKOUT_EXPANSION", "TREND_DOWN", "High", "Positive", horizon),
        evidence=TradingPathEvidence(20, 1.5, 1.4, 65.0, 0.2, 1.3, True),
    )


def test_builder_preserves_candidate_dimensions():
    result = TradingRuleBuilderV088.build(_candidate(5))
    assert result.instrument_uid == "uid"
    assert result.ticker == "SBER"
    assert result.hypothesis == "BREAKOUT_EXPANSION"
    assert result.regime == "TREND_DOWN"
    assert result.volatility_bucket == "High"
    assert result.direction == "Positive"
    assert result.horizon == 5


def test_builder_uses_explicit_deterministic_entry_and_exit_contract():
    result = TradingRuleBuilderV088.build(_candidate())
    assert result.entry_trigger is EntryTriggerV088.EVENT_CLOSE
    assert result.exit_trigger is ExitTriggerV088.TIME_HORIZON


def test_builder_rejects_invalid_horizon():
    with pytest.raises(ValueError, match="horizon must be positive"):
        TradingRuleBuilderV088.build(_candidate(0))
