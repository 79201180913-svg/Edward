from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from t_tech.invest import Client
from t_tech.invest.constants import INVEST_GRPC_API, INVEST_GRPC_API_SANDBOX


HOST = "127.0.0.1"
PORT = int(os.getenv("EDWARD_TINVEST_PORT", "8765"))
TOKEN = os.getenv("EDWARD_TINVEST_TOKEN", "").strip()
ENVIRONMENT = os.getenv("EDWARD_TINVEST_ENV", "sandbox").lower()
REST_TARGET = "https://invest-public-api.tbank.ru" if ENVIRONMENT == "production" else "https://sandbox-invest-public-api.tbank.ru"


def _configure_windows_ca_bundle() -> None:
    if os.name != "nt":
        return
    if os.environ.get("GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"):
        return
    certs: list[bytes] = []
    seen: set[bytes] = set()
    for store_name in ("ROOT", "CA"):
        try:
            entries = ssl.enum_certificates(store_name)
        except Exception:
            continue
        for cert_der, encoding, trust in entries:
            if encoding != "x509_asn":
                continue
            if not isinstance(cert_der, bytes) or cert_der in seen:
                continue
            seen.add(cert_der)
            certs.append(cert_der)
    if not certs:
        return
    bundle_dir = Path(tempfile.gettempdir()) / "Edward"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / "windows-ca-bundle.pem"
    with bundle_path.open("w", encoding="ascii") as fh:
        for cert_der in certs:
            encoded = base64.b64encode(cert_der).decode("ascii")
            fh.write("-----BEGIN CERTIFICATE-----\n")
            for i in range(0, len(encoded), 64):
                fh.write(encoded[i : i + 64] + "\n")
            fh.write("-----END CERTIFICATE-----\n")
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = str(bundle_path)


_configure_windows_ca_bundle()


def _protobuf_to_dict(value: Any) -> Any:
    from google.protobuf.json_format import MessageToDict
    from google.protobuf.message import Message

    if value is None:
        return None
    if isinstance(value, Message):
        return MessageToDict(value, preserving_proto_field_name=True)
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): _protobuf_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_protobuf_to_dict(v) for v in value]
    for attr in ("response", "result", "data"):
        nested = getattr(value, attr, None)
        if nested is not None and nested is not value:
            try:
                return _protobuf_to_dict(nested)
            except Exception:
                pass
    try:
        if hasattr(value, "items"):
            return {str(k): _protobuf_to_dict(v) for k, v in value.items()}
    except Exception:
        pass
    result: dict[str, Any] = {}
    for name in dir(value):
        if name.startswith("_"):
            continue
        try:
            attr = getattr(value, name)
        except Exception:
            continue
        if callable(attr):
            continue
        if isinstance(attr, (str, int, float, bool, type(None), bytes, list, tuple, dict)):
            result[name] = _protobuf_to_dict(attr)
    if result:
        return result
    return {"value": str(value)}


def message_to_dict(message: Any) -> dict[str, Any]:
    converted = _protobuf_to_dict(message)
    if isinstance(converted, dict):
        return converted
    return {"value": converted}


