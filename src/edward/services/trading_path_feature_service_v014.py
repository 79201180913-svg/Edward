from __future__ import annotations

import logging
from dataclasses import dataclass
from math import isnan
from statistics import pstdev
from typing import Sequence

from edward.services.analysis_service import Candle

logger = logging.getLogger(__name__)
FEATURE_LIBRARY_VERSION = "0.8.14"


@dataclass(frozen=True, slots=True)
class TradingPathFeatureV014:
    """One point-in-time feature value for adaptive Trading Path discovery."""

    name: str
    index: int
    timestamp: object
    value: float | None


class TradingPathFeatureServiceV014:
    """Build a deterministic, point-in-time feature library from candles.

    Every feature at index i is calculated only from candles with position <= i.
    No forward returns, OOS observations, or future market state are used here.
    """

    VERSION = FEATURE_LIBRARY_VERSION
    WINDOWS = (5, 10, 20, 50)

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float | None:
        if denominator == 0:
            return None
        return numerator / denominator

    @staticmethod
    def _mean(values: Sequence[float]) -> float | None:
        return sum(values) / len(values) if values else None

    @staticmethod
    def _slope(values: Sequence[float]) -> float | None:
        if len(values) < 2:
            return None
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        denominator = sum((x - x_mean) ** 2 for x in range(n))
        if denominator == 0:
            return None
        return sum((x - x_mean) * (y - y_mean) for x, y in enumerate(values)) / denominator

    @classmethod
    def _realized_volatility(cls, closes: Sequence[float]) -> float | None:
        returns = [
            current / previous - 1.0
            for previous, current in zip(closes, closes[1:])
            if previous > 0 and current > 0
        ]
        return pstdev(returns) if len(returns) >= 2 else None

    @classmethod
    def _atr_like(cls, candles: Sequence[Candle]) -> float | None:
        if len(candles) < 2:
            return None
        true_ranges: list[float] = []
        for previous, current in zip(candles, candles[1:]):
            previous_close = float(previous.close)
            high = float(current.high)
            low = float(current.low)
            true_ranges.append(max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            ))
        return cls._mean(true_ranges)

    @classmethod
    def _percentile_rank(cls, value: float | None, history: Sequence[float]) -> float | None:
        if value is None or not history:
            return None
        less_or_equal = sum(item <= value for item in history)
        return less_or_equal / len(history) * 100.0

    @classmethod
    def build(cls, candles: Sequence[Candle]) -> tuple[TradingPathFeatureV014, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        if not ordered:
            return ()

        features: list[TradingPathFeatureV014] = []
        for index, candle in enumerate(ordered):
            closes = [float(item.close) for item in ordered[: index + 1]]
            highs = [float(item.high) for item in ordered[: index + 1]]
            lows = [float(item.low) for item in ordered[: index + 1]]
            current_close = closes[-1]
            current_open = float(candle.open)
            current_high = float(candle.high)
            current_low = float(candle.low)

            values: dict[str, float | None] = {}
            for window in cls.WINDOWS:
                close_window = closes[max(0, len(closes) - window):]
                high_window = highs[max(0, len(highs) - window):]
                low_window = lows[max(0, len(lows) - window):]
                values[f"return_{window}"] = (
                    current_close / closes[-window - 1] - 1.0
                    if len(closes) > window and closes[-window - 1] > 0
                    else None
                )
                values[f"distance_to_high_{window}"] = (
                    current_close / max(high_window) - 1.0 if max(high_window) > 0 else None
                )
                values[f"distance_to_low_{window}"] = (
                    current_close / min(low_window) - 1.0 if min(low_window) > 0 else None
                )
                sma = cls._mean(close_window)
                values[f"distance_to_sma_{window}"] = (
                    current_close / sma - 1.0 if sma and sma > 0 else None
                )
                values[f"realized_vol_{window}"] = cls._realized_volatility(close_window)
                values[f"range_pct_{window}"] = (
                    (max(high_window) - min(low_window)) / current_close
                    if current_close > 0 else None
                )

            values["sma10_sma20_spread"] = None
            values["sma20_sma50_spread"] = None
            sma10 = cls._mean(closes[-10:])
            sma20 = cls._mean(closes[-20:])
            sma50 = cls._mean(closes[-50:])
            if sma10 and sma20 and sma20 > 0:
                values["sma10_sma20_spread"] = sma10 / sma20 - 1.0
            if sma20 and sma50 and sma50 > 0:
                values["sma20_sma50_spread"] = sma20 / sma50 - 1.0

            slope20 = cls._slope(closes[-20:])
            values["sma20_slope"] = slope20 / current_close if slope20 is not None and current_close > 0 else None
            values["body_ratio"] = (
                abs(current_close - current_open) / (current_high - current_low)
                if current_high > current_low else None
            )
            values["upper_wick_ratio"] = (
                (current_high - max(current_open, current_close)) / (current_high - current_low)
                if current_high > current_low else None
            )
            values["lower_wick_ratio"] = (
                (min(current_open, current_close) - current_low) / (current_high - current_low)
                if current_high > current_low else None
            )
            values["close_position"] = (
                (current_close - current_low) / (current_high - current_low)
                if current_high > current_low else None
            )
            previous_close = closes[-2] if len(closes) >= 2 else None
            values["gap_pct"] = (
                current_open / previous_close - 1.0
                if previous_close and previous_close > 0 else None
            )
            atr20 = cls._atr_like(ordered[max(0, index - 19): index + 1])
            values["atr_pct"] = atr20 / current_close if atr20 is not None and current_close > 0 else None

            for name, value in values.items():
                if value is not None and isnan(value):
                    value = None
                features.append(TradingPathFeatureV014(name, index, candle.timestamp, value))

        logger.warning(
            "[V014 FEATURE LIBRARY] candles=%d features=%d names=%d version=%s point_in_time=True",
            len(ordered), len(features), len({item.name for item in features}), cls.VERSION,
        )
        return tuple(features)

    @classmethod
    def by_name(cls, candles: Sequence[Candle], name: str) -> tuple[TradingPathFeatureV014, ...]:
        return tuple(item for item in cls.build(candles) if item.name == name)


__all__ = ["FEATURE_LIBRARY_VERSION", "TradingPathFeatureV014", "TradingPathFeatureServiceV014"]
