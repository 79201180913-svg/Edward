from __future__ import annotations

import base64
import os
import ssl
import tempfile
from pathlib import Path


def _load_local_env() -> None:
    """Load Edward's local .env before importing the T-Invest SDK."""
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
    """Return Windows trusted roots as PEM bytes."""
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
    """Make gRPC explicitly use Windows trusted roots before SDK import."""
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
from datetime import datetime, timedelta, timezone


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
    """Sandbox accounts must use SandboxService/GetSandboxAccounts, not Users/GetAccounts."""
    result = self._rest_request("SandboxService/GetSandboxAccounts", {})
    _adapter.logger.info("[SANDBOX ACCOUNTS REST] accounts=%s", len(result.get("accounts", []) or []))
    return result


def _sandbox_positions(self, account_id):
    result = self._rest_request("SandboxService/GetSandboxPositions", {"accountId": str(account_id)})
    _adapter.logger.info("[SANDBOX POSITIONS REST] account_id=%s securities=%s money=%s", account_id, len(result.get("securities", []) or []), len(result.get("money", []) or []))
    return result


def _sandbox_portfolio(self, account_id):
    result = self._rest_request("SandboxService/GetSandboxPortfolio", {"accountId": str(account_id), "currency": "RUB"})
    _adapter.logger.info("[SANDBOX PORTFOLIO REST] account_id=%s positions=%s total=%s", account_id, len(result.get("positions", []) or []), result.get("total_amount_portfolio"))
    return result


def _sandbox_operations(self, account_id, limit=1000):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=3650)
    payload = {
        "accountId": str(account_id),
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
        "limit": max(1, min(int(limit), 1000)),
        "withoutCommissions": False,
        "withoutTrades": False,
        "withoutOvernights": False,
    }
    result = self._rest_request("SandboxService/GetSandboxOperationsByCursor", payload)
    _adapter.logger.info("[SANDBOX OPERATIONS REST] account_id=%s items=%s", account_id, len(result.get("items", []) or []))
    return result


def _list_instruments(self, kind="SHARE", trade=True):
    key = str(kind).upper()
    method_map = {"SHARE": "Shares", "BOND": "Bonds", "ETF": "Etfs", "CURRENCY": "Currencies", "FUTURES": "Futures"}
    method_name = method_map.get(key)
    if method_name is None:
        raise ValueError(f"Unsupported instrument kind: {kind}")
    request = {"instrumentStatus": "INSTRUMENT_STATUS_BASE" if trade else "INSTRUMENT_STATUS_ALL", "instrumentExchange": "INSTRUMENT_EXCHANGE_UNSPECIFIED"}
    data = self._rest_request(f"InstrumentsService/{method_name}", request)
    _adapter.logger.info("[INSTRUMENTS REST] kind=%s method=%s count=%s", key, method_name, len(data.get("instruments", []) or []))
    return data


def _last_prices(self, ids):
    return self._rest_request("MarketDataService/GetLastPrices", {"instrumentId": [str(value) for value in ids], "lastPriceType": "LAST_PRICE_UNSPECIFIED"})


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
_adapter.AdapterState.list_instruments = _list_instruments
_adapter.AdapterState.last_prices = _last_prices
_adapter.AdapterState.close_prices = _close_prices
_adapter.AdapterState.trading_status = _trading_status
_adapter.AdapterState.trading_statuses = _trading_statuses


if __name__ == "__main__":
    _adapter.main()
