from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from edward.services.budget_planning_service import BudgetPlan


BUY = "BUY"
HOLD = "HOLD"
ADD = "ADD"
REDUCE = "REDUCE"
SELL = "SELL"
REPLACE = "REPLACE"


@dataclass(frozen=True, slots=True)
class ReallocationPolicy:
    """Rules for changing portfolio composition without embedding a cash budget."""

    replacement_score_delta: float = 5.0
    max_replacement_risk_increase: float = 0.0

    def __post_init__(self) -> None:
        if self.replacement_score_delta < 0:
            raise ValueError("replacement_score_delta must be >= 0")
        if self.max_replacement_risk_increase < 0:
            raise ValueError("max_replacement_risk_increase must be >= 0")


@dataclass(frozen=True, slots=True)
class AllocationAction:
    action: str
    ticker: str
    instrument_uid: str
    score: float
    risk_score: float
    target_value: Decimal
    source_ticker: str | None = None
    source_instrument_uid: str | None = None
    reason: str = ""


class PortfolioReallocationService:
    """Turn market and portfolio analysis into a slot-aware allocation plan.

    The service never invents an absolute budget. Position value comes from the
    live BudgetPlan, while slot count comes from the same plan. It also never
    allocates more new cash than BudgetPlan.investable_cash. Execution remains
    outside this service.
    """

    def __init__(self, policy: ReallocationPolicy | None = None) -> None:
        self.policy = policy or ReallocationPolicy()

    def plan(
        self,
        *,
        budget: BudgetPlan,
        market_opportunities: Iterable[object],
        portfolio_opportunities: Iterable[object],
    ) -> tuple[AllocationAction, ...]:
        market = list(market_opportunities)
        portfolio = list(portfolio_opportunities)
        actions: list[AllocationAction] = []

        held: list[object] = []
        for item in portfolio:
            decision = _decision(item)
            if decision == SELL:
                actions.append(self._action(item, SELL, _target_value(item, budget.target_position_value), "Portfolio Decision требует полного выхода."))
            else:
                held.append(item)
                if decision in {HOLD, ADD, REDUCE}:
                    actions.append(self._action(item, decision, _target_value(item, budget.target_position_value), "Текущее решение Portfolio/Decision Engine."))

        occupied_slots = len(held)
        free_slots = max(0, int(budget.slots) - occupied_slots)
        remaining_cash = max(Decimal("0"), Decimal(str(budget.investable_cash)))
        target_value = max(Decimal("0"), Decimal(str(budget.target_position_value)))
        eligible = sorted(
            (item for item in market if _decision(item) == BUY),
            key=lambda item: (_score(item), -_risk(item)),
            reverse=True,
        )
        selected_uids: set[str] = set()

        for candidate in eligible:
            if free_slots <= 0:
                break
            uid = _uid(candidate)
            if not uid or uid in selected_uids:
                continue
            value = min(target_value, remaining_cash)
            if value <= 0:
                break
            actions.append(self._action(candidate, BUY, value, "Свободный слот портфеля и доступный cash."))
            selected_uids.add(uid)
            remaining_cash -= value
            free_slots -= 1

        if free_slots == 0 and eligible:
            replaceable = sorted(
                (item for item in held if _uid(item) and _decision(item) not in {SELL}),
                key=lambda item: (_score(item), _risk(item)),
            )
            replaced_sources: set[str] = set()
            for candidate in eligible:
                if _uid(candidate) in selected_uids:
                    continue
                source = next(
                    (
                        item
                        for item in replaceable
                        if _uid(item) not in replaced_sources
                        and _score(candidate) >= _score(item) + self.policy.replacement_score_delta
                        and _risk(candidate) <= _risk(item) + self.policy.max_replacement_risk_increase
                    ),
                    None,
                )
                if source is None:
                    continue
                source_uid = _uid(source)
                actions.append(
                    self._action(
                        candidate,
                        REPLACE,
                        target_value,
                        f"Замена {_ticker(source)}: score {_score(candidate):.2f} против {_score(source):.2f}, риск {_risk(candidate):.2f} против {_risk(source):.2f}.",
                        source_ticker=_ticker(source),
                        source_uid=source_uid,
                    )
                )
                selected_uids.add(_uid(candidate))
                replaced_sources.add(source_uid)

        return tuple(actions)

    @staticmethod
    def _action(item: object, action: str, value: Decimal, reason: str, *, source_ticker: str | None = None, source_uid: str | None = None) -> AllocationAction:
        return AllocationAction(
            action=action,
            ticker=_ticker(item),
            instrument_uid=_uid(item),
            score=_score(item),
            risk_score=_risk(item),
            target_value=value,
            source_ticker=source_ticker,
            source_instrument_uid=source_uid,
            reason=reason,
        )


def _field(item: object, name: str, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _ticker(item: object) -> str:
    return str(_field(item, "ticker", ""))


def _uid(item: object) -> str:
    return str(_field(item, "instrument_uid", _field(item, "uid", "")))


def _decision(item: object) -> str:
    value = _field(item, "decision", "")
    return getattr(value, "value", str(value or "")).upper()


def _score(item: object) -> float:
    try:
        return float(_field(item, "opportunity_score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _risk(item: object) -> float:
    try:
        return float(_field(item, "risk_score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _target_value(item: object, fallback: Decimal) -> Decimal:
    try:
        value = Decimal(str(_field(item, "recommended_value", 0.0) or 0.0))
        return value if value > 0 else fallback
    except Exception:
        return fallback
