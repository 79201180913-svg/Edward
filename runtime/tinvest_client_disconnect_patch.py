from __future__ import annotations

import errno
import logging

from . import tinvest_adapter

logger = logging.getLogger("edward.tinvest_adapter")

_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)
_DISCONNECT_WINERROR = 10053


def _is_client_disconnect(exc: BaseException) -> bool:
    if isinstance(exc, _DISCONNECT_ERRORS):
        return True
    return getattr(exc, "winerror", None) == _DISCONNECT_WINERROR


def install() -> None:
    """Make client-side HTTP disconnects non-fatal for the local adapter."""
    handler = tinvest_adapter.Handler
    if getattr(handler, "_client_disconnect_patch_installed", False):
        return

    original_send = handler._send

    def _send(self, status, payload):
        try:
            return original_send(self, status, payload)
        except Exception as exc:
            if _is_client_disconnect(exc):
                logger.info("[ADAPTER CLIENT DISCONNECT] response=%s", status)
                return None
            raise

    original_do_post = handler.do_POST

    def do_POST(self):
        try:
            return original_do_post(self)
        except Exception as exc:
            if _is_client_disconnect(exc):
                logger.info("[ADAPTER CLIENT DISCONNECT] request=%s", self.path)
                return None
            raise

    handler._send = _send
    handler.do_POST = do_POST
    handler._client_disconnect_patch_installed = True


__all__ = ["install"]
