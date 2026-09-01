from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.analysis_service import Candle
from edward.services.benchmark_instrument_resolver_v011 import BenchmarkInstrumentResolverV011
from edward.services.market_context_ab_backtest_v011 import MarketContextABBacktestServiceV011

logger = logging.getLogger(__name__)


def _parse_candles(response: dict) -> list[Candle]:
    from edward.ui.analysis_ui_v04 import _parse_candles as parse_candles
    return parse_candles(response)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run point-in-time baseline vs market-context A/B backtest.")
    parser.add_argument("--instrument-uid", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--days", type=int, default=2400)
    parser.add_argument("--cutoff-step", type=int, default=120)
    return parser.parse_args()


def _load_candles(client: TInvestAdapterClient, instrument_uid: str, days: int) -> list[Candle]:
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
    benchmark = resolver.resolve(type("Benchmark", (), {
        "benchmark_id": "IMOEX",
        "benchmark_kind": "EQUITY_MARKET",
        "market": "MOEX",
        "supported": True,
        "reason": "",
    })())

    response = client.get_candles(
        benchmark.instrument_uid,
        start=start,
        end=end,
        interval="CANDLE_INTERVAL_DAY",
        limit=2400,
    )
    market_candles = _parse_candles(response)
    if not market_candles:
        raise RuntimeError(f"No benchmark candles received for {benchmark.instrument_uid}")

    cutoff_indices = tuple(range(300, max(300, len(instrument_candles) - 60), args.cutoff_step))
    result = MarketContextABBacktestServiceV011().run(
        instrument_candles=instrument_candles,
        market_candles=market_candles,
        cutoff_indices=cutoff_indices,
        instrument_uid=args.instrument_uid,
        ticker=args.ticker,
    )

    logger.warning(
        "[V011 MARKET AB RUNNER] ticker=%s benchmark=IMOEX instrument_candles=%d market_candles=%d cutoffs=%s",
        args.ticker,
        len(instrument_candles),
        len(market_candles),
        cutoff_indices,
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
