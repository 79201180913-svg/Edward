from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.analysis_service import Candle
from edward.services.benchmark_instrument_resolver_v011 import BenchmarkInstrumentResolverV011
from edward.services.market_benchmark_resolver_v011 import BenchmarkDefinition
from edward.services.market_context_ab_backtest_v011 import (
    MarketContextABBacktestResultV011,
    MarketContextABBacktestServiceV011,
)
from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088

logger = logging.getLogger(__name__)


class MarketContextDiagnosticV011:
    """Canonical diagnostic facade for point-in-time market-context A/B.

    The facade deliberately sits outside production Quality Gate logic. It
    consumes the same v0.8.8 research adapter used by production analysis and
    compares baseline vs market-aware Top-1/Top-3 selection on future OOS
    observations only.
    """

    def __init__(self, analysis_service_factory=None) -> None:
        self.backtest = MarketContextABBacktestServiceV011(
            analysis_service_factory=analysis_service_factory or __import__(
                "edward.services.analysis_service_v08",
                fromlist=["AnalysisServiceV08"],
            ).AnalysisServiceV08
        )

    @staticmethod
    def cutoffs(candle_count: int, step: int = 120) -> tuple[int, ...]:
        warmup = 300
        oos_tail = 60
        if step <= 0:
            raise ValueError("cutoff step must be positive")
        last_cutoff_exclusive = candle_count - oos_tail
        if last_cutoff_exclusive <= warmup:
            return ()
        return tuple(range(warmup, last_cutoff_exclusive, step))

    def run(
        self,
        *,
        instrument_candles: Sequence[Candle],
        market_candles: Sequence[Candle],
        instrument_uid: str,
        ticker: str,
        profile: str = "medium_term",
        cutoff_step: int = 120,
    ) -> MarketContextABBacktestResultV011:
        instrument = tuple(sorted(instrument_candles, key=lambda item: item.timestamp))
        market = tuple(sorted(market_candles, key=lambda item: item.timestamp))
        if not instrument or not market:
            raise ValueError("instrument_candles and market_candles are required")
        cutoff_indices = self.cutoffs(len(instrument), cutoff_step)
        if not cutoff_indices:
            raise ValueError("Not enough candles for point-in-time A/B diagnostic")
        return self.backtest.run(
            instrument_candles=instrument,
            market_candles=market,
            cutoff_indices=cutoff_indices,
            instrument_uid=instrument_uid,
            ticker=ticker,
            profile=profile,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run point-in-time baseline vs market-context A/B diagnostic."
    )
    parser.add_argument("--instrument-uid", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--days", type=int, default=2400)
    parser.add_argument("--cutoff-step", type=int, default=120)
    parser.add_argument("--profile", default="medium_term")
    parser.add_argument("--log-file", default="runtime/market_context_diagnostic_v011.log")
    return parser.parse_args()


def _configure_logging(log_file: str) -> Path:
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)
    return path


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _number(value: Any) -> float:
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return float(
            Decimal(str(value.get("units", 0)))
            + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        )
    if value is None:
        return 0.0
    return float(value)


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_candles(response: Any) -> tuple[Candle, ...]:
    raw = response.get("candles", []) if isinstance(response, dict) else getattr(response, "candles", [])
    candles: list[Candle] = []
    for item in raw or []:
        timestamp = _field(item, "time", _field(item, "timestamp"))
        if timestamp is None:
            continue
        candles.append(
            Candle(
                timestamp=_timestamp(timestamp),
                open=_number(_field(item, "open", 0.0)),
                high=_number(_field(item, "high", 0.0)),
                low=_number(_field(item, "low", 0.0)),
                close=_number(_field(item, "close", 0.0)),
                volume=_number(_field(item, "volume", 0.0)),
            )
        )
    return tuple(sorted(candles, key=lambda item: item.timestamp))


