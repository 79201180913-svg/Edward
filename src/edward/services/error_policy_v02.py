from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    AUTH = "AUTH"
    VALIDATION = "VALIDATION"
    BUSINESS = "BUSINESS"
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER = "SERVER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ErrorDecision:
    category: ErrorCategory
    retryable: bool
    user_message: str


def classify_error(error: Exception) -> ErrorDecision:
    status = getattr(error, "status_code", None)
    code = str(getattr(error, "error_code", "") or "").upper()
    message = str(error)
    if status in (401, 403) or "UNAUTH" in code or "AUTH" in code:
        return ErrorDecision(ErrorCategory.AUTH, False, "Не удалось авторизоваться в T-Invest API.")
    if status == 429 or "RESOURCE_EXHAUSTED" in code or "RATE" in code:
        return ErrorDecision(ErrorCategory.RATE_LIMIT, True, "T-Invest API временно ограничил частоту запросов.")
    if status is not None and status >= 500:
        return ErrorDecision(ErrorCategory.SERVER, True, "T-Invest API временно недоступен.")
    if isinstance(error, TimeoutError) or "TIMEOUT" in code or "timed out" in message.lower():
        return ErrorDecision(ErrorCategory.TIMEOUT, True, "Истекло время ожидания ответа T-Invest API.")
    if "unavailable" in message.lower() or "connection" in message.lower() or "network" in message.lower():
        return ErrorDecision(ErrorCategory.NETWORK, True, "Нет соединения с T-Invest API.")
    if status in (400, 422):
        return ErrorDecision(ErrorCategory.VALIDATION, False, "Заявка отклонена из-за некорректных параметров.")
    if status == 409:
        return ErrorDecision(ErrorCategory.BUSINESS, False, "Операция конфликтует с текущим состоянием заявки или счета.")
    return ErrorDecision(ErrorCategory.UNKNOWN, bool(getattr(error, "retryable", False)), "Не удалось выполнить операцию.")


def safe_error_details(error: Exception) -> dict[str, Any]:
    return {"type": type(error).__name__, "message": str(error), "api_code": getattr(error, "error_code", None), "status_code": getattr(error, "status_code", None), "retryable": getattr(error, "retryable", False)}
