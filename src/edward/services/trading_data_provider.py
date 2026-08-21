from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.balance_service import BalanceService
from edward.services.order_service import OrderRequest, OrderSide, OrderType
from edward.validation.trading_validator import ValidationContext

logger = logging.getLogger("edward.trading_validation")

_DEBUG_FILE = Path(__file__).resolve().parents[3] / "runtime" / "edward_debug.log"


def _debug_file(message: str) -> None:
    """Write critical trading diagnostics to a persistent local file."""
    try:
        _DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")
    except Exception:
        pass


class AdapterTradingDataProvider:
    def __init__(self, client: TInvestAdapterClient) -> None:
        self._client = client

    def get_validation_context(self, request: OrderRequest) -> ValidationContext:
        _debug_file(
            f"VALIDATION START account_id={request.account_id} instrument_uid={request.instrument_uid} "
            f"side={request.side.value} order_type={request.order_type.value} quantity={request.quantity}"
        )

        response = self._client.list_instruments(request.instrument_kind, trade_available_only=False)
        instruments = self._items(response, "instruments")
        instrument = next((item for item in instruments if self._uid(item) == request.instrument_uid), None)

        status = self._client.get_trading_status(request.instrument_uid)
        api_trade_available = bool(self._field(status, "api_trade_available_flag", False))
        limit_order_available = bool(self._field(status, "limit_order_available_flag", True))
        available = api_trade_available and (request.order_type != OrderType.LIMIT or limit_order_available)
        trading_diagnostic = (
            f"api_trade_available_flag={self._field(status, 'api_trade_available_flag', None)!r}; "
            f"limit_order_available_flag={self._field(status, 'limit_order_available_flag', None)!r}; "
            f"trading_status={self._field(status, 'trading_status', self._field(status, 'status', None))!r}"
        )

        current = self._items(self._client.get_last_prices([request.instrument_uid]), "last_prices")
        market_price = self._decimal(self._field(current[0], "price")) if current else None
        increment = self._decimal(self._field(instrument, "min_price_increment")) if instrument else None
        if increment is None and instrument is not None:
            increment = self._decimal(self._field(instrument, "min_price_increment_value"))

        # Sandbox buying funds must come directly from the real sandbox
        # GetSandboxPositions response. Do not route this through BalanceService
        # or another derived/normalized balance source.
        is_sandbox = str(self._client.health().get("environment", "")).lower() == "sandbox"
        if is_sandbox:
            positions = self._client.get_sandbox_positions(request.account_id)
        else:
            positions = self._client.get_positions(request.account_id)

        money = self._items(positions, "money")
        securities = BalanceService.get_security_positions(positions)
        available_money = Decimal("0")
        raw_money = money
        _debug_file(f"POSITIONS account_id={request.account_id} sandbox={is_sandbox} raw_positions={positions}")

        for item in money:
            if str(self._field(item, "currency", "")).upper() != "RUB":
                continue

            if is_sandbox and isinstance(item, dict) and ("units" in item or "nano" in item):
                available_raw = item
            else:
                available_raw = self._field(item, "available", None)
                if available_raw is None:
                    available_raw = self._field(item, "available_value", None)
                if available_raw is None and isinstance(item, dict) and ("units" in item or "nano" in item):
                    available_raw = item

            parsed = self._decimal(available_raw)
            _debug_file(
                f"MONEY account_id={request.account_id} item={item} "
                f"available_raw={available_raw} parsed={parsed}"
            )
            available_money += parsed or Decimal("0")

        print(
            f"[TRADING CASH] account_id={request.account_id} sandbox={is_sandbox} "
            f"available_money={available_money} raw_money={raw_money}"
        )
        _debug_file(
            f"CASH RESULT account_id={request.account_id} sandbox={is_sandbox} "
            f"available_money={available_money} raw_money={raw_money}"
        )

        available_position = None
        for item in securities:
            if self._uid(item) == request.instrument_uid:
                balance = self._decimal(self._field(item, "balance")) or Decimal("0")
                blocked = self._decimal(self._field(item, "blocked_lots", self._field(item, "blocked", 0))) or Decimal("0")
                available_position = max(0, int(balance - blocked))
                break

        unit_price = request.price or market_price
        estimated_total = unit_price * request.quantity if unit_price is not None else None
        estimated_commission = Decimal("0")

        # GetSandboxOrderPrice is defined for preliminary LIMIT-order pricing.
        # MARKET orders use the current market price for the local pre-flight estimate.
        if request.order_type == OrderType.LIMIT and unit_price is not None:
            try:
                whole = unit_price.quantize(Decimal("1"))
                quotation = {"units": str(whole), "nano": int((unit_price - whole) * Decimal("1000000000"))}
                price_response = self._client.get_order_price(
                    request.account_id,
                    request.instrument_uid,
                    quotation,
                    request.side.value,
                    request.quantity,
                )
                estimated_total = self._decimal(self._field(price_response, "total_order_amount")) or estimated_total
                estimated_commission = self._decimal(
                    self._field(price_response, "executed_commission", self._field(price_response, "deal_commission", "0"))
                ) or Decimal("0")
            except Exception as exc:
                _debug_file(f"ORDER PRICE ERROR account_id={request.account_id} error={type(exc).__name__}: {exc}")

        print(
            f"[TRADING FUNDS] side={request.side.value} quantity={request.quantity} "
            f"unit_price={unit_price} estimated_total={estimated_total} "
            f"commission={estimated_commission} available_money={available_money} "
            f"available_position={available_position} trading_allowed={available}"
        )
        _debug_file(
            f"FUNDS account_id={request.account_id} side={request.side.value} quantity={request.quantity} "
            f"unit_price={unit_price} estimated_total={estimated_total} commission={estimated_commission} "
            f"available_money={available_money} available_position={available_position} trading_allowed={available}"
        )

        return ValidationContext(
            instrument_available=instrument is not None,
            trading_allowed=available,
            price_increment=increment,
            market_price=market_price,
            available_money=available_money if request.side == OrderSide.BUY else None,
            available_position=available_position if request.side == OrderSide.SELL else None,
            estimated_total=estimated_total,
            estimated_commission=estimated_commission,
            trading_diagnostic=trading_diagnostic,
        )

    @staticmethod
    def _items(response: Any, name: str) -> list[Any]:
        if isinstance(response, list):
            return response
        value = response.get(name, []) if isinstance(response, dict) else getattr(response, name, [])
        return list(value or [])

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)

    @classmethod
    def _uid(cls, value: Any) -> str:
        return str(cls._field(value, "uid", cls._field(value, "instrument_uid", "")))

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, dict) and ("units" in value or "nano" in value):
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        try:
            return Decimal(str(value))
        except Exception:
            return None
