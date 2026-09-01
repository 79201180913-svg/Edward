from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_PATCH_PATH = Path(__file__).resolve().parents[1] / "runtime" / "tinvest_client_disconnect_patch.py"


class _Handler:
    _client_disconnect_patch_installed = False

    def _send(self, status, payload):
        raise ConnectionAbortedError(10053, "connection aborted")

    def do_POST(self):
        raise AssertionError("not used")


def _load_patch():
    fake_adapter = types.ModuleType("tinvest_adapter")
    fake_adapter.Handler = _Handler
    previous = sys.modules.get("tinvest_adapter")
    sys.modules["tinvest_adapter"] = fake_adapter
    try:
        spec = importlib.util.spec_from_file_location("tinvest_client_disconnect_patch", _PATCH_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            sys.modules.pop("tinvest_adapter", None)
        else:
            sys.modules["tinvest_adapter"] = previous


patch = _load_patch()


def test_is_client_disconnect_recognizes_socket_disconnects():
    assert patch._is_client_disconnect(BrokenPipeError())
    assert patch._is_client_disconnect(ConnectionResetError())
    assert patch._is_client_disconnect(ConnectionAbortedError())


def test_is_client_disconnect_recognizes_windows_10053():
    exc = OSError("connection aborted")
    exc.winerror = 10053
    assert patch._is_client_disconnect(exc)


def test_is_client_disconnect_does_not_swallow_unrelated_errors():
    assert not patch._is_client_disconnect(RuntimeError("real adapter failure"))


def test_install_wraps_send_and_swallows_client_disconnect():
    patch.install()

    handler = _Handler()
    assert handler._send(200, {"ok": True}) is None
    assert _Handler._client_disconnect_patch_installed
