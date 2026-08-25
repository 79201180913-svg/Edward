from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Protocol

from edward.domain.execution import ExecutionRequest, ExecutionResult, ExecutionStatus


class TInvestExecutionClient(Protocol):
    """Minimal client boundary required by the T-Invest execution adapter."""

    def create_order(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    def order_state(self, account_id: str, order_id: str) -> Mapping[str, Any]:
        ...

    def cancel_order(self, account_id: str, order_id: str) -> Mapping[str, Any]:
        ...


_STATUS_MAP = {
    "EXECUTION_REPORT_STATUS_NEW": ExecutionStatus.SUBMITTED,
    "EXECUTION_REPORT_STATUS_PARTIALLYFILL": ExecutionStatus.PARTIALLY_FILLED,
    "EXECUTION_REPORT_STATUS_PARTIALLY_FILLED": ExecutionStatus.PARTIALLY_FILLED,
    "EXECUTION_REPORT_STATUS_FILL": ExecutionStatus.FILLED,
    "EXECUTION_REPORT_STATUS_CANCELLED": ExecutionStatus.CANCELLED,
    "EXECUTION_REPORT_STATUS_REJECTED": ExecutionStatus.REJECTED,
    "NEW": ExecutionStatus.SUBMITTED,
    "PARTIALLY_FILLED": ExecutionStatus.PARTIALLY_FILLED,
    "FILLED": ExecutionStatus.FILLED,
    "CANCELLED": ExecutionStatus.CANCELLED,
    "REJECTED": ExecutionStatus.REJECTED,
}


def _value(payload: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return default


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Mapping):
        units = value.get("units", 0)
        nano = value.get("nano", 0)
        try:
            return Decimal(str(units)) + Decimal(str(nano)) / Decimal("1000000000")
        except Exception:
            return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _status(value: Any) -> ExecutionStatus:
    raw = str(getattr(value, "value", value) or "").upper()
    if raw in _STATUS_MAP:
        return _STATUS_MAP[raw]
    if "PARTIALLY" in raw:
        return ExecutionStatus.PARTIALLY_FILLED
    if "FILL" in raw and "PARTIALLY" not in raw:
        return ExecutionStatus.FILLED
    if "CANCEL" in raw:
        return ExecutionStatus.CANCELLED
    if "REJECT" in raw:
        return ExecutionStatus.REJECTED
    if "NEW" in raw or "ACTIVE" in raw:
        return ExecutionStatus.SUBMITTED
    return ExecutionStatus.FAILED


class TInvestExecutionAdapter:
    """Maps Edward execution contracts to the existing T-Invest adapter boundary."""

    def __init__(self, client: TInvestExecutionClient) -> None:
        self.client = client
        self._orders: dict[str, tuple[str, str]] = {}

    def submit(self, request: ExecutionRequest) -> str:
        payload: dict[str, Any] = {
            "request_id": request.execution_id,
            "account_id": request.account_id,
            "instrument_uid": request.instrument_uid,
            "direction": request.side,
            "order_type": request.order_type,
            "quantity": int(request.quantity),
        }
        if request.entry_price is not None:
            payload["price"] = request.entry_price
        result = self.client.create_order(payload)
        order_id = _value(result, "order_id", "orderId", "id")
        if not order_id:
            raise RuntimeError("T-Invest did not return broker order id")
        broker_order_id = str(order_id)
        self._orders[broker_order_id] = (request.account_id, request.execution_id)
        return broker_order_id

    def get_status(self, broker_order_id: str) -> ExecutionResult:
        account_id, execution_id = self._orders.get(broker_order_id, ("", ""))
        if not account_id:
            raise KeyError(f"Unknown broker order id: {broker_order_id}")
        raw = self.client.order_state(account_id, broker_order_id)
        status = _status(_value(raw, "execution_report_status", "status", "order_status", "state"))
        filled = _decimal(_value(raw, "lots_executed", "filled_quantity", "filledQuantity", "quantity_executed"))
        average_price = _value(raw, "executed_order_price", "average_fill_price", "averageFillPrice")
        commission = _decimal(_value(raw, "executed_commission", "commission"))
        error_code = _value(raw, "error_code", "errorCode")
        error_message = _value(raw, "error_message", "errorMessage", "message")
        return ExecutionResult(
            execution_id=execution_id,
            status=status,
            broker_order_id=broker_order_id,
            filled_quantity=filled,
            average_fill_price=_decimal(average_price) if average_price is not None else None,
            commission=commission,
            error_code=str(error_code) if error_code else None,
            error_message=str(error_message) if error_message else None,
        )

    def cancel(self, broker_order_id: str) -> None:
        account_id, _execution_id = self._orders.get(broker_order_id, ("", ""))
        if not account_id:
            raise KeyError(f"Unknown broker order id: {broker_order_id}")
        self.client.cancel_order(account_id, broker_order_id)
