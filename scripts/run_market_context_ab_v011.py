from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.analysis_service import Candle
from edward.services.benchmark_instrument_resolver_v011 import BenchmarkInstrumentResolverV011
from edward.services.market_context_ab_backtest_v011 import MarketContextABBacktestServiceV011
from edward.services.market_benchmark_resolver_v011 import BenchmarkDefinition

logger = logging.getLogger(__name__)


def build_cutoff_indices(candle_count: int, step: int = 120) -> tuple[int, ...]:
    if step <= 0:
        raise ValueError("cutoff step must be positive")
    warmup = 300
    oos_tail = 60
    first_cutoff = warmup
    last_cutoff_exclusive = candle_count - oos_tail
    if last_cutoff_exclusive <= first_cutoff:
        return ()
    return tuple(range(first_cutoff, last_cutoff_exclusive, step))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run point-in-time baseline vs market-context A/B backtest.")
    parser.add_argument("--instrument-uid", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--days", type=int, default=2400)
    parser.add_argument("--cutoff-step", type=int, default=120)
    parser.add_argument("--log-file", default="runtime/market_context_ab_v011.log")
    return parser.parse_args()


def _configure_logging(log_file: str) -> Path:
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
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
        candles.append(Candle(timestamp=_timestamp(timestamp), open=_number(_field(item, "open", 0.0)), high=_number(_field(item, "high", 0.0)), low=_number(_field(item, "low", 0.0)), close=_number(_field(item, "close", 0.0)), volume=_number(_field(item, "volume", 0.0))))
    candles.sort(key=lambda item: item.timestamp)
    return candles


def _load_candles(client: TInvestAdapterClient, instrument_uid: str, days: int) -> list[Candle]:
    if days <= 0:
        raise ValueError("days must be positive")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    logger.info("[V011 MARKET AB] loading candles instrument=%s days=%d start=%s end=%s", instrument_uid, days, start.isoformat(), end.isoformat())
    response = client.get_candles(instrument_uid, start=start, end=end, interval="CANDLE_INTERVAL_DAY", limit=2400)
    candles = _parse_candles(response)
    logger.info("[V011 MARKET AB] loaded candles instrument=%s count=%d", instrument_uid, len(candles))
    if not candles:
        raise RuntimeError(f"No candles received for {instrument_uid}")
    return candles


def main() -> int:
    args = _parse_args()
    log_path = _configure_logging(args.log_file)
    logger.info("[V011 MARKET AB START] ticker=%s instrument_uid=%s days=%d cutoff_step=%d log_file=%s", args.ticker, args.instrument_uid, args.days, args.cutoff_step, log_path)
    client = TInvestAdapterClient()
    try:
        health = client.health()
        logger.info("[V011 MARKET AB HEALTH] %s", health)
        instrument_candles = _load_candles(client, args.instrument_uid, args.days)
        start = instrument_candles[0].timestamp
        end = instrument_candles[-1].timestamp
        logger.info("[V011 MARKET AB] resolving benchmark=IMOEX")
        resolver = BenchmarkInstrumentResolverV011(client.get_indicatives, client.find_instrument)
        benchmark = resolver.resolve(BenchmarkDefinition(benchmark_id="IMOEX", benchmark_kind="EQUITY_MARKET", market="MOEX", supported=True, reason=""))
        logger.info("[V011 MARKET AB] resolved benchmark=IMOEX uid=%s", benchmark.instrument_uid)
        if not benchmark.instrument_uid:
            raise RuntimeError("IMOEX benchmark UID could not be resolved")
        response = client.get_candles(benchmark.instrument_uid, start=start, end=end, interval="CANDLE_INTERVAL_DAY", limit=2400)
        market_candles = _parse_candles(response)
        logger.info("[V011 MARKET AB] loaded benchmark candles uid=%s count=%d", benchmark.instrument_uid, len(market_candles))
        if not market_candles:
            raise RuntimeError(f"No benchmark candles received for {benchmark.instrument_uid}")
        cutoff_indices = build_cutoff_indices(len(instrument_candles), args.cutoff_step)
        logger.info("[V011 MARKET AB] cutoffs=%s", cutoff_indices)
        if not cutoff_indices:
            raise RuntimeError("Not enough candles for the requested A/B configuration")
        result = MarketContextABBacktestServiceV011().run(instrument_candles=instrument_candles, market_candles=market_candles, cutoff_indices=cutoff_indices, instrument_uid=args.instrument_uid, ticker=args.ticker)
        logger.info("[V011 MARKET AB RESULT] ticker=%s windows=%d rank_change_rate=%.2f baseline_top1_mean=%.6f context_top1_mean=%.6f baseline_top1_win=%.2f context_top1_win=%.2f baseline_top3_mean=%.6f context_top3_mean=%.6f", args.ticker, len(result.window_results), result.rank_change_rate_pct, result.baseline_top1.mean_oos_return_pct, result.context_top1.mean_oos_return_pct, result.baseline_top1.win_rate_pct, result.context_top1.win_rate_pct, result.baseline_top3.mean_oos_return_pct, result.context_top3.mean_oos_return_pct)
        logger.info("[V011 MARKET AB END] status=SUCCESS")
        return 0
    except Exception:
        logger.exception("[V011 MARKET AB END] status=ERROR")
        raise
    finally:
        logging.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
