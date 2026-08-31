from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from edward.domain import TradingPathCandidate
from edward.services.economic_validation_v088 import EconomicValidationV088, TradingCostModelV088
from edward.services.event_backtest_v088 import EventBacktestV088
from edward.services.trading_path_evidence_v088 import TradingPathEvidenceServiceV088
from edward.services.trading_path_statistical_validation_v088 import TradingPathStatisticalValidationV088
from edward.services.trading_rule_builder_v088 import TradingRuleBuilderV088


@dataclass(frozen=True, slots=True)
class TradingPathPipelineResultV088:
    candidate: TradingPathCandidate
    gross_return_pct: float
    net_return_pct: float
    trades: int
    statistical_evidence: object
    temporal_evidence: object | None = None


class TradingPathValidationPipelineV088:
    """Compose v0.8.8 validation stages without changing v0.8.7 decisions."""

    @staticmethod
    def run(
        candidate: TradingPathCandidate,
        candles: Sequence[object],
        observations: Sequence[object],
        cost_model: TradingCostModelV088 | None = None,
    ) -> TradingPathPipelineResultV088:
        rule = TradingRuleBuilderV088.build(candidate)
        backtest = EventBacktestV088.run(candles, observations, rule)
        costs = cost_model or TradingCostModelV088()
        returns = tuple(float(trade.return_pct) for trade in backtest.trades)
        economic = EconomicValidationV088.validate(returns, costs)
        temporal = TradingPathEvidenceServiceV088.temporal_blocks(returns)
        statistics = TradingPathStatisticalValidationV088.evaluate(
            returns, tuple((value,) for value in temporal)
        )
        evidence = TradingPathEvidenceServiceV088.build(returns)
        return TradingPathPipelineResultV088(
            candidate=candidate,
            gross_return_pct=economic.gross_return_pct,
            net_return_pct=economic.net_return_pct,
            trades=economic.trades,
            statistical_evidence=statistics,
            temporal_evidence=evidence,
        )


__all__ = ["TradingPathPipelineResultV088", "TradingPathValidationPipelineV088"]
