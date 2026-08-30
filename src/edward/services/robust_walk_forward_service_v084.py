from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Any, Iterable, Sequence

from edward.services.economic_viability_service_v084 import EconomicViabilityServiceV084
from edward.services.parameter_zone_v084 import ParameterZoneServiceV084, ParameterZoneV084
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestResult, ResearchBacktestService
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult, RobustWalkForwardService, WalkForwardWindowResult, ParameterStability

ROBUST_WF_V084_VERSION = "0.8.4"
logger = logging.getLogger(__name__)
_ACTIVE_MAX_DRAWDOWN: contextvars.ContextVar[float | None] = contextvars.ContextVar("edward_v084_max_train_drawdown_pct", default=None)
_ACTIVE_MIN_TRADES: contextvars.ContextVar[int] = contextvars.ContextVar("edward_v084_min_train_trades", default=1)
_ACTIVE_STRATEGY: contextvars.ContextVar[str] = contextvars.ContextVar("edward_v084_strategy", default="unknown")
_ACTIVE_ZONES: contextvars.ContextVar[list[ParameterZoneV084] | None] = contextvars.ContextVar("edward_v084_parameter_zones", default=None)
_ACTIVE_TRAIN_TRADES: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar("edward_v084_selected_train_trades", default=None)
_ACTIVE_NO_TRADE_WINDOWS: contextvars.ContextVar[list[int] | None] = contextvars.ContextVar("edward_v084_no_trade_windows", default=None)


class NoViableTrainWindowV084(ValueError):
    """Signals that the current Train window has no economically viable candidate."""


@dataclass(frozen=True, slots=True)
class RobustWalkForwardResultV084(RobustWalkForwardResult):
    parameter_zone_diagnostics: tuple[ParameterZoneV084, ...] = ()
    selected_train_trades: tuple[int, ...] = ()
    no_trade_windows: tuple[int, ...] = ()
    evaluated_windows: int = 0


