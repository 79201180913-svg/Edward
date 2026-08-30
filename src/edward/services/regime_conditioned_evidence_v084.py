from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult

logger = logging.getLogger(__name__)
REGIME_CONDITIONED_EVIDENCE_V084_VERSION = "0.8.4"


@dataclass(frozen=True, slots=True)
class RegimeConditionedEvidence:
    strategy: str
    current_regime: str
    current_regime_confidence: float
    matching_windows: int
    total_windows: int
    coverage_pct: float
    mean_oos_return_pct: float
    mean_oos_excess_return_pct: float
    positive_return_windows: int
    positive_return_pct: float
    mean_oos_drawdown_pct: float
    mean_oos_sharpe: float
    evidence_score: float


class RegimeConditionedEvidenceServiceV084:
    """Evaluate historical OOS windows conditioned on the current market regime.

    Historical OOS data is used only after parameter selection. It never participates
    in Train parameter selection, transfer selection, or production parameter choice.
    """

    @staticmethod
    def _window_regime(candles: Sequence[Candle], start, end):
        window = [c for c in candles if start <= c.timestamp <= end]
        # A short OOS slice is not enough for the classifier; use the information
        # available through the end of the window without changing Train selection.
        if len(window) < 51:
            prefix = [c for c in candles if c.timestamp <= end]
            return RegimeEngine.classify(prefix)
        return RegimeEngine.classify(window)

    @classmethod
    def evaluate(
        cls,
        result: RobustWalkForwardResult,
        candles: Sequence[Candle],
        current_regime: str,
        current_confidence: float,
        *,
        ticker: str | None = None,
    ) -> RegimeConditionedEvidence:
        matching = []
        for window in result.windows:
            regime = cls._window_regime(candles, window.test_start, window.test_end)
            matches = regime.regime == current_regime
            logger.warning(
                "[V084 REGIME OOS WINDOW] ticker=%s strategy=%s window=%d test_start=%s test_end=%s oos_regime=%s current_regime=%s match=%s confidence=%.2f return=%.4f excess=%.4f dd=%.4f sharpe=%.4f",
                ticker, result.strategy, window.index, window.test_start, window.test_end,
                regime.regime, current_regime, matches, regime.confidence,
                window.test_net_return_pct, window.test_excess_return_pct,
                window.test_max_drawdown_pct, window.test_sharpe,
            )
            if matches:
                matching.append(window)

        total = len(result.windows)
        count = len(matching)
        if not matching:
            evidence = RegimeConditionedEvidence(
                result.strategy, current_regime, current_confidence, 0, total,
                0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0.0,
            )
        else:
            positive = sum(w.test_net_return_pct > 0 for w in matching)
            positive_pct = positive / count * 100.0
            coverage = count / total * 100.0 if total else 0.0
            # Evidence score is descriptive, not a QG bypass: positive consistency,
            # economic excess, and risk-adjusted behavior are combined conservatively.
            consistency = positive_pct
            economic = 50.0 + min(50.0, max(-50.0, mean(w.test_excess_return_pct for w in matching) * 10.0))
            sharpe = max(0.0, min(100.0, 50.0 + mean(w.test_sharpe for w in matching) * 25.0))
            evidence_score = round(0.45 * consistency + 0.35 * economic + 0.20 * sharpe, 4)
            evidence = RegimeConditionedEvidence(
                result.strategy, current_regime, current_confidence, count, total,
                round(coverage, 4),
                round(mean(w.test_net_return_pct for w in matching), 8),
                round(mean(w.test_excess_return_pct for w in matching), 8),
                positive, round(positive_pct, 4),
                round(mean(w.test_max_drawdown_pct for w in matching), 8),
                round(mean(w.test_sharpe for w in matching), 8), evidence_score,
            )
        logger.warning(
            "[V084 REGIME EVIDENCE RESULT] ticker=%s strategy=%s current_regime=%s confidence=%.2f matching=%d/%d coverage=%.2f positive_pct=%.2f mean_return=%.4f mean_excess=%.4f mean_dd=%.4f mean_sharpe=%.4f evidence_score=%.4f",
            ticker, result.strategy, current_regime, current_confidence, evidence.matching_windows,
            evidence.total_windows, evidence.coverage_pct, evidence.positive_return_pct,
            evidence.mean_oos_return_pct, evidence.mean_oos_excess_return_pct,
            evidence.mean_oos_drawdown_pct, evidence.mean_oos_sharpe, evidence.evidence_score,
        )
        return evidence


__all__ = ["REGIME_CONDITIONED_EVIDENCE_V084_VERSION", "RegimeConditionedEvidence", "RegimeConditionedEvidenceServiceV084"]
