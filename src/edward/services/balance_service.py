from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from edward.api.portfolio import PortfolioApi


@dataclass(frozen=True, slots=True)
class FinancialSummary:
    currency: str
    available: Decimal
    blocked: Decimal
    cash: Decimal
    securities: Decimal
    portfolio_value: Decimal


class BalanceService:
    def __init__(self, api: PortfolioApi | None = None) -> None:
        self._api = api

    def get_positions(self, account_id: str) -> Any:
        if self._api is None:
            raise RuntimeError("Portfolio API is not configured")
        return self._api.get_positions(account_id)

    def get_portfolio(self, account_id: str) -> Any:
        if self._api is None:
            raise RuntimeError("Portfolio API is not configured")
        return self._api.get_portfolio(account_id)

    @staticmethod
    def get_money_positions(positions_response: Any) -> list[Any]:
        if isinstance(positions_response, dict):
            return list(positions_response.get("money", []))
        return list(getattr(positions_response, "money", []))

    @staticmethod
    def get_security_positions(positions_response: Any) -> list[Any]:
        if isinstance(positions_response, dict):
            return list(positions_response.get("securities", []))
        return list(getattr(positions_response, "securities", []))

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, dict):
            if "units" in value or "nano" in value:
                return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
            if "value" in value:
                return BalanceService._decimal(value["value"])
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    @classmethod
    def _field(cls, value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    @classmethod
    def _money_field(cls, position: Any, *names: str) -> Any:
        for name in names:
            value = cls._field(position, name, None)
            if value is not None:
                return value
        if cls._field(position, "units", None) is not None or cls._field(position, "nano", None) is not None:
            return position
        return None

    @classmethod
    def build_summary(cls, positions_response: Any, portfolio_response: Any | None = None) -> FinancialSummary:
        money = cls.get_money_positions(positions_response)
        currency = "RUB"
        available = Decimal("0")
        blocked = Decimal("0")

        for position in money:
            position_currency = cls._field(position, "currency")
            if position_currency:
                currency = str(position_currency).upper()
            available += cls._decimal(cls._money_field(position, "available", "available_value"))
            blocked += cls._decimal(cls._money_field(position, "blocked", "blocked_value"))

        portfolio_value = cls._portfolio_value(portfolio_response)
        cash_value = available + blocked
        securities_value = cls._portfolio_securities_value(portfolio_response)

        if portfolio_value is None or (portfolio_value == Decimal("0") and (cash_value or securities_value)):
            # PortfolioResponse already provides values calculated by T-Invest.
            # Prefer these class totals over multiplying position quantities by
            # price, because position quantity is expressed in pieces and the
            # price is for one security; lot conversion would otherwise be
            # required and differs by instrument type.
            portfolio_value = cash_value + securities_value

        return FinancialSummary(
            currency=currency,
            available=available,
            blocked=blocked,
            cash=cash_value,
            securities=securities_value,
            portfolio_value=portfolio_value,
        )

    @classmethod
    def _portfolio_value(cls, response: Any | None) -> Decimal | None:
        if response is None:
            return None
        value = cls._field(response, "total_amount_portfolio")
        if value is not None:
            return cls._decimal(value)
        return None

    @classmethod
    def _portfolio_securities_value(cls, response: Any | None) -> Decimal:
        if response is None:
            return Decimal("0")
        total = Decimal("0")
        for name in (
            "total_amount_shares",
            "total_amount_bonds",
            "total_amount_etf",
            "total_amount_futures",
            "total_amount_options",
            "total_amount_sp",
            "total_amount_dfa",
        ):
            total += cls._decimal(cls._field(response, name))
        return total
