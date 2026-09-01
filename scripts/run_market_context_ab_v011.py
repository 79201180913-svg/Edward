from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.analysis_service import Candle
from edward.services.benchmark_instrument_resolver_v011 import BenchmarkInstrumentResolverV011
from edward.services.market_context_ab_backtest_v011 import MarketContextABBacktestServiceV011
from edward.services.market_benchmark_resolver_v011 import BenchmarkDefinition

logger = logging.getLogger(__name__)


def build_cutoff_indices(candle_count: int, step: int = 120) -> tuple[int, ...]:
    if candle_count <= 360:
        return ()
    if step <= 0:
        raise ValueError("cutoff step must be positive")
    return tuple(range(300, candle_count - 60, step))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run point-in-time baseline vs market-context A/B backtest.")
    parser.add_argument("--instrument-uid", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--days", type=int, default=2400)
    parser.add_argument("--cutoff-step", type=int, default=120)
    return parser.parse_args()


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _number(value: Any) -> float:
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return float(Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000"))
    if value is None:
        return 0.0
    return float(value)


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_candles(response: Any) -> list[Candle]:
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
    candles.sort(key=lambda candle: candle.timestamp)
    return candles


def _load_candles(client: TInvestAdapterClient, instrument_uid: str, days: int) -> list[Candle]:
    if days <= 0:
        raise ValueError("days must be positive")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    response = client.get_candles(
        instrument_uid,
        start=start,
        end=end,
        interval="CANDLE_INTERVAL_DAY",
        limit=2400,
    )
    candles = _parse_candles(response)
    if not candles:
        raise RuntimeError(f"No candles received for {instrument_uid}")
    return candles


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    args = _parse_args()
    client = TInvestAdapterClient()

    instrument_candles = _load_candles(client, args.instrument_uid, args.days)
    start = instrument_candles[0].timestamp
    end = instrument_candles[-1].timestamp

    resolver = BenchmarkInstrumentResolverV011(client.get_indicatives, client.find_instrument)
    benchmark = resolver.resolve(BenchmarkDefinition(
        benchmark_id="IMOEX",
        benchmark_kind="EQUITY_MARKET",
        market="MOEX",
        supported=True,
        reason="",
    ))

    if not benchmark.instrument_uid:
        raise RuntimeError("IMOEX benchmark UID could not be resolved")

    market_response = client.get_candles(
        benchmark.instrument_uid,
        start=start,
        end=end,
        interval="CANDLE_INTERVAL_DAY",
        limit=2400,
    )
    market_candles = _parse_candles(market_response)
    if not market_candles:
        raise RuntimeError(f"No benchmark candles received for {benchmark.instrument_uid}")

    cutoff_indices = build_cutoff_indices(len(instrument_candles), args.cutoff_step)
    if not cutoff_indices:
        raise RuntimeError("Not enough candles for the requested A/B configuration")

    logger.warning(
        "[V011 MARKET AB RUNNER] ticker=%s benchmark=IMOEX instrument_candles=%d market_candles=%d cutoffs=%s",
        args.ticker,
        len(instrument_candles),
        len(market_candles),
        cutoff_indices,
    )

    result = MarketContextABBacktestServiceV011().run(
        instrument_candles=instrument_candles,
        market_candles=market_candles,
        cutoff_indices=cutoff_indices,
        instrument_uid=args.instrument_uid,
        ticker=args.ticker,
    )

    logger.warning(
        "[V011 MARKET AB RESULT] ticker=%s windows=%d rank_change_rate=%.2f "
        "baseline_top1_mean=%.6f context_top1_mean=%.6f "
        "baseline_top1_win=%.2f context_top1_win=%.2f "
        "baseline_top3_mean=%.6f context_top3_mean=%.6f",
        args.ticker,
        len(result.window_results),
        result.rank_change_rate_pct,
        result.baseline_top1.mean_oos_return_pct,
        result.context_top1.mean_oos_return_pct,
        result.baseline_top1.win_rate_pct,
        result.context_top1.win_rate_pct,
        result.baseline_top3.mean_oos_return_pct,
        result.context_top3.mean_oos_return_pct,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
