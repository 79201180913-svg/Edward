from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import sys
import tempfile
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from t_tech.invest import Client, MoneyValue, OrderDirection as SDKOrderDirection, OrderType as SDKOrderType, Quotation as SDKQuotation
from t_tech.invest.constants import INVEST_GRPC_API, INVEST_GRPC_API_SANDBOX

HOST = "127.0.0.1"
PORT = int(os.getenv("EDWARD_TINVEST_PORT", "8765"))
TOKEN = os.getenv("EDWARD_TINVEST_TOKEN", "").strip()
ENVIRONMENT = os.getenv("EDWARD_TINVEST_ENV", "sandbox").lower()
REST_TARGET = "https://invest-public-api.tbank.ru" if ENVIRONMENT == "production" else "https://sandbox-invest-public-api.tbank.ru"

logger = logging.getLogger("edward.tinvest_adapter")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _sdk_order_direction(value: Any) -> Any:
    raw = getattr(value, "value", value)
    key = str(raw).upper()
    mapping = {"BUY": SDKOrderDirection.ORDER_DIRECTION_BUY, "ORDER_DIRECTION_BUY": SDKOrderDirection.ORDER_DIRECTION_BUY, "SELL": SDKOrderDirection.ORDER_DIRECTION_SELL, "ORDER_DIRECTION_SELL": SDKOrderDirection.ORDER_DIRECTION_SELL}
    if key in mapping:
        return mapping[key]
    if isinstance(value, SDKOrderDirection):
        return value
    raise ValueError(f"Unsupported order direction: {value!r}")


def _sdk_order_type(value: Any) -> Any:
    raw = getattr(value, "value", value)
    key = str(raw).upper()
    mapping = {"MARKET": SDKOrderType.ORDER_TYPE_MARKET, "ORDER_TYPE_MARKET": SDKOrderType.ORDER_TYPE_MARKET, "LIMIT": SDKOrderType.ORDER_TYPE_LIMIT, "ORDER_TYPE_LIMIT": SDKOrderType.ORDER_TYPE_LIMIT}
    if key in mapping:
        return mapping[key]
    if isinstance(value, SDKOrderType):
        return value
    raise ValueError(f"Unsupported order type: {value!r}")


def _quotation_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return {"units": str(value.get("units", 0)), "nano": int(value.get("nano", 0))}
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    whole = amount.quantize(Decimal("1"))
    nano = int((amount - whole) * Decimal("1000000000"))
    return {"units": str(whole), "nano": nano}


def _sdk_quotation(value: Any) -> Any:
    payload = _quotation_payload(value)
    if payload is None:
        return None
    return SDKQuotation(units=int(payload["units"]), nano=int(payload["nano"]))


def _configure_windows_ca_bundle() -> None:
    if os.name != "nt" or os.environ.get("GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"):
        return
    certs: list[bytes] = []
    seen: set[bytes] = set()
    try:
        context = ssl.create_default_context()
        for cert_der in context.get_ca_certs(binary_form=True):
            if cert_der not in seen:
                seen.add(cert_der)
                certs.append(cert_der)
    except Exception:
        pass
    for store_name in ("ROOT", "CA"):
        try:
            entries = ssl.enum_certificates(store_name)
        except Exception:
            continue
        for cert_der, encoding, _trust in entries:
            if encoding == "x509_asn" and isinstance(cert_der, bytes) and cert_der not in seen:
                seen.add(cert_der)
                certs.append(cert_der)
    if not certs:
        return
    path = Path(tempfile.gettempdir()) / "Edward" / "windows-ca-bundle.pem"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as fh:
        for cert in certs:
            encoded = base64.b64encode(cert).decode("ascii")
            fh.write("-----BEGIN CERTIFICATE-----\n")
            for i in range(0, len(encoded), 64):
                fh.write(encoded[i:i + 64] + "\n")
            fh.write("-----END CERTIFICATE-----\n")
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = str(path)


_configure_windows_ca_bundle()


