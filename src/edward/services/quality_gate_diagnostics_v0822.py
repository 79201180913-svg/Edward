from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping

from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult


QUALITY_GATE_DIAGNOSTICS_V0822_VERSION = "0.8.2.2"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QualityGateCheck:
    key: str
    label: str
    actual: float
    threshold: float
    passed: bool


@dataclass(frozen=True, slots=True)
class QualityGateDiagnostics:
    """Explain the existing v0.8 Quality Gate without changing its rules."""

    profile: str
    robustness_threshold: float
    checks: tuple[QualityGateCheck, ...]
    failed_checks: tuple[str, ...]
    passed: bool

    @property
    def failure_reason(self) -> str:
        if self.passed:
            return "Все критерии Quality Gate выполнены"
        return "; ".join(self.failed_checks)


class QualityGateDiagnosticsServiceV0822:
    """Single source of truth for v0.8 Quality Gate diagnostics.

    v0.8.3 adds diagnostic logging only. Existing thresholds and decision
    rules are intentionally unchanged.
    """

    PROFILES: Mapping[str, Mapping[str, float]] = {
        "long_term": {"max_drawdown_pct": 30.0, "min_stability_pct": 60.0},
        "medium_term": {"max_drawdown_pct": 25.0, "min_stability_pct": 60.0},
        "speculative": {"max_drawdown_pct": 35.0, "min_stability_pct": 55.0},
    }

    @classmethod
    def evaluate(cls, result: RobustWalkForwardResult, profile: str) -> QualityGateDiagnostics:
        if profile not in cls.PROFILES:
            raise ValueError(f"Unsupported profile: {profile}")
        cfg = cls.PROFILES[profile]

        logger.info(
            "[V083 QG START] strategy=%s profile=%s windows=%d train_test_windows=%d",
            result.strategy,
            profile,
            len(result.windows),
            len(result.windows),
        )
        logger.info(
            "[V083 QG WF SUMMARY] strategy=%s mean_oos_return=%.4f median_oos_return=%.4f "
            "worst_oos_return=%.4f best_oos_return=%.4f mean_oos_dd=%.4f mean_oos_sharpe=%.4f "
            "return_consistency=%.2f risk_consistency=%.2f sharpe_consistency=%.2f robustness=%.2f",
            result.strategy,
            result.mean_test_return_pct,
            result.median_test_return_pct,
            result.worst_test_return_pct,
            result.best_test_return_pct,
            result.mean_test_drawdown_pct,
            result.mean_test_sharpe,
            result.return_consistency_pct,
            result.risk_consistency_pct,
            result.sharpe_consistency_pct,
            result.robustness_score,
        )
        logger.info(
            "[V083 QG PARAMETER STABILITY] strategy=%s windows=%d dominant_windows=%d "
            "stability=%.2f selected_parameters=%s",
            result.strategy,
            result.parameter_stability.windows,
            result.parameter_stability.dominant_windows,
            result.parameter_stability.stability_pct,
            result.parameter_stability.selected_parameters,
        )

        for window in result.windows:
            logger.info(
                "[V083 WF WINDOW] strategy=%s window=%d train=%s..%s test=%s..%s "
                "params=%s train_score=%.4f oos_return=%.4f benchmark=%.4f excess=%.4f "
                "dd=%.4f sharpe=%.4f sortino=%.4f trades=%d",
                result.strategy,
                window.index,
                window.train_start,
                window.train_end,
                window.test_start,
                window.test_end,
                window.parameters,
                window.train_score,
                window.test_net_return_pct,
                window.test_benchmark_return_pct,
                window.test_excess_return_pct,
                window.test_max_drawdown_pct,
                window.test_sharpe,
                window.test_sortino,
                window.test_trades,
            )

        checks = (
            QualityGateCheck("wf_windows", "WF окон", float(len(result.windows)), 5.0, len(result.windows) >= 5),
            QualityGateCheck("mean_test_return", "Средняя OOS доходность", result.mean_test_return_pct, 0.0, result.mean_test_return_pct > 0.0),
            QualityGateCheck("mean_test_drawdown", "Средняя OOS просадка", result.mean_test_drawdown_pct, cfg["max_drawdown_pct"], result.mean_test_drawdown_pct <= cfg["max_drawdown_pct"]),
            QualityGateCheck("mean_test_sharpe", "Средний OOS Sharpe", result.mean_test_sharpe, 0.0, result.mean_test_sharpe > 0.0),
            QualityGateCheck("return_consistency", "Положительные OOS окна", result.return_consistency_pct, 60.0, result.return_consistency_pct >= 60.0),
            QualityGateCheck("robustness_score", "Robustness Score", result.robustness_score, cfg["min_stability_pct"], result.robustness_score >= cfg["min_stability_pct"]),
        )
        failed = tuple(check.label for check in checks if not check.passed)

        for check in checks:
            logger.info(
                "[V083 QG CHECK] strategy=%s key=%s actual=%.6f threshold=%.6f passed=%s",
                result.strategy,
                check.key,
                check.actual,
                check.threshold,
                check.passed,
            )

        diagnostics = QualityGateDiagnostics(
            profile=profile,
            robustness_threshold=cfg["min_stability_pct"],
            checks=checks,
            failed_checks=failed,
            passed=not failed,
        )
        logger.info(
            "[V083 QG RESULT] strategy=%s profile=%s passed=%s failed_checks=%s reason=%s",
            result.strategy,
            profile,
            diagnostics.passed,
            diagnostics.failed_checks,
            diagnostics.failure_reason,
        )
        return diagnostics


__all__ = [
    "QUALITY_GATE_DIAGNOSTICS_V0822_VERSION",
    "QualityGateCheck",
    "QualityGateDiagnostics",
    "QualityGateDiagnosticsServiceV0822",
]
