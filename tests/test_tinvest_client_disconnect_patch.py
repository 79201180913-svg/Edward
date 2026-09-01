from __future__ import annotations

import types

import tinvest_client_disconnect_patch as patch


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


def test_install_wraps_send_and_swallows_client_disconnect(monkeypatch):
    class Handler:
        _client_disconnect_patch_installed = False

        def _send(self, status, payload):
            raise ConnectionAbortedError(10053, "connection aborted")

        def do_POST(self):
            raise AssertionError("not used")

    module = types.SimpleNamespace(Handler=Handler)
    monkeypatch.setattr(patch, "tinvest_adapter", module)
    patch.install()

    handler = Handler()
    assert handler._send(200, {"ok": True}) is None
    assert Handler._client_disconnect_patch_installed
