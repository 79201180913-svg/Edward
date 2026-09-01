from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Sequence

from edward.services.analysis_service import Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088
from edward.services.event_backtest_v088 import EventBacktestV088
from edward.services.event_observation_v086 import EventObservationBuilderV086
from edward.services.market_context_shadow_scoring_v011 import MarketContextShadowScoringServiceV011
from edward.services.market_context_snapshot_v011 import MarketContextSnapshotV011, resolve_context_status
from edward.services.market_regime_context_v011 import MarketRegimeContextBuilderV011
from edward.services.market_volatility_context_v011 import MarketVolatilityContextAnalyzerV011
from edward.services.relative_strength_analyzer_v011 import RelativeStrengthAnalyzerV011
from edward.services.trading_rule_builder_v088 import TradingRuleBuilderV088

logger = logging.getLogger(__name__)
MARKET_CONTEXT_AB_BACKTEST_VERSION = "0.11.0"


@dataclass(frozen=True, slots=True)
class MarketContextABWindowResultV011:
    cutoff_index: int
    as_of: Any
    baseline_top1: str | None
    context_top1: str | None
    baseline_top3: tuple[str, ...]
    context_top3: tuple[str, ...]
    baseline_top1_mean_oos_return_pct: float
    context_top1_mean_oos_return_pct: float
    baseline_top1_win_rate_pct: float
    context_top1_win_rate_pct: float
    baseline_top1_trades: int
    context_top1_trades: int
    baseline_top3_mean_oos_return_pct: float
    context_top3_mean_oos_return_pct: float
    rank_changed: bool


@dataclass(frozen=True, slots=True)
class MarketContextABMetricV011:
    windows: int
    mean_oos_return_pct: float
    median_oos_return_pct: float
    win_rate_pct: float
    total_trades: int
    positive_windows: int


@dataclass(frozen=True, slots=True)
class MarketContextABBacktestResultV011:
    version: str
    window_results: tuple[MarketContextABWindowResultV011, ...]
    baseline_top1: MarketContextABMetricV011
    context_top1: MarketContextABMetricV011
    baseline_top3: MarketContextABMetricV011
    context_top3: MarketContextABMetricV011
    rank_change_rate_pct: float


