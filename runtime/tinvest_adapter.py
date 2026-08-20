from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from t_tech.invest import Client
from t_tech.invest.constants import INVEST_GRPC_API, INVEST_GRPC_API_SANDBOX


HOST = "127.0.0.1"
PORT = int(os.getenv("EDWARD_TINVEST_PORT", "8765"))
TOKEN = os.getenv("EDWARD_TINVEST_TOKEN", "").strip()
ENVIRONMENT = os.getenv("EDWARD_TINVEST_ENV", "sandbox").lower()


def message_to_dict(message: Any) -> dict[str, Any]:
    from google.protobuf.json_format import MessageToDict

    return MessageToDict(message, preserving_proto_field_name=True)


class AdapterState:
    def __init__(self) -> None:
        if not TOKEN:
            raise RuntimeError("T-Invest API token is not configured")
        target = INVEST_GRPC_API if ENVIRONMENT == "production" else INVEST_GRPC_API_SANDBOX
        self.client = Client(TOKEN, target=target)
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    def accounts(self) -> Any:
        return self.client.users.get_accounts()

    def portfolio(self, account_id: str) -> Any:
        return self.client.operations.get_portfolio(account_id=account_id)

    def positions(self, account_id: str) -> Any:
        return self.client.operations.get_positions(account_id=account_id)


STATE = AdapterState()


class Handler(BaseHTTPRequestHandler):
    server_version = "EdwardTInvestAdapter/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Do not log request bodies because they may contain sensitive data.
        sys.stderr.write("Edward T-Invest adapter: " + format % args + "\n")

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ok", "environment": ENVIRONMENT})
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/accounts":
                response = STATE.accounts()
                self._send(200, message_to_dict(response))
                return
            if self.path == "/portfolio":
                account_id = str(payload.get("account_id", "")).strip()
                if not account_id:
                    self._send(400, {"error": "account_id is required"})
                    return
                response = STATE.portfolio(account_id)
                self._send(200, message_to_dict(response))
                return
            if self.path == "/positions":
                account_id = str(payload.get("account_id", "")).strip()
                if not account_id:
                    self._send(400, {"error": "account_id is required"})
                    return
                response = STATE.positions(account_id)
                self._send(200, message_to_dict(response))
                return
            self._send(404, {"error": "not_found"})
        except Exception as exc:
            # Return only the technical error text. Never return the token.
            self._send(502, {"error": type(exc).__name__, "message": str(exc)})


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Edward T-Invest adapter started on http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        STATE.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