class RobustWalkForwardServiceV084(RobustWalkForwardService):
    VERSION = ROBUST_WF_V084_VERSION

    @classmethod
    def _select_robust_parameters(cls, candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]]) -> tuple[dict[str, Any], ResearchBacktestResult, float]:
        max_drawdown_pct = _ACTIVE_MAX_DRAWDOWN.get()
        min_train_trades = _ACTIVE_MIN_TRADES.get()
        strategy = _ACTIVE_STRATEGY.get()
        viable: list[tuple[dict[str, Any], ResearchBacktestResult]] = []
        logger.warning("[V084 WF VIABILITY FILTER] candidates=%d max_train_dd=%s min_train_trades=%d", len(candidates), max_drawdown_pct, min_train_trades)
        for params, result in candidates:
            decision = EconomicViabilityServiceV084.evaluate(result, min_excess_return_pct=0.0, max_drawdown_pct=max_drawdown_pct, min_trades=min_train_trades)
            logger.warning("[V084 WF CANDIDATE] params=%s eligible=%s reasons=%s train_excess=%.4f train_return=%.4f train_dd=%.4f trades=%d", params, decision.eligible, decision.reasons, result.excess_return_pct, result.net_return_pct, result.max_drawdown_pct, result.trades)
            if decision.eligible:
                viable.append((params, result))
        logger.warning("[V084 WF VIABILITY RESULT] total=%d viable=%d rejected=%d", len(candidates), len(viable), len(candidates) - len(viable))
        if not viable:
            logger.warning("[V084 WF NO TRADE WINDOW] strategy=%s reason=NO_VIABLE_TRAIN action=CONTINUE", strategy)
            raise NoViableTrainWindowV084("No economically viable Train parameter candidate")
        selected = super()._select_robust_parameters(viable)
        train_trades = _ACTIVE_TRAIN_TRADES.get()
        if train_trades is not None:
            train_trades.append(int(selected[1].trades))
        zone = ParameterZoneServiceV084.evaluate(strategy=strategy, candidates=candidates, viable=viable, anchor_parameters=selected[0])
        zones = _ACTIVE_ZONES.get()
        if zones is not None:
            zones.append(zone)
        zone_risk = "STABLE_ZONE" if zone.stable else "POINT_OPTIMUM"
        logger.warning("[V084 PARAMETER ZONE RISK] strategy=%s risk=%s representative=%s robust_winner=%s viable=%d/%d viability_pct=%.2f stability=%.2f", strategy, zone_risk, zone.representative_parameters, selected[0], zone.viable_candidates, zone.candidates, zone.viability_pct, zone.neighborhood_stability_pct)
        logger.warning("[V084 WF VIABLE SELECTION] selected=%s robust_train_score=%.2f viable_candidates=%d zone_risk=%s selected_train_trades=%d", selected[0], selected[2], len(viable), zone_risk, selected[1].trades)
        return selected

    @staticmethod
    def _with_diagnostics(result: RobustWalkForwardResult, zones: Sequence[ParameterZoneV084], train_trades: Sequence[int], no_trade_windows: Sequence[int], evaluated_windows: int = 0) -> RobustWalkForwardResultV084:
        return RobustWalkForwardResultV084(
            strategy=result.strategy, windows=result.windows,
            mean_test_return_pct=result.mean_test_return_pct, median_test_return_pct=result.median_test_return_pct,
            std_test_return_pct=result.std_test_return_pct, worst_test_return_pct=result.worst_test_return_pct,
            best_test_return_pct=result.best_test_return_pct, mean_test_drawdown_pct=result.mean_test_drawdown_pct,
            mean_test_sharpe=result.mean_test_sharpe, positive_return_windows=result.positive_return_windows,
            risk_ok_windows=result.risk_ok_windows, positive_sharpe_windows=result.positive_sharpe_windows,
            return_consistency_pct=result.return_consistency_pct, risk_consistency_pct=result.risk_consistency_pct,
            sharpe_consistency_pct=result.sharpe_consistency_pct, robustness_score=result.robustness_score,
            parameter_stability=result.parameter_stability, version=result.version,
            parameter_zone_diagnostics=tuple(zones), selected_train_trades=tuple(train_trades), no_trade_windows=tuple(no_trade_windows),
            evaluated_windows=evaluated_windows,
        )

    @classmethod
    def run(cls, *, candles: Iterable, strategy: str, parameter_grid, signal_factory, train_size: int, test_size: int, costs: BacktestCostModel | None = None, max_drawdown_pct: float | None = None, min_train_trades: int = 1):
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if train_size < 2 or test_size < 1:
            raise ValueError("train_size must be >= 2 and test_size must be >= 1")
        if not parameter_grid:
            raise ValueError("parameter_grid cannot be empty")
        expected_windows = max(0, (len(ordered) - train_size) // test_size)
        logger.warning("[V084 WF START] strategy=%s candles=%d train=%d test=%d expected_windows=%d grid=%d max_dd=%s min_train_trades=%d", strategy, len(ordered), train_size, test_size, expected_windows, len(parameter_grid), max_drawdown_pct, min_train_trades)
        windows = []
        exposures = []
        transfer_matches = 0
        transfer_gaps = []
        criterion_matches = {key: 0 for key in ("excess_return", "sharpe", "sortino", "return_dd", "composite")}
        criterion_gaps = {key: [] for key in criterion_matches}
        stability_margins = []
        stability_neighborhoods = []
        stability_confidences = []
        shadow_changed = 0
        shadow_deltas = []
        history = []
        zones = []
        train_trades = []
        no_trade_windows = []
        max_dd_token = _ACTIVE_MAX_DRAWDOWN.set(max_drawdown_pct)
        min_trades_token = _ACTIVE_MIN_TRADES.set(min_train_trades)
        strategy_token = _ACTIVE_STRATEGY.set(strategy)
        zones_token = _ACTIVE_ZONES.set(zones)
        train_trades_token = _ACTIVE_TRAIN_TRADES.set(train_trades)
        no_trade_token = _ACTIVE_NO_TRADE_WINDOWS.set(no_trade_windows)
        try:
            start = 0
            while start + train_size + test_size <= len(ordered):
                train = ordered[start:start + train_size]
                test = ordered[start + train_size:start + train_size + test_size]
                window_index = len(windows)
                candidates = []
                for params in parameter_grid:
                    train_result = ResearchBacktestService.run(candles=train, strategy=strategy, parameters=params, signal_fn=signal_factory(strategy, params), costs=costs)
                    candidates.append((dict(params), train_result))
                try:
                    selected_params, train_result, robust_train_score = cls._select_robust_parameters(candidates)
                except NoViableTrainWindowV084:
                    no_trade_windows.append(window_index)
                    train_trades.append(0)
                    zone = ParameterZoneServiceV084.evaluate(strategy=strategy, candidates=candidates, viable=(), anchor_parameters=None)
                    zones.append(zone)
                    window = WalkForwardWindowResult(window_index, train[0].timestamp, train[-1].timestamp, test[0].timestamp, test[-1].timestamp, {}, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
                    windows.append(window)
                    exposures.append(0.0)
                    logger.warning("[V084 WF NO TRADE WINDOW RESULT] strategy=%s window=%d train=%s..%s test=%s..%s params={} train_score=0.0000 oos_return=0.0000 trades=0", strategy, window_index, train[0].timestamp, train[-1].timestamp, test[0].timestamp, test[-1].timestamp)
                    start += test_size
                    continue
                cls._log_parameter_leaderboard(strategy=strategy, window_index=window_index, candidates=candidates, selected_params=selected_params)
                cls._log_robust_selection(strategy=strategy, window_index=window_index, candidates=candidates, selected_params=selected_params, selected_score=robust_train_score)
                margin, neighborhood, confidence = cls._log_parameter_stability(strategy=strategy, window_index=window_index, candidates=candidates, selected_params=selected_params)
                stability_margins.append(margin)
                stability_neighborhoods.append(neighborhood)
                stability_confidences.append(confidence)
                oos_candidates = []
                for params, _ in candidates:
                    oos_result = ResearchBacktestService.run(candles=test, strategy=strategy, parameters=params, signal_fn=signal_factory(strategy, params), costs=costs)
                    oos_candidates.append((dict(params), oos_result))
                matches, gaps = cls._log_selection_criteria_diagnostics(strategy=strategy, window_index=window_index, train_candidates=candidates, oos_candidates=oos_candidates, production_selected_params=selected_params)
                for criterion, matched in matches.items():
                    criterion_matches[criterion] += int(matched)
                    criterion_gaps[criterion].append(gaps[criterion])
                transfer_match, transfer_gap = cls._log_oos_parameter_transfer(strategy=strategy, window_index=window_index, candidates=oos_candidates, selected_params=selected_params)
                if transfer_match:
                    transfer_matches += 1
                transfer_gaps.append(transfer_gap)
                _, changed, shadow_delta = cls._log_parameter_transfer_shadow(strategy=strategy, window_index=window_index, candidates=candidates, oos_candidates=oos_candidates, baseline_parameters=selected_params, history=history)
                if changed:
                    shadow_changed += 1
                shadow_deltas.append(shadow_delta)
                test_result = next(result for params, result in oos_candidates if params == selected_params)
                exposures.append(test_result.exposure_pct)
                window = WalkForwardWindowResult(window_index, train[0].timestamp, train[-1].timestamp, test[0].timestamp, test[-1].timestamp, dict(selected_params), robust_train_score, test_result.net_return_pct, test_result.benchmark_return_pct, test_result.excess_return_pct, test_result.max_drawdown_pct, test_result.sharpe, test_result.sortino, test_result.trades)
                windows.append(window)
                cls._append_oos_candidate_history(strategy=strategy, window_index=window_index, oos_candidates=oos_candidates, selection_confidence_value=confidence, history=history)
                logger.warning("[V084 WF WINDOW] strategy=%s window=%d train=%s..%s test=%s..%s params=%s train_excess=%.4f robust_train_score=%.2f oos_return=%.4f benchmark=%.4f excess=%.4f dd=%.4f sharpe=%.4f sortino=%.4f trades=%d", strategy, window.index, window.train_start, window.train_end, window.test_start, window.test_end, window.parameters, train_result.excess_return_pct, window.train_score, window.test_net_return_pct, window.test_benchmark_return_pct, window.test_excess_return_pct, window.test_max_drawdown_pct, window.test_sharpe, window.test_sortino, window.test_trades)
                cls._log_window_activity(strategy=strategy, window=window, test_result=test_result)
                start += test_size
            if not windows:
                logger.warning("[V084 WF EMPTY] strategy=%s candles=%d train=%d test=%d", strategy, len(ordered), train_size, test_size)
                return cls._with_diagnostics(cls._empty(strategy), zones, train_trades, no_trade_windows, 0)

            evaluation_windows = [window for window in windows if window.index not in no_trade_windows]
            returns = [i.test_net_return_pct for i in evaluation_windows]
            drawdowns = [i.test_max_drawdown_pct for i in evaluation_windows]
            sharpes = [i.test_sharpe for i in evaluation_windows]
            count = len(evaluation_windows)
            if count == 0:
                logger.warning("[V084 WF NO EVALUABLE OOS] strategy=%s windows=%d no_trade_windows=%d", strategy, len(windows), len(no_trade_windows))
                return cls._with_diagnostics(cls._empty(strategy), zones, train_trades, no_trade_windows, 0)
            positive = sum(v > 0 for v in returns)
            risk_ok = sum(max_drawdown_pct is None or v <= max_drawdown_pct for v in drawdowns)
            positive_sharpe = sum(v > 0 for v in sharpes)
            return_consistency = positive / count * 100
            risk_consistency = risk_ok / count * 100
            sharpe_consistency = positive_sharpe / count * 100
            stability = cls._parameter_stability(evaluation_windows)
            dispersion_penalty = pstdev(returns) / max(abs(mean(returns)), 1.0) * 10
            performance_consistency = max(0.0, min(100.0, 100.0 - dispersion_penalty))
            robustness = round(return_consistency * .35 + risk_consistency * .20 + sharpe_consistency * .15 + stability.stability_pct * .15 + performance_consistency * .15, 2)
            result = RobustWalkForwardResult(strategy=strategy, windows=tuple(windows), mean_test_return_pct=mean(returns), median_test_return_pct=median(returns), std_test_return_pct=pstdev(returns) if len(returns) > 1 else 0.0, worst_test_return_pct=min(returns), best_test_return_pct=max(returns), mean_test_drawdown_pct=mean(drawdowns), mean_test_sharpe=mean(sharpes), positive_return_windows=positive, risk_ok_windows=risk_ok, positive_sharpe_windows=positive_sharpe, return_consistency_pct=return_consistency, risk_consistency_pct=risk_consistency, sharpe_consistency_pct=sharpe_consistency, robustness_score=robustness, parameter_stability=stability)
            result_v084 = cls._with_diagnostics(result, zones, train_trades, no_trade_windows, count)
            active_windows = sum(i.test_trades > 0 for i in evaluation_windows)
            logger.warning("[V084 WF ACTIVITY RESULT] strategy=%s windows=%d evaluated_windows=%d active_windows=%d inactive_windows=%d active_pct=%.2f total_trades=%d mean_exposure=%.2f", strategy, len(windows), count, active_windows, count - active_windows, active_windows / count * 100, sum(i.test_trades for i in evaluation_windows), mean(exposures))
            logger.warning("[V084 WF NO TRADE RESULT] strategy=%s no_trade_windows=%d no_trade_pct=%.2f", strategy, len(no_trade_windows), len(no_trade_windows) / len(windows) * 100)
            logger.warning("[V084 WF RESULT] strategy=%s windows=%d evaluated_windows=%d robustness=%.2f mean_oos_return=%.4f mean_oos_dd=%.4f mean_oos_sharpe=%.4f", strategy, len(windows), count, result_v084.robustness_score, result_v084.mean_test_return_pct, result_v084.mean_test_drawdown_pct, result_v084.mean_test_sharpe)
            return result_v084
        finally:
            _ACTIVE_MAX_DRAWDOWN.reset(max_dd_token)
            _ACTIVE_MIN_TRADES.reset(min_trades_token)
            _ACTIVE_STRATEGY.reset(strategy_token)
            _ACTIVE_ZONES.reset(zones_token)
            _ACTIVE_TRAIN_TRADES.reset(train_trades_token)
            _ACTIVE_NO_TRADE_WINDOWS.reset(no_trade_token)

    @staticmethod
    def _empty(strategy: str) -> RobustWalkForwardResult:
        return RobustWalkForwardResult(strategy=strategy, windows=(), mean_test_return_pct=0.0, median_test_return_pct=0.0, std_test_return_pct=0.0, worst_test_return_pct=0.0, best_test_return_pct=0.0, mean_test_drawdown_pct=0.0, mean_test_sharpe=0.0, positive_return_windows=0, risk_ok_windows=0, positive_sharpe_windows=0, return_consistency_pct=0.0, risk_consistency_pct=0.0, sharpe_consistency_pct=0.0, robustness_score=0.0, parameter_stability=ParameterStability(0, 0, 0.0, ()))


__all__ = ["ROBUST_WF_V084_VERSION", "NoViableTrainWindowV084", "RobustWalkForwardResultV084", "RobustWalkForwardServiceV084"]
