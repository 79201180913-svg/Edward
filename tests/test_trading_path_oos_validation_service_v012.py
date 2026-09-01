from datetime import datetime, timedelta, timezone

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012


def _cand() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid",
            ticker="SBER",
            hypothesis="BREAKOUT_EXPANSION",
            regime="RANGE",
            volatility_bucket="Normal",
            direction="Positive",
            horizon=2,
        ),
        evidence=TradingPathEvidence(
            observations=10,
            mean_forward_return_pct=1.0,
            median_forward_return_pct=1.0,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.0,
            excess_return_pct=1.0,
            sufficient_sample=True,
        ),
    )


def _candles(n=80):
    return [
        Candle(
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
            100.0 + i * 0.2,
            101.0 + i * 0.2,
            99.0 + i * 0.2,
            100.0 + i * 0.2,
            1000.0,
        )
        for i in range(n)
    ]


def test_oos_validation_uses_fixed_path_and_returns_temporal_windows():
    result = TradingPathOOSValidationServiceV012.validate(_cand(), _candles(), windows=3, test_size=10)

    assert len(result) == 3
    assert [item.index for item in result] == [1, 2, 3]
    assert result[0].start < result[0].end
    assert result[0].end == result[1].start


def test_oos_validation_never_uses_discovery_evidence_as_oos_result():
    result = TradingPathOOSValidationServiceV012.validate(_cand(), _candles(), windows=2, test_size=10)

    assert all(item.observations >= 0 for item in result)
    assert all(item.excess_return_pct != 1.0 or item.observations == 0 for item in result)


def test_build_validation_produces_path_level_validation_summary():
    result = TradingPathOOSValidationServiceV012.build_validation(_cand(), _candles(), windows=2, test_size=10)

    assert result.candidate.rule.hypothesis == "BREAKOUT_EXPANSION"
    assert result.validation.wf_persistence_pct is not None
    assert result.validation.positive_oos_windows_pct is not None
    assert result.validation.statistical_valid in (True, False)
    assert result.validation.promotion_status in ("validated", "rejected")


def test_oos_validation_returns_empty_when_not_enough_data():
    result = TradingPathOOSValidationServiceV012.validate(_cand(), _candles(20), windows=4, test_size=10)

    assert result == ()
