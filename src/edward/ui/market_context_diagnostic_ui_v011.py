from __future__ import annotations

import logging
from typing import Any

from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088
from edward.services.market_context_ab_backtest_v011 import MarketContextABBacktestResultV011
from edward.services.market_context_diagnostic_v011 import MarketContextDiagnosticV011
from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011

logger = logging.getLogger(__name__)

_INSTALLED = False
_RUNNING = False
_ORIGINAL_ANALYZE = None


def _log_result(ticker: str, result: MarketContextABBacktestResultV011) -> None:
    baseline = result.baseline_top1
    context = result.context_top1
    baseline3 = result.baseline_top3
    context3 = result.context_top3
    logger.warning(
        "[V011 MARKET DIAGNOSTIC RESULT] ticker=%s windows=%d rank_change_rate=%.2f "
        "baseline_top1_mean=%.6f context_top1_mean=%.6f delta_top1=%.6f "
        "baseline_top1_win=%.2f context_top1_win=%.2f "
        "baseline_top3_mean=%.6f context_top3_mean=%.6f delta_top3=%.6f "
        "baseline_top3_positive_windows=%d context_top3_positive_windows=%d",
        ticker,
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
    for window in result.window_results:
        logger.warning(
            "[V011 MARKET DIAGNOSTIC WINDOW] ticker=%s cutoff=%d as_of=%s baseline_top1=%s "
            "context_top1=%s baseline_oos=%.6f context_oos=%.6f delta=%.6f "
            "baseline_win=%.2f context_win=%.2f rank_changed=%s",
            ticker,
            window.cutoff_index,
            window.as_of,
            window.baseline_top1,
            window.context_top1,
            window.baseline_top1_mean_oos_return_pct,
            window.context_top1_mean_oos_return_pct,
            window.context_top1_mean_oos_return_pct - window.baseline_top1_mean_oos_return_pct,
            window.baseline_top1_win_rate_pct,
            window.context_top1_win_rate_pct,
            window.rank_changed,
        )


def install() -> None:
    global _INSTALLED, _ORIGINAL_ANALYZE
    if _INSTALLED:
        return
    _ORIGINAL_ANALYZE = AnalysisTradingPathAdapterV088.analyze

    def analyze_with_market_diagnostic(self: Any, *args: Any, **kwargs: Any):
        global _RUNNING
        result = _ORIGINAL_ANALYZE(self, *args, **kwargs)
        if _RUNNING:
            return result

        try:
            instrument_uid = kwargs.get("instrument_uid")
            ticker = kwargs.get("ticker")
            candles = kwargs.get("candles")
            if instrument_uid is None or ticker is None or candles is None:
                return result

            snapshot = MarketContextRuntimeServiceV011.last_built_snapshot
            market_candles = MarketContextRuntimeServiceV011.last_built_market_candles
            if snapshot is None or snapshot.instrument_id != str(instrument_uid):
                return result
            if snapshot.context_status != "FULL" or not market_candles:
                logger.warning(
                    "[V011 MARKET DIAGNOSTIC] ticker=%s status=SKIPPED reason=context_unavailable",
                    ticker,
                )
                return result

            _RUNNING = True
            diagnostic = MarketContextDiagnosticV011()
            diagnostic_result = diagnostic.run(
                instrument_candles=tuple(candles),
                market_candles=market_candles,
                instrument_uid=str(instrument_uid),
                ticker=str(ticker),
                profile=str(kwargs.get("profile", "medium_term")),
                cutoff_step=120,
            )
            _log_result(str(ticker), diagnostic_result)
        except Exception:
            logger.exception("[V011 MARKET DIAGNOSTIC] ticker=%s status=ERROR", kwargs.get("ticker", "UNKNOWN"))
        finally:
            _RUNNING = False
        return result

    AnalysisTradingPathAdapterV088.analyze = analyze_with_market_diagnostic
    _INSTALLED = True


__all__ = ["install"]
