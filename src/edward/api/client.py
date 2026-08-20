from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from t_tech.invest import Client
from t_tech.invest.constants import INVEST_GRPC_API, INVEST_GRPC_API_SANDBOX

from edward.config.settings import Environment, Settings


@dataclass
class TInvestClient:
    """Thin lifecycle wrapper around the T-Invest Python SDK."""

    settings: Settings
    token: str

    def __post_init__(self) -> None:
        if not self.token.strip():
            raise ValueError("T-Invest API token cannot be empty")
        self._client: Any | None = None

    def __enter__(self) -> Any:
        target = (
            INVEST_GRPC_API
            if self.settings.environment is Environment.PRODUCTION
            else INVEST_GRPC_API_SANDBOX
        )
        self._client = Client(self.token, target=target)
        self._client.__enter__()
        return self._client

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._client is not None:
            self._client.__exit__(exc_type, exc, tb)
            self._client = None

    @property
    def is_production(self) -> bool:
        return self.settings.environment is Environment.PRODUCTION
