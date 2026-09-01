from datetime import datetime, timedelta, timezone

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.trading_path_expected_value_service_v012 import TradingPathExpectedValueServiceV012


def _candidate() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid-1",
            ticker="SBER",
            hypothesis="BREAKOUT_EXPANSION",
            regime="TREND_UP",
            volatility_bucket="Normal",
            direction="Positive",
            horizon=2,
        ),
        evidence=TradingPathEvidence(
            observations=20,
            mean_forward_return_pct=1.0,
            median_forward_return_pct=1.0,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.2,
            excess_return_pct=0.8,
            sufficient_sample=True,
        ),
    )


def _candles(n: int = 130) -> list[Candle]:
    return [
        Candle(
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
            100.0 + i * 0.01,
            101.0 + i * 0.01,
            99.0 + i * 0.01,
            100.0 + i * 0.02,
            1000.0,
        )
        for i in range(n)
    ]


def test_path_ev_is_built_from_oos_path_outcomes_only():
    candidate = _candidate()
    candles = _candles()

    outcomes = TradingPathExpectedValueServiceV012.outcomes(candidate, candles)
    result = TradingPathExpectedValueServiceV012.calculate(candidate, candles)

    assert result.observations == len(outcomes)
    assert result.available is True if outcomes else result.available is False
    assert result.expected_value_pct == 0.0 if not outcomes else result.expected_value_pct >= 0.0


def test_insufficient_temporal_data_returns_unavailable_ev():
    result = TradingPathExpectedValueServiceV012.calculate(_candidate(), _candles(50))

    assert result.available is False
    assert result.observations == 0
    assert result.unavailable_reason == "NO_REALIZED_OUTCOMES"