def _protobuf_to_dict(value: Any) -> Any:
    from google.protobuf.json_format import MessageToDict
    from google.protobuf.message import Message
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Message):
        return MessageToDict(value, preserving_proto_field_name=True)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): _protobuf_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_protobuf_to_dict(v) for v in value]
    try:
        if hasattr(value, "currency") and (hasattr(value, "units") or hasattr(value, "nano")):
            return {"currency": str(getattr(value, "currency", "")), "units": int(getattr(value, "units", 0)), "nano": int(getattr(value, "nano", 0))}
    except Exception:
        pass
    known_fields = ("balance", "money", "securities", "positions", "virtual_positions", "account_id", "order_id", "operation_id", "id", "next_cursor", "has_next", "tracking_id", "status", "state", "currency", "available_value", "blocked_value", "lots_executed", "lots_requested", "stages", "executed_order_price", "executed_commission", "total_order_amount", "initial_order_price", "initial_security_price", "ticker", "figi", "instrument_uid", "order_request_id", "order_date")
    found: dict[str, Any] = {}
    for name in known_fields:
        try:
            if hasattr(value, name):
                attr = getattr(value, name)
                if callable(attr):
                    continue
                found[name] = _protobuf_to_dict(attr)
        except Exception:
            continue
    if found:
        return found
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
    return result or {"value": str(value)}


def message_to_dict(message: Any) -> dict[str, Any]:
    value = _protobuf_to_dict(message)
    return value if isinstance(value, dict) else {"value": value}


def _camel_to_snake(value: Any) -> Any:
    if isinstance(value, list):
        return [_camel_to_snake(v) for v in value]
    if not isinstance(value, dict):
        return value
    return {"".join("_" + c.lower() if c.isupper() else c for c in str(k)).lstrip("_"): _camel_to_snake(v) for k, v in value.items()}


