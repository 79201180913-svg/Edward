from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult


QUALITY_GATE_DIAGNOSTICS_V0822_VERSION = "0.8.2.2"


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

    The boolean criteria intentionally mirror AnalysisServiceV08._quality().
    This release only exposes why a strategy passed or failed; it does not
    change any existing threshold or decision rule.
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
        checks = (
            QualityGateCheck("wf_windows", "WF окон", float(len(result.windows)), 5.0, len(result.windows) >= 5),
            QualityGateCheck("mean_test_return", "Средняя OOS доходность", result.mean_test_return_pct, 0.0, result.mean_test_return_pct > 0.0),
            QualityGateCheck("mean_test_drawdown", "Средняя OOS просадка", result.mean_test_drawdown_pct, cfg["max_drawdown_pct"], result.mean_test_drawdown_pct <= cfg["max_drawdown_pct"]),
            QualityGateCheck("mean_test_sharpe", "Средний OOS Sharpe", result.mean_test_sharpe, 0.0, result.mean_test_sharpe > 0.0),
            QualityGateCheck("return_consistency", "Положительные OOS окна", result.return_consistency_pct, 60.0, result.return_consistency_pct >= 60.0),
            QualityGateCheck("robustness_score", "Robustness Score", result.robustness_score, cfg["min_stability_pct"], result.robustness_score >= cfg["min_stability_pct"]),
        )
        failed = tuple(check.label for check in checks if not check.passed)
        return QualityGateDiagnostics(
            profile=profile,
            robustness_threshold=cfg["min_stability_pct"],
            checks=checks,
            failed_checks=failed,
            passed=not failed,
        )


__all__ = [
    "QUALITY_GATE_DIAGNOSTICS_V0822_VERSION",
    "QualityGateCheck",
    "QualityGateDiagnostics",
    "QualityGateDiagnosticsServiceV0822",
]
