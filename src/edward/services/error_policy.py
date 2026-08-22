from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ApiErrorCategory(str, Enum):
    AUTH = "AUTH"
    VALIDATION = "VALIDATION"
    BUSINESS = "BUSINESS"
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER = "SERVER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ApiErrorInfo:
    category: ApiErrorCategory
    code: str | None
    message: str
    retryable: bool


def classify_api_error(status: int | None = None, code: str | None = None, message: str = "") -> ApiErrorInfo:
    text = message.lower()
    if status in (401, 403):
        return ApiErrorInfo(ApiErrorCategory.AUTH, code, message, False)
    if status == 429 or "resource_exhausted" in text or "rate limit" in text:
        return ApiErrorInfo(ApiErrorCategory.RATE_LIMIT, code, message, True)
    if status is not None and 500 <= status <= 599:
        return ApiErrorInfo(ApiErrorCategory.SERVER, code, message, True)
    if status in (400, 422):
        return ApiErrorInfo(ApiErrorCategory.VALIDATION, code, message, False)
    if any(x in text for x in ("timeout", "deadline exceeded")):
        return ApiErrorInfo(ApiErrorCategory.TIMEOUT, code, message, True)
    if any(x in text for x in ("connection", "network", "unavailable")):
        return ApiErrorInfo(ApiErrorCategory.NETWORK, code, message, True)
    if code:
        return ApiErrorInfo(ApiErrorCategory.BUSINESS, code, message, False)
    return ApiErrorInfo(ApiErrorCategory.UNKNOWN, code, message, False)
