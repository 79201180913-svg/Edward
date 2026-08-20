from __future__ import annotations

import keyring


SERVICE_NAME = "EdwardTradingPlatform"
TOKEN_KEY = "t-invest-api-token"


class TokenStore:
    """Stores the T-Invest API token in the operating system credential store."""

    def save(self, token: str) -> None:
        token = token.strip()
        if not token:
            raise ValueError("T-Invest API token cannot be empty")
        keyring.set_password(SERVICE_NAME, TOKEN_KEY, token)

    def get(self) -> str | None:
        return keyring.get_password(SERVICE_NAME, TOKEN_KEY)

    def delete(self) -> None:
        try:
            keyring.delete_password(SERVICE_NAME, TOKEN_KEY)
        except keyring.errors.PasswordDeleteError:
            pass