class AdapterState:
    def __init__(self) -> None:
        if not TOKEN:
            raise RuntimeError("T-Invest API token is not configured")
        target = INVEST_GRPC_API if ENVIRONMENT == "production" else INVEST_GRPC_API_SANDBOX
        client = Client(TOKEN, target=target)
        entered = client.__enter__()
        self.client = entered if entered is not None else client

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    def _service(self, name: str) -> Any:
        service = getattr(self.client, name, None)
        if service is None:
            raise RuntimeError(f"T-Invest SDK service '{name}' is unavailable")
        return service

    def _rest_request(self, method: str, payload: dict[str, Any], target: str | None = None) -> dict[str, Any]:
        request = Request(
            f"{target or REST_TARGET}/rest/tinkoff.public.invest.api.contract.v1.{method}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=30.0) as response:
                return _camel_to_snake(json.loads(response.read().decode("utf-8")))
        except HTTPError as exc:
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = ""
            raise RuntimeError(f"T-Invest REST HTTP {exc.code}: {body_text or str(exc)}") from exc
        except URLError as exc:
            raise RuntimeError(f"T-Invest REST API is unavailable: {exc.reason}") from exc

    def accounts(self):
        if ENVIRONMENT == "sandbox":
            return self._rest_request("SandboxService/GetSandboxAccounts", {})
        return message_to_dict(self._service("users").get_accounts())

    def open_sandbox_account(self, name=None):
        return self._service("sandbox").open_sandbox_account(**({"name": name} if name else {}))

    def close_sandbox_account(self, account_id):
        return self._service("sandbox").close_sandbox_account(account_id=account_id)

    def sandbox_pay_in(self, account_id, amount):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть больше 0")
        if amount > Decimal("30000000"):
            raise ValueError("Максимальная сумма пополнения — 30 000 000 RUB")
        whole = amount.quantize(Decimal("1"))
        nano = int((amount - whole) * Decimal("1000000000"))
        money = MoneyValue(currency="rub", units=int(whole), nano=nano)
        result = self._service("sandbox").sandbox_pay_in(account_id=str(account_id), amount=money)
        result_dict = message_to_dict(result)
        result_dict["verification_positions"] = message_to_dict(self._service("sandbox").get_sandbox_positions(account_id=str(account_id)))
        result_dict["verification_account_id"] = str(account_id)
        return result_dict

    def sandbox_positions(self, account_id):
        return self._rest_request("SandboxService/GetSandboxPositions", {"accountId": str(account_id)})

    def sandbox_portfolio(self, account_id):
        return self._rest_request("SandboxService/GetSandboxPortfolio", {"accountId": str(account_id), "currency": "RUB"})

    def positions(self, account_id):
        return self.sandbox_positions(account_id) if ENVIRONMENT == "sandbox" else message_to_dict(self._service("operations").get_positions(account_id=account_id))

    def portfolio(self, account_id):
        return self.sandbox_portfolio(account_id) if ENVIRONMENT == "sandbox" else message_to_dict(self._service("operations").get_portfolio(account_id=account_id))

    def list_instruments(self, kind="SHARE", trade=True):
        methods = {"SHARE": "get_shares", "BOND": "get_bonds", "ETF": "get_etfs", "CURRENCY": "get_currencies", "FUTURES": "get_futures"}
        method_name = methods.get(str(kind).upper())
        if not method_name:
            raise ValueError(f"Unsupported instrument kind: {kind}")
        service = self._service("instruments")
        method = getattr(service, method_name, None)
        if method is None:
            raise RuntimeError(f"T-Invest SDK instruments service does not provide {method_name}()")
        try:
            result = method(instrument_status="INSTRUMENT_STATUS_BASE" if trade else "INSTRUMENT_STATUS_ALL", instrument_exchange="INSTRUMENT_EXCHANGE_UNSPECIFIED")
        except TypeError:
            result = method()
        return message_to_dict(result)

    def last_prices(self, ids):
        return message_to_dict(self._service("market_data").get_last_prices(instrument_id=ids))

    def trading_status(self, instrument_id):
        return message_to_dict(self._service("market_data").get_trading_status(instrument_id=instrument_id))

    def trading_statuses(self, ids):
        return message_to_dict(self._service("market_data").get_trading_statuses(instrument_ids=ids))

    def close_prices(self, ids):
        return self._rest_request("MarketDataService/GetClosePrices", {"instruments": [{"instrumentId": str(value)} for value in ids], "instrumentStatus": "INSTRUMENT_STATUS_BASE"})

    def orders(self, account_id):
        return message_to_dict(self._service("sandbox").get_sandbox_orders(account_id=account_id)) if ENVIRONMENT == "sandbox" else message_to_dict(self._service("orders").get_orders(account_id=account_id))

    def order_state(self, account_id, order_id):
        if ENVIRONMENT == "sandbox":
            return message_to_dict(self._service("sandbox").get_sandbox_order_state(account_id=account_id, order_id=order_id))
        return message_to_dict(self._service("orders").get_order_state(account_id=account_id, order_id=order_id))

    def order_price(self, payload):
        direction = str(payload["direction"]).upper()
        if direction in {"BUY", "ORDER_DIRECTION_BUY"}:
            direction = "ORDER_DIRECTION_BUY"
        elif direction in {"SELL", "ORDER_DIRECTION_SELL"}:
            direction = "ORDER_DIRECTION_SELL"
        else:
            raise ValueError(f"Unsupported order direction: {payload['direction']!r}")
        request = {"accountId": str(payload["account_id"]), "instrumentId": str(payload["instrument_id"]), "price": _quotation_payload(payload.get("price")), "direction": direction, "quantity": str(int(payload["quantity"]))}
        method = "SandboxService/GetSandboxOrderPrice" if ENVIRONMENT == "sandbox" else "OrdersService/GetOrderPrice"
        return self._rest_request(method, request)

    def operations(self, account_id, limit=1000):
        method = "SandboxService/GetSandboxOperationsByCursor" if ENVIRONMENT == "sandbox" else "OperationsService/GetOperationsByCursor"
        return self._rest_request(method, {"accountId": account_id, "limit": max(1, min(int(limit), 1000)), "withoutCommissions": False, "withoutTrades": False})

    def create_order(self, payload):
        direction = _sdk_order_direction(payload["direction"])
        order_type = _sdk_order_type(payload["order_type"])
        kwargs = {"quantity": int(payload["quantity"]), "direction": direction, "account_id": str(payload["account_id"]), "order_type": order_type, "instrument_id": str(payload["instrument_uid"]), "order_id": str(payload["request_id"])}
        if payload.get("price") is not None:
            kwargs["price"] = _sdk_quotation(payload["price"])
        if ENVIRONMENT == "sandbox":
            return message_to_dict(self._service("sandbox").post_sandbox_order(**kwargs))
        return message_to_dict(self._service("orders").post_order(**kwargs))

    def cancel_order(self, account_id, order_id):
        if ENVIRONMENT == "sandbox":
            return message_to_dict(self._service("sandbox").cancel_sandbox_order(account_id=account_id, order_id=order_id))
        return message_to_dict(self._service("orders").cancel_order(account_id=account_id, order_id=order_id))

    def replace_order(self, payload):
        kwargs = {"order_id": payload["order_id"], "quantity": int(payload["quantity"]), "account_id": str(payload["account_id"])}
        if payload.get("price") is not None:
            kwargs["price"] = _sdk_quotation(payload["price"])
        if ENVIRONMENT == "sandbox":
            return message_to_dict(self._service("sandbox").replace_sandbox_order(**kwargs))
        return message_to_dict(self._service("orders").replace_order(**kwargs))

    def cancel_all_orders(self, account_id):
        if ENVIRONMENT == "sandbox":
            return message_to_dict(self._service("sandbox").cancel_sandbox_orders(account_id=account_id))
        return message_to_dict(self._service("orders").cancel_all_orders(account_id=account_id))


STATE = AdapterState()


class Handler(BaseHTTPRequestHandler):
    server_version = "EdwardTInvestAdapter/0.1"

    def log_message(self, format, *args):
        sys.stderr.write("Edward T-Invest adapter: " + format + "\n")

    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok", "environment": ENVIRONMENT})
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self):
        try:
            p = self._read_json()
            if self.path == "/accounts": self._send(200, STATE.accounts()); return
            if self.path == "/accounts/create": self._send(200, message_to_dict(STATE.open_sandbox_account(p.get("name")))); return
            if self.path == "/accounts/close": self._send(200, message_to_dict(STATE.close_sandbox_account(str(p.get("account_id", ""))))); return
            if self.path == "/accounts/pay-in": self._send(200, STATE.sandbox_pay_in(str(p["account_id"]), p["amount"])); return
            if self.path == "/accounts/sandbox-positions": self._send(200, STATE.sandbox_positions(str(p["account_id"]))); return
            if self.path == "/accounts/sandbox-portfolio": self._send(200, STATE.sandbox_portfolio(str(p["account_id"]))); return
            if self.path == "/positions": self._send(200, STATE.positions(str(p["account_id"]))); return
            if self.path == "/portfolio": self._send(200, STATE.portfolio(str(p["account_id"]))); return
            if self.path == "/instruments/list": self._send(200, STATE.list_instruments(str(p.get("instrument_kind", "SHARE")), bool(p.get("api_trade_available_flag", True)))); return
            if self.path == "/market/last-prices": self._send(200, STATE.last_prices(list(p.get("instrument_ids", [])))); return
            if self.path == "/market/close-prices": self._send(200, STATE.close_prices(list(p.get("instrument_ids", [])))); return
            if self.path == "/market/trading-status": self._send(200, STATE.trading_status(str(p["instrument_id"]))); return
            if self.path == "/market/trading-statuses": self._send(200, STATE.trading_statuses(list(p.get("instrument_ids", [])))); return
            if self.path == "/orders": self._send(200, STATE.orders(str(p["account_id"]))); return
            if self.path == "/orders/state": self._send(200, STATE.order_state(str(p["account_id"]), str(p["order_id"]))); return
            if self.path == "/orders/price": self._send(200, STATE.order_price(p)); return
            if self.path == "/orders/create": self._send(200, STATE.create_order(p)); return
            if self.path == "/orders/cancel": self._send(200, STATE.cancel_order(str(p.get("account_id", "")), str(p.get("order_id", "")))); return
            if self.path == "/orders/replace": self._send(200, STATE.replace_order(p)); return
            if self.path == "/operations": self._send(200, STATE.operations(str(p.get("account_id", "")), int(p.get("limit", 1000)))); return
            self._send(404, {"error": "not_found"})
        except Exception as exc:
            logger.exception("[ADAPTER ERROR] %s", exc)
            self._send(500, {"error": str(exc), "type": type(exc).__name__})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[INFO] T-Invest adapter listening on http://{HOST}:{PORT}")
    print(f"[INFO] Environment: {ENVIRONMENT.upper()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        STATE.close()
        server.server_close()


if __name__ == "__main__": main()
