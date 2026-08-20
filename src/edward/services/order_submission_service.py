from __future__ import annotations

from typing import Any, Protocol

from edward.services.order_service import OrderRequest
from edward.validation.trading_validator import TradingValidator


class ConfirmationProvider(Protocol):
    def confirm(self, request: OrderRequest, validation: Any) -> bool: ...


class OrderSubmissionService:
    """Coordinates validation, explicit confirmation and exactly-once submission."""

    def __init__(
        self,
        validator: TradingValidator,
        orders_gateway: Any,
        confirmation: ConfirmationProvider,
    ) -> None:
        self._validator = validator
        self._gateway = orders_gateway
        self._confirmation = confirmation
        self._submitted: set[str] = set()

    def submit(self, request: OrderRequest) -> Any:
        if request.request_id in self._submitted:
            raise ValueError("This order request has already been submitted")

        validation = self._validator.validate(request)

        if not self._confirmation.confirm(request, validation):
            raise ValueError("Order was not confirmed by user")

        # The request_id is generated once and passed unchanged to the gateway.
        # T-Invest uses it as the idempotency key for PostOrder.
        result = self._gateway.post_order(request)
        self._submitted.add(request.request_id)
        return result
