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


_load_local_env()


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
        if not certs:
            return
        pem_path = Path(tempfile.gettempdir()) / "edward_windows_ca_bundle.pem"
        pem_path.write_bytes(b"".join(
            ssl.DER_cert_to_PEM_cert(cert_der).encode("ascii") for cert_der in certs
        ))
        os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = str(pem_path)
    except Exception:
        return


_configure_windows_ca_bundle()

import tinvest_adapter as _adapter
from stop_order_adapter_patch import install as install_stop_order_adapter_patch


LAST_PRICES_BATCH_SIZE = 50
LAST_PRICES_RETRIES = 2
LAST_PRICES_RETRY_DELAY_SECONDS = 0.5


def _last_prices(self, ids):
    values = [str(value) for value in ids]
    if not values:
        return {"last_prices": []}

    chunks = [values[index:index + LAST_PRICES_BATCH_SIZE] for index in range(0, len(values), LAST_PRICES_BATCH_SIZE)]
    merged: dict[str, object] = {"last_prices": []}

    for chunk in chunks:
        last_error: Exception | None = None
        for attempt in range(LAST_PRICES_RETRIES + 1):
            try:
                response = self._rest_request(
                    "MarketDataService/GetLastPrices",
                    {"instrumentId": chunk, "lastPriceType": "LAST_PRICE_UNSPECIFIED"},
                )
                if isinstance(response, dict):
                    for key, value in response.items():
                        if key == "last_prices" and isinstance(value, list):
                            merged["last_prices"].extend(value)
                        elif key not in merged:
                            merged[key] = value
                break
            except RuntimeError as exc:
                last_error = exc
                if "HTTP 504" not in str(exc) or attempt >= LAST_PRICES_RETRIES:
                    raise
                time.sleep(LAST_PRICES_RETRY_DELAY_SECONDS * (attempt + 1))
        if last_error is not None and len(merged["last_prices"]) == 0 and len(chunks) == 1:
            raise last_error

    return merged


def _list_instruments(self, kind="SHARE", trade=True):
    key = str(kind).upper()
    method_map = {
        "SHARE": "Shares",
        "BOND": "Bonds",
        "ETF": "Etfs",
        "CURRENCY": "Currencies",
        "FUTURES": "Futures",
        "OPTION": "Options",
        "SP": "StructuredNotes",
        "DFA": "Dfas",
    }
    method_name = method_map.get(key)
    if method_name is None:
        raise ValueError(f"Unsupported instrument kind: {kind}")
    request = {"instrumentStatus": "INSTRUMENT_STATUS_BASE" if trade else "INSTRUMENT_STATUS_ALL", "instrumentExchange": "INSTRUMENT_EXCHANGE_UNSPECIFIED"}
    return self._rest_request(f"InstrumentsService/{method_name}", request)


def _close_prices(self, ids):
    return self._rest_request("MarketDataService/GetClosePrices", {"instruments": [{"instrumentId": str(value)} for value in ids], "instrumentStatus": "INSTRUMENT_STATUS_BASE"})


def _trading_status(self, instrument_id):
    return self._rest_request("MarketDataService/GetTradingStatus", {"instrumentId": str(instrument_id)})


def _trading_statuses(self, ids):
    return self._rest_request("MarketDataService/GetTradingStatuses", {"instrumentId": [str(value) for value in ids]})


_adapter.AdapterState.list_instruments = _list_instruments
_adapter.AdapterState.last_prices = _last_prices
_adapter.AdapterState.close_prices = _close_prices
_adapter.AdapterState.trading_status = _trading_status
_adapter.AdapterState.trading_statuses = _trading_statuses
install_stop_order_adapter_patch(_adapter)

if __name__ == "__main__":
    _adapter.main()
