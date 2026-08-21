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
    def _is_cash(cls, position: Any) -> bool:
        ticker = str(cls._field(position, "ticker", "") or "").upper()
        figi = str(cls._field(position, "figi", "") or "").upper()
        uid = str(cls._field(position, "instrument_uid", "") or "").upper()
        currency = str(cls._field(position, "currency", "") or "").upper()
        instrument_type = str(
            cls._field(position, "instrument_type", cls._field(position, "instrument_kind", "")) or ""
        ).upper()
        return (
            ticker == "RUB000UTSTOM"
            or figi == "RUB000UTSTOM"
            or ticker.startswith("RUB")
            or uid == "A92E2E25-A698-45CC-A781-167CF465257C"
            or (currency == "RUB" and "CURRENCY" in instrument_type)
        )

    @classmethod
    def build_summary(cls, positions_response: Any, portfolio_response: Any | None = None) -> FinancialSummary:
        money = cls.get_money_positions(positions_response)
        securities_response = cls.get_security_positions(positions_response)
        portfolio_positions = cls._field(portfolio_response, "positions", []) if portfolio_response is not None else []
        portfolio_positions = list(portfolio_positions or [])

        currency = "RUB"
        available = Decimal("0")
        blocked = Decimal("0")

        for position in money:
            position_currency = cls._field(position, "currency")
            if position_currency:
                currency = str(position_currency).upper()
            available += cls._decimal(cls._money_field(position, "available", "available_value"))
            blocked += cls._decimal(cls._money_field(position, "blocked", "blocked_value"))

        cash_value = available + blocked
        securities_value = cls._security_value_from_positions(cls, securities_response, portfolio_positions)
        api_portfolio_value = cls._portfolio_value(portfolio_response)

        # T-Invest's total_amount_portfolio is the authoritative total. In the
        # sandbox response, the positions array can contain RUB/CASH as well;
        # that row must never be counted as a security. If the API total is
        # absent/zero, calculate from cash plus non-cash positions only.
        portfolio_value = api_portfolio_value
        if portfolio_value is None or portfolio_value == Decimal("0"):
            portfolio_value = cash_value + securities_value

        print(
            f"[BALANCE SUMMARY] cash={cash_value} securities={securities_value} "
            f"api_total={api_portfolio_value} portfolio={portfolio_value}",
            flush=True,
        )

        return FinancialSummary(
            currency=currency,
            available=available,
            blocked=blocked,
            cash=cash_value,
            securities=securities_value,
            portfolio_value=portfolio_value,
        )

    @classmethod
    def _security_value_from_positions(
        cls,
        _unused: Any,
        securities_response: list[Any],
        portfolio_positions: list[Any],
    ) -> Decimal:
        total = Decimal("0")

        # Prefer explicit aggregated non-cash positions from GetPositions.
        for position in securities_response:
            if cls._is_cash(position):
                continue
            explicit = cls._field(position, "current_value", cls._field(position, "value", None))
            if explicit is not None:
                total += cls._decimal(explicit)
                continue
            quantity = cls._decimal(cls._field(position, "balance", cls._field(position, "quantity", 0)))
            price = cls._decimal(cls._field(position, "current_price", 0))
            total += quantity * price

        # Some sandbox responses expose only PortfolioPosition[] in the
        # portfolio response. Use those rows as a fallback, excluding RUB/CASH.
        if total == Decimal("0"):
            for position in portfolio_positions:
                if cls._is_cash(position):
                    continue
                explicit = cls._field(position, "current_value", cls._field(position, "value", None))
                if explicit is not None:
                    total += cls._decimal(explicit)
                    continue
                quantity = cls._decimal(cls._field(position, "quantity", cls._field(position, "balance", 0)))
                price = cls._decimal(cls._field(position, "current_price", 0))
                total += quantity * price

        return total

    @classmethod
    def _portfolio_value(cls, response: Any | None) -> Decimal | None:
        if response is None:
            return None
        for name in ("total_amount_portfolio", "total_amount_currencies"):
            value = cls._field(response, name, None)
            if value is not None:
                return cls._decimal(value)
        return None