def main() -> int:
    args = _parse_args()
    log_path = _configure_logging(args.log_file)
    logger.info(
        "[V011 MARKET DIAGNOSTIC START] ticker=%s instrument_uid=%s days=%d cutoff_step=%d profile=%s log_file=%s",
        args.ticker,
        args.instrument_uid,
        args.days,
        args.cutoff_step,
        args.profile,
        log_path,
    )
    client = TInvestAdapterClient()
    try:
        health = client.health()
        logger.info("[V011 MARKET DIAGNOSTIC HEALTH] %s", health)

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=args.days)
        instrument_candles = _parse_candles(
            client.get_candles(
                args.instrument_uid,
                start=start,
                end=end,
                interval="CANDLE_INTERVAL_DAY",
                limit=2400,
            )
        )
        logger.info(
            "[V011 MARKET DIAGNOSTIC] instrument candles=%d start=%s end=%s",
            len(instrument_candles),
            instrument_candles[0].timestamp if instrument_candles else None,
            instrument_candles[-1].timestamp if instrument_candles else None,
        )
        if not instrument_candles:
            raise RuntimeError(f"No candles received for {args.ticker}")

        resolver = BenchmarkInstrumentResolverV011(client.get_indicatives, client.find_instrument)
        benchmark = resolver.resolve(
            BenchmarkDefinition(
                benchmark_id="IMOEX",
                benchmark_kind="EQUITY_MARKET",
                market="MOEX",
                supported=True,
                reason="",
            )
        )
        if not benchmark.instrument_uid:
            raise RuntimeError("IMOEX benchmark UID could not be resolved")
        logger.info("[V011 MARKET DIAGNOSTIC] benchmark=IMOEX uid=%s", benchmark.instrument_uid)

        market_candles = _parse_candles(
            client.get_candles(
                benchmark.instrument_uid,
                start=instrument_candles[0].timestamp,
                end=instrument_candles[-1].timestamp,
                interval="CANDLE_INTERVAL_DAY",
                limit=2400,
            )
        )
        logger.info("[V011 MARKET DIAGNOSTIC] benchmark candles=%d", len(market_candles))
        if not market_candles:
            raise RuntimeError("No IMOEX candles received")

        result = MarketContextDiagnosticV011().run(
            instrument_candles=instrument_candles,
            market_candles=market_candles,
            instrument_uid=args.instrument_uid,
            ticker=args.ticker,
            profile=args.profile,
            cutoff_step=args.cutoff_step,
        )

        baseline = result.baseline_top1
        context = result.context_top1
        baseline3 = result.baseline_top3
        context3 = result.context_top3
        logger.info(
            "[V011 MARKET DIAGNOSTIC RESULT] ticker=%s windows=%d rank_change_rate=%.2f baseline_top1_mean=%.6f context_top1_mean=%.6f delta_top1=%.6f baseline_top1_win=%.2f context_top1_win=%.2f baseline_top3_mean=%.6f context_top3_mean=%.6f delta_top3=%.6f baseline_top3_positive_windows=%d context_top3_positive_windows=%d",
            args.ticker,
            len(result.window_results),
            result.rank_change_rate_pct,
            baseline.mean_oos_return_pct,
            context.mean_oos_return_pct,
            context.mean_oos_return_pct - baseline.mean_oos_return_pct,
            baseline.win_rate_pct,
            context.win_rate_pct,
            baseline3.mean_oos_return_pct,
            context3.mean_oos_return_pct,
            context3.mean_oos_return_pct - baseline3.mean_oos_return_pct,
            baseline3.positive_windows,
            context3.positive_windows,
        )
        logger.info("[V011 MARKET DIAGNOSTIC TOP1] baseline=%s", result.window_results[0].baseline_top1 if result.window_results else None)
        logger.info("[V011 MARKET DIAGNOSTIC TOP1] context=%s", result.window_results[0].context_top1 if result.window_results else None)
        logger.info("[V011 MARKET DIAGNOSTIC END] status=SUCCESS")
        return 0
    except Exception:
        logger.exception("[V011 MARKET DIAGNOSTIC END] status=ERROR")
        return 1
    finally:
        logging.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["MarketContextDiagnosticV011"]