def _camel_to_snake(value: Any) -> Any:
    if isinstance(value, list):
        return [_camel_to_snake(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        snake = "".join("_" + char.lower() if char.isupper() else char for char in str(key)).lstrip("_")
        result[snake] = _camel_to_snake(item)
    return result


class AdapterState:
    def __init__(self) -> None:
        if not TOKEN:
            raise RuntimeError("T-Invest API token is not configured")
        target = INVEST_GRPC_API if ENVIRONMENT == "production" else INVEST_GRPC_API_SANDBOX
        client = Client(TOKEN, target=target)
        entered_client = client.__enter__()
        self.client = entered_client if entered_client is not None else client

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    def _service(self, name: str) -> Any:
        service = getattr(self.client, name, None)
        if service is None:
            raise RuntimeError(
                f"T-Invest SDK service '{name}' is unavailable on Client "
                f"(SDK object: {type(self.client).__module__}.{type(self.client).__name__})"
            )
        return service

    def _rest_request(self, service_method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{REST_TARGET}/rest/tinkoff.public.invest.api.contract.v1.{service_method}"
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30.0) as response:
                return _camel_to_snake(json.loads(response.read().decode("utf-8")))
        except HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except Exception:
                body = {"error": "http_error", "message": str(exc)}
            raise RuntimeError(body.get("message", body.get("error", str(exc)))) from exc
        except URLError as exc:
            raise RuntimeError(f"T-Invest REST API is unavailable: {exc.reason}") from exc

    def accounts(self) -> Any:
        return self._service("users").get_accounts()

    def open_sandbox_account(self, name: str | None = None) -> Any:
        request: dict[str, Any] = {}
        if name:
            request["name"] = name
        return self._service("sandbox").open_sandbox_account(**request)

    def close_sandbox_account(self, account_id: str) -> Any:
        return self._service("sandbox").close_sandbox_account(account_id=account_id)

    def portfolio(self, account_id: str) -> Any:
        return self._service("operations").get_portfolio(account_id=account_id)

    def positions(self, account_id: str) -> Any:
        return self._service("operations").get_positions(account_id=account_id)

    def find_instrument(self, query: str, trade_available_only: bool = True) -> Any:
        return self._rest_request(
            "InstrumentsService/FindInstrument",
            {
                "query": query,
                "instrumentKind": "INSTRUMENT_TYPE_UNSPECIFIED",
                "apiTradeAvailableFlag": trade_available_only,
            },
        )

    def list_instruments(self, instrument_kind: str = "SHARE", trade_available_only: bool = True) -> Any:
        method_map = {
            "SHARE": "Shares",
            "BOND": "Bonds",
            "ETF": "Etfs",
            "CURRENCY": "Currencies",
            "FUTURES": "Futures",
            "OPTION": "Options",
        }
        method_name = method_map.get(instrument_kind.upper())
        if method_name is None:
            raise ValueError(f"Unsupported instrument kind: {instrument_kind}")
        return self._rest_request(
            f"InstrumentsService/{method_name}",
            {
                "instrumentStatus": "INSTRUMENT_STATUS_BASE" if trade_available_only else "INSTRUMENT_STATUS_ALL",
                "instrumentExchange": "INSTRUMENT_EXCHANGE_UNSPECIFIED",
            },
        )

    def last_prices(self, instrument_ids: list[str]) -> Any:
        return self._service("market_data").get_last_prices(instrument_id=instrument_ids)

    def trading_status(self, instrument_id: str) -> Any:
        return self._service("market_data").get_trading_status(instrument_id=instrument_id)

    def orders(self, account_id: str) -> Any:
        return self._service("orders").get_orders(account_id=account_id)

    def order_state(self, account_id: str, order_id: str) -> Any:
        return self._service("orders").get_order_state(account_id=account_id, order_id=order_id)

    def create_order(self, payload: dict[str, Any]) -> Any:
        kwargs = {
            "quantity": payload["quantity"],
            "direction": payload["direction"],
            "account_id": payload["account_id"],
            "order_type": payload["order_type"],
            "instrument_id": payload["instrument_uid"],
            "order_id": payload["request_id"],
        }
        for name in ("price", "stop_price"):
            if payload.get(name) is not None:
                kwargs[name] = payload[name]
        return self._service("orders").post_order(**kwargs)

    def cancel_order(self, account_id: str, order_id: str) -> Any:
        return self._service("orders").cancel_order(account_id=account_id, order_id=order_id)

    def replace_order(self, payload: dict[str, Any]) -> Any:
        kwargs = {
            "order_id": payload["order_id"],
            "quantity": payload["quantity"],
            "account_id": payload["account_id"],
        }
        if payload.get("price") is not None:
            kwargs["price"] = payload["price"]
        return self._service("orders").replace_order(**kwargs)


STATE = AdapterState()


class Handler(BaseHTTPRequestHandler):
    server_version = "EdwardTInvestAdapter/0.1"

    def log_message(self, format: str, *args: Any) -> None:
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
                self._send(200, message_to_dict(STATE.accounts()))
                return
            if self.path == "/accounts/create":
                name = str(payload.get("name", "")).strip() or None
                self._send(200, message_to_dict(STATE.open_sandbox_account(name)))
                return
            if self.path == "/accounts/close":
                account_id = str(payload.get("account_id", "")).strip()
                if not account_id:
                    self._send(400, {"error": "account_id is required"})
                    return
                self._send(200, message_to_dict(STATE.close_sandbox_account(account_id)))
                return
            if self.path == "/portfolio":
                account_id = str(payload.get("account_id", "")).strip()
                if not account_id:
                    self._send(400, {"error": "account_id is required"})
                    return
                self._send(200, message_to_dict(STATE.portfolio(account_id)))
                return
            if self.path == "/positions":
                account_id = str(payload.get("account_id", "")).strip()
                if not account_id:
                    self._send(400, {"error": "account_id is required"})
                    return
                self._send(200, message_to_dict(STATE.positions(account_id)))
                return
            if self.path == "/instruments/search":
                query = str(payload.get("query", "")).strip()
                if not query:
                    self._send(400, {"error": "query is required"})
                    return
                self._send(200, message_to_dict(STATE.find_instrument(query, bool(payload.get("api_trade_available_flag", True)))))
                return
            if self.path == "/instruments/list":
                kind = str(payload.get("instrument_kind", "SHARE")).strip().upper()
                trade_available_only = bool(payload.get("api_trade_available_flag", True))
                self._send(200, message_to_dict(STATE.list_instruments(kind, trade_available_only)))
                return
            if self.path == "/market/last-prices":
                instrument_ids = [str(value) for value in payload.get("instrument_ids", [])]
                self._send(200, message_to_dict(STATE.last_prices(instrument_ids)))
                return
            if self.path == "/market/trading-status":
                instrument_id = str(payload.get("instrument_id", "")).strip()
                if not instrument_id:
                    self._send(400, {"error": "instrument_id is required"})
                    return
                self._send(200, message_to_dict(STATE.trading_status(instrument_id)))
                return
            if self.path == "/orders":
                self._send(200, message_to_dict(STATE.orders(str(payload.get("account_id", "")).strip())))
                return
            if self.path == "/orders/state":
                self._send(200, message_to_dict(STATE.order_state(str(payload.get("account_id", "")).strip(), str(payload.get("order_id", "")).strip())))
                return
            if self.path == "/orders/create":
                self._send(200, message_to_dict(STATE.create_order(payload)))
                return
            if self.path == "/orders/cancel":
                self._send(200, message_to_dict(STATE.cancel_order(str(payload.get("account_id", "")).strip(), str(payload.get("order_id", "")).strip())))
                return
            if self.path == "/orders/replace":
                self._send(200, message_to_dict(STATE.replace_order(payload)))
                return
            self._send(404, {"error": "not_found"})
        except Exception as exc:
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
