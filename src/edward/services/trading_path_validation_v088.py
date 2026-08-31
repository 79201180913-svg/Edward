from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.economic_validation_v088 import (
    EconomicValidationResultV088,
    EconomicValidationV088,
    TradingCostModelV088,
)
from edward.services.event_backtest_v088 import EventBacktestResultV088, EventBacktestV088
from edward.services.event_observation_v086 import EventObservationV086
from edward.services.trading_rule_builder_v088 import TradingRuleBuilderV088, TradingRuleV088
from edward.domain import TradingPathCandidate


@dataclass(frozen=True, slots=True)
class TradingPathValidationResultV088:
    candidate: TradingPathCandidate
    rule: TradingRuleV088
    backtest: EventBacktestResultV088
    economics: EconomicValidationResultV088


class TradingPathValidationServiceV088:
    """Connect v0.8.8 research candidates to executable validation.

    This service is deliberately validation-only. It does not promote status,
    alter the v0.8.7 analysis result, bypass WF, or invoke production execution.
    """

    @classmethod
    def validate(
        cls,
        candidate: TradingPathCandidate,
        candles: Sequence[Candle],
        observations: Sequence[EventObservationV086],
        cost_model: TradingCostModelV088,
    ) -> TradingPathValidationResultV088:
        rule = TradingRuleBuilderV088.build(candidate)
        backtest = EventBacktestV088.run(candles, observations, rule)
        economics = EconomicValidationV088.validate(
            (trade.return_pct for trade in backtest.trades),
            cost_model,
        )
        return TradingPathValidationResultV088(
            candidate=candidate,
            rule=rule,
            backtest=backtest,
            economics=economics,
        )


__all__ = ["TradingPathValidationResultV088", "TradingPathValidationServiceV088"]
