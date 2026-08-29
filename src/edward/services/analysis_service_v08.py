from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.quality_gate_diagnostics_v0822 import QualityGateDiagnostics, QualityGateDiagnosticsServiceV0822
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestService
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult, RobustWalkForwardService

logger = logging.getLogger(__name__)
ANALYSIS_V08_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class AnalysisV08Diagnostics:
    regime_confidence: float
    regime: str
    robustness_by_strategy: dict[str, float]
    quality_gate_by_strategy: dict[str, QualityGateDiagnostics]


class AnalysisServiceV08:
    """v0.8 analytical facade with the v0.7 AnalysisResult contract."""

    STRATEGIES = ("Trend Following", "Momentum", "Breakout", "Mean Reversion")
    PROFILES = {
        "long_term": {"train": 360, "test": 90, "max_drawdown_pct": 30.0, "min_stability_pct": 60.0},
        "medium_term": {"train": 240, "test": 60, "max_drawdown_pct": 25.0, "min_stability_pct": 60.0},
        "speculative": {"train": 120, "test": 30, "max_drawdown_pct": 35.0, "min_stability_pct": 55.0},
    }

    def __init__(self, *, costs: BacktestCostModel | None = None) -> None:
        self.costs = costs or BacktestCostModel()
        self.last_diagnostics: AnalysisV08Diagnostics | None = None

    @staticmethod
    def _grid(strategy: str, profile: str) -> list[dict[str, Any]]:
        if strategy == "Trend Following":
            return [{"fast": f, "slow": s} for f, s in ((10, 30), (20, 50), (30, 90))]
        if strategy == "Momentum":
            values = (20, 40, 80) if profile == "long_term" else (10, 20, 40)
            return [{"lookback": v} for v in values]
        if strategy == "Breakout":
            values = (10, 20, 40) if profile == "speculative" else (20, 40, 80)
            return [{"lookback": v} for v in values]
        return [{"lookback": v, "deviation": d} for v in (10, 20, 40) for d in (1.5, 2.0, 3.0)]

    @staticmethod
    def _signal_factory(strategy: str, parameters: dict[str, Any]):
        return lambda candles, index: ResearchBacktestService.simple_signal(strategy, candles, parameters, index)

    def _robust(self, candles: list[Candle], strategy: str, profile: str) -> RobustWalkForwardResult:
        cfg = self.PROFILES[profile]
        parameter_grid = self._grid(strategy, profile)
        candle_count = len(candles)
        window_size = cfg["train"] + cfg["test"]
        available_windows = max(0, (candle_count - window_size) // cfg["test"] + 1) if candle_count >= window_size else 0
        minimum_windows = 5
        required_candles = window_size + cfg["test"] * (minimum_windows - 1)
        logger.info(
            "[WALK FORWARD] strategy=%s profile=%s candles=%d train=%d test=%d window_size=%d available_windows=%d min_required_windows=%d required_candles=%d parameter_candidates=%d",
            strategy,
            profile,
            candle_count,
            cfg["train"],
            cfg["test"],
            window_size,
            available_windows,
            minimum_windows,
            required_candles,
            len(parameter_grid),
        )
        if available_windows < minimum_windows:
            logger.warning(
                "[WALK FORWARD] strategy=%s status=INSUFFICIENT_DATA reason=NOT_ENOUGH_WINDOWS available_windows=%d required_windows=%d candles=%d required_candles=%d",
                strategy,
                available_windows,
                minimum_windows,
                candle_count,
                required_candles,
            )
        else:
            logger.info(
                "[WALK FORWARD] strategy=%s status=DATA_SUFFICIENT available_windows=%d required_windows=%d",
                strategy,
                available_windows,
                minimum_windows,
            )

        result = RobustWalkForwardService.run(
            candles=candles,
            strategy=strategy,
            parameter_grid=parameter_grid,
            signal_factory=self._signal_factory,
            train_size=cfg["train"],
            test_size=cfg["test"],
            costs=self.costs,
            max_drawdown_pct=cfg["max_drawdown_pct"],
        )

        if not result.windows:
            logger.warning(
                "[WALK FORWARD] strategy=%s status=NO_WINDOWS completed_windows=0 reason=NO_COMPLETE_TRAIN_TEST_WINDOW",
                strategy,
            )
        else:
            for window in result.windows:
                logger.info(
                    "[WALK FORWARD WINDOW] strategy=%s index=%d train=%s..%s test=%s..%s parameters=%s train_score=%.4f oos_return=%.4f oos_excess=%.4f drawdown=%.4f sharpe=%.4f sortino=%.4f trades=%d",
                    strategy,
                    window.index,
                    window.train_start,
                    window.train_end,
                    window.test_start,
                    window.test_end,
                    window.parameters,
                    window.train_score,
                    window.test_net_return_pct,
                    window.test_excess_return_pct,
                    window.test_max_drawdown_pct,
                    window.test_sharpe,
                    window.test_sortino,
                    window.test_trades,
                )
            logger.info(
                "[WALK FORWARD SUMMARY] strategy=%s completed_windows=%d positive_return=%d/%d risk_ok=%d/%d positive_sharpe=%d/%d parameter_stability=%.2f robustness=%.2f",
                strategy,
                len(result.windows),
                result.positive_return_windows,
                len(result.windows),
                result.risk_ok_windows,
                len(result.windows),
                result.positive_sharpe_windows,
                len(result.windows),
                result.parameter_stability.stability_pct,
                result.robustness_score,
            )
        return result

    @staticmethod
    def _quality(result: RobustWalkForwardResult, profile: str) -> bool:
        diagnostics = QualityGateDiagnosticsServiceV0822.evaluate(result, profile)
        logger.info(
            "[QUALITY GATE] strategy=%s profile=%s result=%s",
            result.strategy,
            profile,
            "PASS" if diagnostics.passed else "FAIL",
        )
        for check in diagnostics.checks:
            logger.info(
                "[QUALITY GATE] strategy=%s check=%s actual=%.4f threshold=%.4f result=%s",
                result.strategy,
                check.key,
                check.actual,
                check.threshold,
                "PASS" if check.passed else "FAIL",
            )
        logger.info(
            "[QUALITY GATE] strategy=%s failed_checks=%s reason=%s",
            result.strategy,
            diagnostics.failed_checks,
            diagnostics.failure_reason or "none",
        )
        return diagnostics.passed

    @staticmethod
    def _legacy_strategy_result(result: RobustWalkForwardResult, profile: str) -> StrategyResult:
        quality = AnalysisServiceV08._quality(result, profile)
        return StrategyResult(
            strategy=result.strategy,
            parameters=dict(result.windows[-1].parameters) if result.windows else {},
            return_pct=round(result.mean_test_return_pct, 8),
            max_drawdown_pct=round(result.mean_test_drawdown_pct, 8),
            sharpe=round(result.mean_test_sharpe, 8),
            trades=sum(item.test_trades for item in result.windows),
            stability=round(result.robustness_score, 8),
            quality_gate=quality,
            score=round(result.robustness_score, 8),
            train_score=round(sum(item.train_score for item in result.windows) / len(result.windows), 8) if result.windows else 0.0,
            test_score=round(result.mean_test_return_pct, 8),
            wf_windows=len(result.windows),
            positive_return_windows=result.positive_return_windows,
            risk_ok_windows=result.risk_ok_windows,
            positive_sharpe_windows=result.positive_sharpe_windows,
            return_consistency=round(result.return_consistency_pct, 8),
            risk_consistency=round(result.risk_consistency_pct, 8),
            sharpe_consistency=round(result.sharpe_consistency_pct, 8),
        )

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
    ) -> AnalysisResult:
        if profile not in self.PROFILES:
            raise ValueError(f"Unsupported profile: {profile}")
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        minimum = self.PROFILES[profile]["train"] + self.PROFILES[profile]["test"]
        if len(ordered) < minimum:
            raise ValueError(f"Для v0.8-анализа требуется не менее {minimum} исторических свечей для профиля {profile}")
        regime_result = RegimeEngine.classify(ordered)
        robust_results = [self._robust(ordered, strategy, profile) for strategy in self.STRATEGIES]
        strategies = [self._legacy_strategy_result(item, profile) for item in robust_results]
        passed = [item for item in strategies if item.quality_gate]
        winner = max(passed, key=lambda item: item.score) if passed else None
        score_winner = max(strategies, key=lambda item: item.score) if strategies else None
        recommendation = winner.strategy if winner else None
        confidence = "Low" if not winner else "High" if winner.stability >= 80.0 else "Medium" if winner.stability >= 65.0 else "Low"
        self.last_diagnostics = AnalysisV08Diagnostics(
            regime_confidence=regime_result.confidence,
            regime=regime_result.regime,
            robustness_by_strategy={item.strategy: item.robustness_score for item in robust_results},
            quality_gate_by_strategy={item.strategy: QualityGateDiagnosticsServiceV0822.evaluate(item, profile) for item in robust_results},
        )
        logger.info(
            "[STRATEGY SELECTION] ticker=%s profile=%s quality_gate_winner=%s max_score_strategy=%s quality_gate_pass_count=%d total_strategies=%d",
            ticker,
            profile,
            winner.strategy if winner else None,
            score_winner.strategy if score_winner else None,
            len(passed),
            len(strategies),
        )
        explanation = (
            f"Рекомендована {winner.strategy}: v0.8 robustness {winner.score:.1f}, OOS return {winner.return_pct:.2f}%, Sharpe {winner.sharpe:.2f}, режим {regime_result.regime}, regime confidence {regime_result.confidence:.0f}%."
            if winner
            else f"Ни одна стратегия не прошла v0.8 Quality Gate; режим {regime_result.regime}, regime confidence {regime_result.confidence:.0f}%."
        )
        return AnalysisResult(
            instrument_uid=instrument_uid,
            ticker=ticker,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
            market_regime=regime_result.regime,
            recommendation=recommendation,
            confidence=confidence,
            score=winner.score if winner else 0.0,
            strategies=strategies,
            explanation=explanation,
            created_at=ordered[-1].timestamp.isoformat(),
            analysis_version=ANALYSIS_V08_VERSION,
        )


__all__ = ["ANALYSIS_V08_VERSION", "AnalysisV08Diagnostics", "AnalysisServiceV08"]
