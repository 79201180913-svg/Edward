from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from edward.services.balance_service import FinancialSummary


MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class BudgetPlanningPolicy:
    """Strategy parameters for autonomous capital planning.

    The policy never contains an absolute budget. The budget is always derived
    from the live account state supplied to ``BudgetPlanningService``.
    """

    slots: int
    reserve_pct: Decimal = Decimal("0")
    min_position_value: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.slots < 1:
            raise ValueError("slots must be >= 1")
        if not Decimal("0") <= self.reserve_pct <= Decimal("100"):
            raise ValueError("reserve_pct must be between 0 and 100")
        if self.min_position_value < 0:
            raise ValueError("min_position_value must be >= 0")


@dataclass(frozen=True, slots=True)
class BudgetPlan:
    account_capital: Decimal
    cash: Decimal
    blocked_cash: Decimal
    invested: Decimal
    reserve: Decimal
    planning_budget: Decimal
    investable_cash: Decimal
    slots: int
    target_position_value: Decimal
    currency: str = "RUB"


class BudgetPlanningService:
    """Derive the autonomous investment budget from the live account state."""

    def build(self, financial: FinancialSummary, policy: BudgetPlanningPolicy) -> BudgetPlan:
        capital = self._money(financial.portfolio_value)
        cash = self._money(financial.cash)
        blocked = self._money(financial.blocked)
        invested = max(Decimal("0"), self._money(financial.securities))

        reserve = self._money(capital * policy.reserve_pct / Decimal("100"))
        planning_budget = max(Decimal("0"), capital - reserve)

        # New purchases can only use actual available cash. Securities are
        # already part of the portfolio and therefore remain in the target
        # portfolio budget rather than becoming spendable cash.
        investable_cash = max(Decimal("0"), cash - reserve)

        target = (planning_budget / Decimal(policy.slots)).quantize(
            MONEY_QUANTUM, rounding=ROUND_DOWN
        )
        if target < policy.min_position_value:
            target = Decimal("0")

        return BudgetPlan(
            account_capital=capital,
            cash=cash,
            blocked_cash=blocked,
            invested=invested,
            reserve=reserve,
            planning_budget=planning_budget,
            investable_cash=investable_cash,
            slots=policy.slots,
            target_position_value=target,
            currency=str(financial.currency or "RUB").upper(),
        )

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return Decimal(str(value or 0)).quantize(MONEY_QUANTUM)