class MarketContextABBacktestServiceV011:
    """Point-in-time A/B test of baseline vs market-context ranking.

    A candidate is ranked only from candles at or before each cutoff. OOS
    performance is measured only on event observations after the cutoff.
    Market context is built from benchmark candles at or before the same cutoff.
    The service never mutates the production ranking or Quality Gate.
    """

    def __init__(self, analysis_service_factory=AnalysisServiceV08) -> None:
        self.analysis_service_factory = analysis_service_factory
        self.context_regime_builder = MarketRegimeContextBuilderV011()
        self.relative_strength_analyzer = RelativeStrengthAnalyzerV011()
        self.volatility_analyzer = MarketVolatilityContextAnalyzerV011()

    def _snapshot(
        self,
        *,
        instrument_id: str,
        as_of: Any,
        instrument_candles: Sequence[Candle],
        market_candles: Sequence[Candle],
    ) -> MarketContextSnapshotV011:
        instrument_point = tuple(c for c in instrument_candles if c.timestamp <= as_of)
        market_point = tuple(c for c in market_candles if c.timestamp <= as_of)
        market_regime = self.context_regime_builder.build(
            instrument_id="benchmark",
            as_of=as_of,
            candles=market_point,
        )
        relative_strength = self.relative_strength_analyzer.analyze(
            instrument_candles=instrument_point,
            market_candles=market_point,
            as_of=as_of,
            horizon_bars=20,
        )
        volatility = self.volatility_analyzer.analyze(
            instrument_candles=instrument_point,
            market_candles=market_point,
            as_of=as_of,
            horizon_bars=20,
        )
        snapshot = MarketContextSnapshotV011(
            instrument_id=instrument_id,
            as_of=as_of,
            benchmark_id="IMOEX",
            benchmark_supported=True,
            market_regime=market_regime,
            relative_strength=relative_strength,
            volatility=volatility,
            context_status=resolve_context_status(
                benchmark_supported=True,
                market_regime=market_regime,
                relative_strength=relative_strength,
                volatility=volatility,
            ),
        )
        if not snapshot.validate_point_in_time():
            raise ValueError("A/B market context is not point-in-time safe")
        return snapshot

    @staticmethod
    def _candidate_label(item: Any) -> str:
        rule = item.candidate.rule
        return f"{rule.hypothesis}/{rule.regime}/{rule.volatility_bucket}/{rule.direction}/H={rule.horizon}"

    @staticmethod
    def future_observations(candles: Sequence[Candle], cutoff_index: int):
        """Expose only events strictly after the cutoff; future labels are OOS-only."""
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        observations = EventObservationBuilderV086.build(ordered)
        return tuple(item for item in observations if item.index > cutoff_index)

    @staticmethod
    def _evaluate_candidate(candidate: Any, candles: Sequence[Candle], observations: Sequence[Any]) -> tuple[float, float, int]:
        rule = TradingRuleBuilderV088.build(candidate.candidate)
        executable = EventBacktestV088.run(candles, observations, rule)
        returns = tuple(trade.return_pct for trade in executable.trades)
        if not returns:
            return 0.0, 0.0, 0
        return mean(returns), sum(value > 0 for value in returns) / len(returns) * 100.0, len(returns)

    @staticmethod
    def aggregate(values: Sequence[tuple[float, float, int]]) -> MarketContextABMetricV011:
        if not values:
            return MarketContextABMetricV011(0, 0.0, 0.0, 0.0, 0, 0)
        total_trades = sum(item[2] for item in values)
        positive_windows = sum(item[0] > 0 for item in values)
        window_returns = [item[0] for item in values]
        winning_trades = sum(item[1] * item[2] / 100.0 for item in values)
        win_rate = winning_trades / total_trades * 100.0 if total_trades else 0.0
        return MarketContextABMetricV011(
            windows=len(values),
            mean_oos_return_pct=mean(window_returns),
            median_oos_return_pct=median(window_returns),
            win_rate_pct=win_rate,
            total_trades=total_trades,
            positive_windows=positive_windows,
        )

    def run(
        self,
        *,
        instrument_candles: Sequence[Candle],
        market_candles: Sequence[Candle],
        cutoff_indices: Sequence[int],
        instrument_uid: str,
        ticker: str,
        profile: str = "medium_term",
    ) -> MarketContextABBacktestResultV011:
        ordered = tuple(sorted(instrument_candles, key=lambda item: item.timestamp))
        market = tuple(sorted(market_candles, key=lambda item: item.timestamp))
        if not ordered or not market:
            raise ValueError("instrument_candles and market_candles are required")
        full_observations = self.future_observations(ordered, 0)
        window_results: list[MarketContextABWindowResultV011] = []
        baseline_values: list[tuple[float, float, int]] = []
        context_values: list[tuple[float, float, int]] = []
        baseline_top3_values: list[tuple[float, float, int]] = []
        context_top3_values: list[tuple[float, float, int]] = []

        for cutoff_index in cutoff_indices:
            if cutoff_index < 300 or cutoff_index + 1 >= len(ordered):
                continue
            train = ordered[: cutoff_index + 1]
            as_of = train[-1].timestamp
            market_train = tuple(c for c in market if c.timestamp <= as_of)
            if len(market_train) < 22:
                continue
            analysis_service = self.analysis_service_factory()
            adapter = AnalysisTradingPathAdapterV088(analysis_service)
            research = adapter.analyze(
                instrument_uid=instrument_uid,
                ticker=ticker,
                candles=train,
                profile=profile,
            )
            snapshot = self._snapshot(
                instrument_id=instrument_uid,
                as_of=as_of,
                instrument_candles=train,
                market_candles=market_train,
            )
            shadow = MarketContextShadowScoringServiceV011.rank(research.ranked_candidates, snapshot)
            if not research.ranked_candidates or not shadow:
                continue
            baseline_top = research.ranked_candidates[0]
            baseline_top3 = research.ranked_candidates[:3]
            shadow_by_rank = sorted(shadow, key=lambda item: item[1].context_rank)
            context_top = shadow_by_rank[0][0]
            context_top3 = tuple(item[0] for item in shadow_by_rank[:3])
            oos_observations = tuple(item for item in full_observations if item.index > cutoff_index)

            baseline_top_eval = self._evaluate_candidate(baseline_top, ordered, oos_observations)
            context_top_eval = self._evaluate_candidate(context_top, ordered, oos_observations)
            baseline_top3_evals = [self._evaluate_candidate(item, ordered, oos_observations) for item in baseline_top3]
            context_top3_evals = [self._evaluate_candidate(item, ordered, oos_observations) for item in context_top3]

            baseline_top3_mean = mean(value[0] for value in baseline_top3_evals) if baseline_top3_evals else 0.0
            context_top3_mean = mean(value[0] for value in context_top3_evals) if context_top3_evals else 0.0
            baseline_top3_trades = sum(value[2] for value in baseline_top3_evals)
            context_top3_trades = sum(value[2] for value in context_top3_evals)
            baseline_top3_win = (sum(value[1] * value[2] / 100.0 for value in baseline_top3_evals) / baseline_top3_trades * 100.0) if baseline_top3_trades else 0.0
            context_top3_win = (sum(value[1] * value[2] / 100.0 for value in context_top3_evals) / context_top3_trades * 100.0) if context_top3_trades else 0.0
            baseline_top3_values.append((baseline_top3_mean, baseline_top3_win, baseline_top3_trades))
            context_top3_values.append((context_top3_mean, context_top3_win, context_top3_trades))
            baseline_values.append(baseline_top_eval)
            context_values.append(context_top_eval)
            window_results.append(MarketContextABWindowResultV011(
                cutoff_index=cutoff_index,
                as_of=as_of,
                baseline_top1=self._candidate_label(baseline_top),
                context_top1=self._candidate_label(context_top),
                baseline_top3=tuple(self._candidate_label(item) for item in baseline_top3),
                context_top3=tuple(self._candidate_label(item) for item in context_top3),
                baseline_top1_mean_oos_return_pct=baseline_top_eval[0],
                context_top1_mean_oos_return_pct=context_top_eval[0],
                baseline_top1_win_rate_pct=baseline_top_eval[1],
                context_top1_win_rate_pct=context_top_eval[1],
                baseline_top1_trades=baseline_top_eval[2],
                context_top1_trades=context_top_eval[2],
                baseline_top3_mean_oos_return_pct=baseline_top3_mean,
                context_top3_mean_oos_return_pct=context_top3_mean,
                rank_changed=self._candidate_label(baseline_top) != self._candidate_label(context_top),
            ))

        baseline_metric = self.aggregate(baseline_values)
        context_metric = self.aggregate(context_values)
        baseline_top3_metric = self.aggregate(baseline_top3_values)
        context_top3_metric = self.aggregate(context_top3_values)
        changed = sum(item.rank_changed for item in window_results)
        change_rate = changed / len(window_results) * 100.0 if window_results else 0.0
        logger.warning(
            "[V011 MARKET AB SUMMARY] ticker=%s windows=%d rank_change_rate=%.2f baseline_top1_mean=%.4f context_top1_mean=%.4f baseline_top3_mean=%.4f context_top3_mean=%.4f",
            ticker,
            len(window_results),
            change_rate,
            baseline_metric.mean_oos_return_pct,
            context_metric.mean_oos_return_pct,
            baseline_top3_metric.mean_oos_return_pct,
            context_top3_metric.mean_oos_return_pct,
        )
        for item in window_results:
            logger.warning(
                "[V011 MARKET AB WINDOW] ticker=%s cutoff=%d as_of=%s baseline_top1=%s context_top1=%s baseline_oos=%.6f context_oos=%.6f baseline_win=%.2f context_win=%.2f baseline_trades=%d context_trades=%d rank_changed=%s",
                ticker,
                item.cutoff_index,
                item.as_of,
                item.baseline_top1,
                item.context_top1,
                item.baseline_top1_mean_oos_return_pct,
                item.context_top1_mean_oos_return_pct,
                item.baseline_top1_win_rate_pct,
                item.context_top1_win_rate_pct,
                item.baseline_top1_trades,
                item.context_top1_trades,
                item.rank_changed,
            )
        return MarketContextABBacktestResultV011(
            version=MARKET_CONTEXT_AB_BACKTEST_VERSION,
            window_results=tuple(window_results),
            baseline_top1=baseline_metric,
            context_top1=context_metric,
            baseline_top3=baseline_top3_metric,
            context_top3=context_top3_metric,
            rank_change_rate_pct=change_rate,
        )


__all__ = [
    "MARKET_CONTEXT_AB_BACKTEST_VERSION",
    "MarketContextABBacktestResultV011",
    "MarketContextABBacktestServiceV011",
    "MarketContextABMetricV011",
    "MarketContextABWindowResultV011",
]
