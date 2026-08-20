from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Environment(StrEnum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True)
class Settings:
    environment: Environment = Environment.SANDBOX
    history_path: str = "data/trading_history.xlsx"

    @property
    def api_endpoint(self) -> str:
        if self.environment is Environment.PRODUCTION:
            return "invest-public-api.tbank.ru:443"
        return "sandbox-invest-public-api.tbank.ru:443"

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION
