from __future__ import annotations

import base64
import os
import ssl
import tempfile
import time
from pathlib import Path


def _load_local_env() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or key in os.environ:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            os.environ[key] = value
    except OSError:
        return


def _windows_ca_bundle() -> bytes | None:
    if os.name != "nt":
        return None
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
        return None
    output: list[str] = []
    for cert in certs:
        encoded = base64.b64encode(cert).decode("ascii")
        output.append("-----BEGIN CERTIFICATE-----")
        output.extend(encoded[i:i + 64] for i in range(0, len(encoded), 64))
        output.append("-----END CERTIFICATE-----")
    return ("\n".join(output) + "\n").encode("ascii")


def _configure_grpc_tls() -> None:
    roots = _windows_ca_bundle()
    if not roots:
        return
    path = Path(tempfile.gettempdir()) / "Edward" / "windows-ca-bundle.pem"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(roots)
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = str(path)
    try:
        import grpc
        original = grpc.ssl_channel_credentials
        if getattr(original, "__edward_windows_roots__", False):
            return

        def ssl_channel_credentials_with_windows_roots(root_certificates=None, private_key=None, certificate_chain=None):
            effective_roots = roots if root_certificates is None else root_certificates
            return original(root_certificates=effective_roots, private_key=private_key, certificate_chain=certificate_chain)

        ssl_channel_credentials_with_windows_roots.__edward_windows_roots__ = True
        grpc.ssl_channel_credentials = ssl_channel_credentials_with_windows_roots
    except Exception:
        return


_load_local_env()
_configure_grpc_tls()

import tinvest_adapter as _adapter
from stop_order_adapter_patch import install as install_stop_order_adapter_patch


def _refresh_adapter_config() -> None:
    _adapter.TOKEN = os.getenv("EDWARD_TINVEST_TOKEN", "").strip()
    _adapter.ENVIRONMENT = os.getenv("EDWARD_TINVEST_ENV", "sandbox").lower()
    _adapter.PORT = int(os.getenv("EDWARD_TINVEST_PORT", "8765"))
    _adapter.REST_TARGET = "https://invest-public-api.tbank.ru" if _adapter.ENVIRONMENT == "production" else "https://sandbox-invest-public-api.tbank.ru"


def _sdk_order_type(value):
    raw = getattr(value, "value", value)
    key = str(raw).upper()
    mapping = {
        "MARKET": _adapter.SDKOrderType.ORDER_TYPE_MARKET,
        "ORDER_TYPE_MARKET": _adapter.SDKOrderType.ORDER_TYPE_MARKET,
        "LIMIT": _adapter.SDKOrderType.ORDER_TYPE_LIMIT,
        "ORDER_TYPE_LIMIT": _adapter.SDKOrderType.ORDER_TYPE_LIMIT,
    }
    bestprice = getattr(_adapter.SDKOrderType, "ORDER_TYPE_BESTPRICE", None) or getattr(_adapter.SDKOrderType, "ORDER_TYPE_BEST_PRICE", None)
    if bestprice is not None:
        mapping.update({"BESTPRICE": bestprice, "BEST_PRICE": bestprice, "ORDER_TYPE_BESTPRICE": bestprice})
    if key in mapping:
        return mapping[key]
    if isinstance(value, _adapter.SDKOrderType):
        return value
    raise ValueError(f"Unsupported ordinary order type: {value!r}")


def _sandbox_accounts(self):
    result = self._service("users").get_accounts()
    result = _adapter.message_to_dict(result)
    _adapter.logger.info("[SANDBOX ACCOUNTS SDK] accounts=%s", len(result.get("accounts", []) or []))
    return result


def _sandbox_positions(self, account_id):
    result = self._service("sandbox").get_sandbox_positions(account_id=str(account_id))
    result = _adapter.message_to_dict(result)
    _adapter.logger.info("[SANDBOX POSITIONS SDK] account_id=%s securities=%s money=%s", account_id, len(result.get("securities", []) or []), len(result.get("money", []) or []))
    return result


def _money_to_number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, dict):
        units = float(value.get("units", 0))
        nano = float(value.get("nano", 0)) / 1_000_000_000
        return units + nano
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sandbox_portfolio(self, account_id):
    result = self._service("sandbox").get_sandbox_portfolio(account_id=str(account_id))
    result = _adapter.message_to_dict(result)
    total = 0.0
    for position in result.get("positions", []) or []:
        if not isinstance(position, dict):
            continue
        for key in ("current_price", "market_value", "quantity_lots", "quantity"):
            if key not in position:
                continue
            candidate = position.get(key)
            if isinstance(candidate, dict) and "units" in candidate:
                total += _money_to_number(candidate)
                break
    result.setdefault("total_amount_portfolio", total)
    _adapter.logger.info("[SANDBOX PORTFOLIO SDK] account_id=%s positions=%s total=%s", account_id, len(result.get("positions", []) or []), result.get("total_amount_portfolio"))
    return result


def _sandbox_operations(self, account_id, limit=1000):
    service = self._service("sandbox")
    method = getattr(service, "get_sandbox_operations_by_cursor", None) or getattr(service, "get_sandbox_operations", None)
    if method is None:
        raise RuntimeError("T-Invest SDK sandbox service does not provide operations methods")
    try:
        result = method(account_id=str(account_id))
    except TypeError:
        result = method(str(account_id))
    result = _adapter.message_to_dict(result)
    items = result.get("items")
    if isinstance(items, list):
        result["items"] = items[: max(0, int(limit))]
    return result


