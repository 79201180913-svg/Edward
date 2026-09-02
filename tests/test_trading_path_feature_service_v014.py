from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.trading_path_feature_service_v014 import TradingPathFeatureServiceV014


def make_candles(count: int = 60) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles: list[Candle] = []
    for index in range(count):
        close = 100.0 + index
        candles.append(
            Candle(
                timestamp=start + timedelta(hours=index),
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1000.0 + index,
            )
        )
    return candles


def feature(features, name: str, index: int):
    return next(item for item in features if item.name == name and item.index == index)


def test_feature_library_is_deterministic_and_point_in_time():
    candles = make_candles()
    features = TradingPathFeatureServiceV014.build(candles)
    repeated = TradingPathFeatureServiceV014.build(candles)

    assert features == repeated
    assert len(features) > 0
    assert {item.name for item in features} >= {
        "return_5",
        "return_10",
        "return_20",
        "distance_to_high_20",
        "distance_to_low_20",
        "distance_to_sma_20",
        "realized_vol_20",
        "sma10_sma20_spread",
        "sma20_sma50_spread",
        "sma20_slope",
        "body_ratio",
        "upper_wick_ratio",
        "lower_wick_ratio",
        "close_position",
        "gap_pct",
        "atr_pct",
    }


def test_return_5_uses_only_current_and_prior_candles():
    candles = make_candles()
    features = TradingPathFeatureServiceV014.build(candles)
    before = feature(features, "return_5", 30).value

    changed = list(candles)
    changed[31] = Candle(
        timestamp=changed[31].timestamp,
        open=9999.0,
        high=10000.0,
        low=9998.0,
        close=10000.0,
        volume=1.0,
    )
    after = feature(TradingPathFeatureServiceV014.build(changed), "return_5", 30).value
    assert after == before


def test_window_features_are_none_until_enough_history_exists():
    features = TradingPathFeatureServiceV014.build(make_candles())

    assert feature(features, "return_20", 19).value is None
    assert feature(features, "return_20", 20).value is not None
    assert feature(features, "sma20_sma50_spread", 20).value is None
    assert feature(features, "sma20_sma50_spread", 50).value is not None


def test_by_name_returns_only_requested_feature():
    candles = make_candles()
    selected = TradingPathFeatureServiceV014.by_name(candles, "gap_pct")

    assert selected
    assert all(item.name == "gap_pct" for item in selected)
    assert len(selected) == len(candles)


def test_empty_input_returns_empty_tuple():
    assert TradingPathFeatureServiceV014.build([]) == ()
