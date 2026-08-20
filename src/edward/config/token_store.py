from __future__ import annotations

import keyring


class TokenStore:
    """Persist the T-Invest token in the operating system credential store."""

    SERVICE_NAME = "edward.t-invest"
    ACCOUNT_NAME = "api-token"

    def save(self, token: str) -> None:
        token = token.strip()
        if not token:
            raise ValueError("API token cannot be empty")
        keyring.set_password(self.SERVICE_NAME, self.ACCOUNT_NAME, token)

    def load(self) -> str | None:
        return keyring.get_password(self.SERVICE_NAME, self.ACCOUNT_NAME)

    def delete(self) -> None:
        try:
            keyring.delete_password(self.SERVICE_NAME, self.ACCOUNT_NAME)
        except keyring.errors.PasswordDeleteError:
            pass