def _sandbox_create_order(self, payload):
    direction = str(payload["direction"]).upper()
    if direction in {"BUY", "ORDER_DIRECTION_BUY"}:
        direction = "ORDER_DIRECTION_BUY"
    elif direction in {"SELL", "ORDER_DIRECTION_SELL"}:
        direction = "ORDER_DIRECTION_SELL"
    else:
        raise ValueError(f"Unsupported order direction: {payload['direction']!r}")
    order_type = str(payload["order_type"]).upper()
    if order_type in {"MARKET", "ORDER_TYPE_MARKET"}:
        order_type = "ORDER_TYPE_MARKET"
    elif order_type in {"LIMIT", "ORDER_TYPE_LIMIT"}:
        order_type = "ORDER_TYPE_LIMIT"
    elif order_type in {"BESTPRICE", "BEST_PRICE", "ORDER_TYPE_BESTPRICE"}:
        order_type = "ORDER_TYPE_BESTPRICE"
    else:
        raise ValueError(f"Unsupported order type: {payload['order_type']!r}")
    request_id = str(payload.get("request_id") or payload.get("order_id") or "")
    instrument_id = str(payload.get("instrument_uid") or payload.get("instrument_id") or "")
    if not request_id:
        raise ValueError("Sandbox order request_id/order_id is required")
    if not instrument_id:
        raise ValueError("Sandbox order instrument_uid/instrument_id is required")
    request = {"quantity": str(int(payload["quantity"])), "direction": direction, "accountId": str(payload["account_id"]), "orderType": order_type, "orderId": request_id, "instrumentId": instrument_id}
    if payload.get("price") is not None:
        request["price"] = _adapter._quotation_payload(payload["price"])
    if payload.get("time_in_force") is not None:
        request["timeInForce"] = str(payload["time_in_force"])
    if payload.get("price_type") is not None:
        request["priceType"] = str(payload["price_type"])
    if payload.get("confirm_margin_trade") is not None:
        request["confirmMarginTrade"] = bool(payload["confirm_margin_trade"])
    result = self._rest_request("SandboxService/PostSandboxOrder", request)
    _adapter.logger.info("[SANDBOX ORDER REST] request_id=%s order_id=%s status=%s", request_id, result.get("order_id"), result.get("execution_report_status"))
    return result


def _list_instruments(self, kind="SHARE", trade=True):
    key = str(kind).upper()
    method_map = {
        "SHARE": "Shares", "BOND": "Bonds", "ETF": "Etfs", "CURRENCY": "Currencies",
        "FUTURES": "Futures", "OPTION": "Options", "SP": "StructuredNotes", "DFA": "Dfas",
    }
    method_name = method_map.get(key)
    if method_name is None:
        raise ValueError(f"Unsupported instrument kind: {kind}")
    request = {"instrumentStatus": "INSTRUMENT_STATUS_BASE" if trade else "INSTRUMENT_STATUS_ALL", "instrumentExchange": "INSTRUMENT_EXCHANGE_UNSPECIFIED"}
    return self._rest_request(f"InstrumentsService/{method_name}", request)


LAST_PRICES_BATCH_SIZE = 50
LAST_PRICES_RETRIES = 2
LAST_PRICES_RETRY_DELAY_SECONDS = 0.5


def _last_prices(self, ids):
    values = [str(value) for value in ids]
    if not values:
        return {"last_prices": []}
    merged: dict[str, object] = {"last_prices": []}
    for start in range(0, len(values), LAST_PRICES_BATCH_SIZE):
        chunk = values[start:start + LAST_PRICES_BATCH_SIZE]
        for attempt in range(LAST_PRICES_RETRIES + 1):
            try:
                response = self._rest_request(
                    "MarketDataService/GetLastPrices",
                    {"instrumentId": chunk, "lastPriceType": "LAST_PRICE_UNSPECIFIED"},
                )
                if isinstance(response, dict):
                    prices = response.get("last_prices")
                    if isinstance(prices, list):
                        merged["last_prices"].extend(prices)
                    for key, value in response.items():
                        if key != "last_prices" and key not in merged:
                            merged[key] = value
                break
            except RuntimeError as exc:
                if "HTTP 504" not in str(exc) or attempt >= LAST_PRICES_RETRIES:
                    raise
                time.sleep(LAST_PRICES_RETRY_DELAY_SECONDS * (attempt + 1))
    return merged


def _close_prices(self, ids):
    return self._rest_request("MarketDataService/GetClosePrices", {"instruments": [{"instrumentId": str(value)} for value in ids], "instrumentStatus": "INSTRUMENT_STATUS_BASE"})


def _trading_status(self, instrument_id):
    return self._rest_request("MarketDataService/GetTradingStatus", {"instrumentId": str(instrument_id)})


def _trading_statuses(self, ids):
    return self._rest_request("MarketDataService/GetTradingStatuses", {"instrumentId": [str(value) for value in ids]})


_refresh_adapter_config()
_adapter._sdk_order_type = _sdk_order_type
_adapter.AdapterState.accounts = _sandbox_accounts
_adapter.AdapterState.sandbox_positions = _sandbox_positions
_adapter.AdapterState.sandbox_portfolio = _sandbox_portfolio
_adapter.AdapterState.operations = _sandbox_operations
_adapter.AdapterState.create_order = _sandbox_create_order
_adapter.AdapterState.list_instruments = _list_instruments
_adapter.AdapterState.last_prices = _last_prices
_adapter.AdapterState.close_prices = _close_prices
_adapter.AdapterState.trading_status = _trading_status
_adapter.AdapterState.trading_statuses = _trading_statuses
install_stop_order_adapter_patch(_adapter)

if __name__ == "__main__":
    _adapter.main()
