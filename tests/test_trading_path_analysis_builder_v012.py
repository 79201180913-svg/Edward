from datetime import datetime, timedelta, timezone

from edward.domain import TradingPathAnalysisStatus, TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.trading_path_analysis_builder_v012 import TradingPathAnalysisBuilderV012


def _candidate() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid-1",
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
            median_forward_return_pct=0.8,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.2,
            excess_return_pct=0.8,
            sufficient_sample=True,
        ),
    )


def _candles(count: int = 140) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(start + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0 + i * 0.05, 1000.0)
        for i in range(count)
    ]


def test_builder_returns_canonical_path_analysis():
    result = TradingPathAnalysisBuilderV012.build([_candidate()], _candles())

    assert len(result) == 1
    path = result[0]
    assert path.ticker == "SBER"
    assert path.strategy_family == "Breakout"
    assert path.hypothesis == "BREAKOUT_EXPANSION"
    assert path.validation.positive_oos_windows_pct is not None
    assert path.decision.value == "wait"


def test_builder_does_not_promote_without_positive_oos_evidence():
    candidate = _candidate()
    candles = [
        Candle(datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for i in range(140)
    ]

    result = TradingPathAnalysisBuilderV012.build([candidate], candles)

    assert result[0].status is TradingPathAnalysisStatus.REJECTED
    assert result[0].decision.value == "wait"
