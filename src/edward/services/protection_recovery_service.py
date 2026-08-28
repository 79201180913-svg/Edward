from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from edward.services.account_state_refresh_service import AccountState
from edward.services.autonomous_protection_service import AutonomousProtectionService


@dataclass(frozen=True, slots=True)
class ProtectionRecoveryResult:
    recovered: bool
    status: str
    reasons: tuple[str, ...] = ()


class ProtectionRecoveryService:
    """Restore missing protection for existing positions using explicit stop prices."""

    def __init__(self, protection: AutonomousProtectionService) -> None:
        self._protection = protection

    def recover(self, *, account_id: str, state: AccountState, stop_prices: dict[str, Decimal | int | float | str]) -> ProtectionRecoveryResult:
        reasons: list[str] = []
        attempted = False
        for position in state.positions or ():
            uid = self._uid(position)
            quantity = self._quantity(position)
            if not uid or quantity <= 0:
                continue
            if uid not in stop_prices:
                reasons.append(f"STOP_PRICE_REQUIRED:{uid}")
                continue
            attempted = True
            result = self._protection.recover_position(account_id=account_id, instrument_uid=uid, quantity=quantity, stop_price=stop_prices[uid])
            if not result.protected:
                reasons.append(f"{uid}:{result.reason or result.status}")
        if reasons:
            return ProtectionRecoveryResult(False, "RECOVERY_FAILED", tuple(reasons))
        return ProtectionRecoveryResult(True, "RECOVERED" if attempted else "NOTHING_TO_RECOVER")

    @staticmethod
    def _uid(position: Any) -> str:
        if isinstance(position, dict):
            return str(position.get("instrument_uid", position.get("instrument_id", "")))
        return str(getattr(position, "instrument_uid", getattr(position, "instrument_id", "")))

    @staticmethod
    def _quantity(position: Any) -> int:
        value = position.get("quantity", position.get("lots", 0)) if isinstance(position, dict) else getattr(position, "quantity", getattr(position, "lots", 0))
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0


__all__ = ["ProtectionRecoveryResult", "ProtectionRecoveryService"]
