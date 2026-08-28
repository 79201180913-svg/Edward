from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Mapping, Optional, Protocol


class ExecutionDecision(StrEnum):
    BUY = "BUY"
    ADD = "ADD"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"


class ExecutionMode(StrEnum):
    ANALYSIS_ONLY = "analysis_only"
    PREPARE_ORDER = "prepare_order"
    USER_CONFIRMATION = "user_confirmation"
    AUTONOMOUS = "autonomous"


class ExecutionStatus(StrEnum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    RECONCILED = "RECONCILED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    RECONCILIATION_ERROR = "RECONCILIATION_ERROR"


class ExecutionEventType(StrEnum):
    CREATED = "CREATED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    REVALIDATION_STARTED = "REVALIDATION_STARTED"
    REVALIDATION_FAILED = "REVALIDATION_FAILED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    CONFIRMED = "CONFIRMED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    STATUS_CHANGED = "STATUS_CHANGED"
    FILL_UPDATED = "FILL_UPDATED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    RECONCILIATION_STARTED = "RECONCILIATION_STARTED"
    RECONCILED = "RECONCILED"
    ERROR = "ERROR"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    execution_id: str
    account_id: str
    instrument_uid: str
    ticker: str
    decision: ExecutionDecision
    side: str
    quantity: Decimal
    order_type: str
    entry_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    strategy: Optional[str] = None
    strategy_score: float = 0.0
    opportunity_score: float = 0.0
    risk_score: float = 0.0
    forecast_quality: Optional[float] = None
    execution_ready: bool = False
    portfolio_weight: Optional[float] = None
    target_weight: Optional[float] = None
    maximum_position_weight: Optional[float] = None
    analysis_snapshot: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("execution_id is required")
        if not self.account_id:
            raise ValueError("account_id is required")
        if not self.instrument_uid:
            raise ValueError("instrument_uid is required")
        if not self.ticker:
            raise ValueError("ticker is required")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.decision not in {
            ExecutionDecision.BUY,
            ExecutionDecision.ADD,
            ExecutionDecision.HOLD,
            ExecutionDecision.REDUCE,
            ExecutionDecision.SELL,
        }:
            raise ValueError("decision is not executable")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    execution_id: str
    status: ExecutionStatus
    broker_order_id: Optional[str] = None
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    commission: Decimal = Decimal("0")
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    execution_id: str
    event_type: ExecutionEventType
    status: ExecutionStatus
    message: str
    created_at: datetime = field(default_factory=_utc_now)
    payload: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionJournalEntry:
    execution_id: str
    account_id: str
    instrument_uid: str
    decision: ExecutionDecision
    side: str
    order_type: str
    requested_quantity: Decimal
    requested_price: Optional[Decimal]
    stop_price: Optional[Decimal]
    execution_ready: bool
    pretrade_status: Optional[str] = None
    broker_order_id: Optional[str] = None
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    commission: Decimal = Decimal("0")
    status: ExecutionStatus = ExecutionStatus.CREATED
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ExecutionJournal(Protocol):
    """Persistence boundary for execution attempts; implementations may use SQLite or another store."""

    def append(self, entry: ExecutionJournalEntry) -> None:
        ...

    def update(self, entry: ExecutionJournalEntry) -> None:
        ...

    def get(self, execution_id: str) -> Optional[ExecutionJournalEntry]:
        ...
