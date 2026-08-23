from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
import logging


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InstrumentCatalogService:
    client: Any

    def list(self, instrument_kind: str = "SHARE", trade_available_only: bool = True) -> list[Any]:
        response = self.client.list_instruments(
            instrument_kind=instrument_kind,
            trade_available_only=trade_available_only,
        )
        instruments = self._as_list(response, "instruments")
        logger.info("[PRICE DEBUG] Catalog loaded: kind=%s instruments=%d", instrument_kind, len(instruments))
        return self._enrich(instruments, instrument_kind)

    def search(self, query: str, instrument_kind: str = "SHARE", trade_available_only: bool = True) -> list[Any]:
        query = query.strip().casefold()
        instruments = self.list(instrument_kind, trade_available_only)
        if not query:
            return instruments
        names = ("ticker", "name", "uid", "instrument_uid", "figi", "isin")
        return [
            instrument
            for instrument in instruments
            if any(query in str(_field(instrument, name, "")).casefold() for name in names)
        ]

    def trading_status(self, instrument_uid: str) -> Any:
        return self.client.get_trading_status(instrument_uid)

    def _enrich(self, instruments: list[Any], kind: str) -> list[Any]:
        ids = [_uid(instrument) for instrument in instruments if _uid(instrument)]
        logger.info("[PRICE DEBUG] Requesting market prices: kind=%s ids=%d", kind, len(ids))
        logger.info("[PRICE DEBUG] First UIDs: %s", ids[:5])
        prices_response = self.client.get_last_prices(ids) if ids else {}
        prices = _index(prices_response, "last_prices") if ids else {}
        logger.info(
            "[PRICE DEBUG] MarketData response: type=%s prices=%d raw_keys=%s",
            type(prices_response).__name__,
            len(prices),
            list(prices_response.keys()) if isinstance(prices_response, dict) else "not-dict",
        )
        if ids and not prices:
            logger.warning("[PRICE DEBUG] NO PRICES MATCHED. Raw response: %r", prices_response)

        statuses = {}
        if ids:
            try:
                statuses = _index(self.client.get_trading_statuses(ids), "trading_statuses")
            except Exception as exc:
                logger.warning("[PRICE DEBUG] Trading statuses failed: %s", exc)

        result = []
        missing_price = 0
        for instrument in instruments:
            item = dict(instrument) if isinstance(instrument, dict) else instrument
            uid = _uid(instrument)
            price_item = prices.get(uid)
            status = statuses.get(uid)
            raw_price = _field(price_item, "price", _field(price_item, "last_price", ""))
            normalized_price = _quotation_to_string(raw_price)

            api_available = _bool_flag(
                status,
                "api_trade_available_flag",
                _field(instrument, "api_trade_available_flag", False),
            )
            limit_available = _bool_flag(status, "limit_order_available_flag", False)
            market_available = _bool_flag(status, "market_order_available_flag", False)
            bestprice_available = _bool_flag(status, "bestprice_order_available_flag", False)
            trading_status = _field(status, "trading_status", _field(status, "status", ""))

            # api_trade_available_flag means that API access exists for the
            # instrument; it does not mean that an order can be submitted now.
            # The UI flag must represent actual current order availability.
            trading_status_text = str(trading_status or "").upper()
            status_allows_trading = trading_status_text not in {
                "SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING",
                "NOT_AVAILABLE_FOR_TRADING",
            }
            trade_available = bool(
                api_available
                and status_allows_trading
                and (limit_available or market_available or bestprice_available)
            )

            fields = {
                "instrument_kind": kind,
                "last_price": normalized_price,
                "buy_available": _field(instrument, "buy_available_flag", False),
                "sell_available": _field(instrument, "sell_available_flag", False),
                "api_trade_available": api_available,
                "trading_available": trade_available,
                "trading_status": trading_status,
                "limit_order_available": limit_available,
                "market_order_available": market_available,
                "bestprice_order_available": bestprice_available,
                "min_price_increment": _field(
                    instrument,
                    "min_price_increment",
                    _field(instrument, "min_price_increment_value", ""),
                ),
            }

            if isinstance(item, dict):
                item.update(fields)
            else:
                # T-Invest protobuf responses and test doubles are object-shaped,
                # while REST responses are dict-shaped. Preserve object identity
                # and expose the same enriched contract for mutable objects.
                for name, value in fields.items():
                    try:
                        setattr(item, name, value)
                    except (AttributeError, TypeError):
                        logger.warning(
                            "[PRICE DEBUG] Cannot enrich object field: type=%s field=%s",
                            type(item).__name__,
                            name,
                        )

            if not normalized_price:
                missing_price += 1
                if missing_price <= 10:
                    logger.warning(
                        "[PRICE DEBUG] Missing price: ticker=%s uid=%s price_item=%r",
                        _field(instrument, "ticker", ""), uid, price_item,
                    )
            elif len(result) < 5:
                logger.info(
                    "[PRICE DEBUG] Price matched: ticker=%s uid=%s raw=%r normalized=%s",
                    _field(instrument, "ticker", ""), uid, raw_price, normalized_price,
                )

            logger.debug(
                "[TRADING AVAILABILITY] ticker=%s uid=%s api=%s limit=%s market=%s bestprice=%s status=%s available=%s",
                _field(instrument, "ticker", ""),
                uid,
                api_available,
                limit_available,
                market_available,
                bestprice_available,
                trading_status,
                trade_available,
            )
            result.append(item)

        logger.info(
            "[PRICE DEBUG] Price enrichment finished: instruments=%d prices=%d missing=%d",
            len(instruments), len(prices), missing_price,
        )
        return result

    @staticmethod
    def _as_list(response: Any, name: str) -> list[Any]:
        if isinstance(response, list):
            return response
        value = response.get(name, []) if isinstance(response, dict) else []
        return list(value or [])


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _bool_flag(value: Any, name: str, default: Any = False) -> bool:
    raw = _field(value, name, None)
    if raw is None:
        camel = {
            "api_trade_available_flag": "apiTradeAvailableFlag",
            "limit_order_available_flag": "limitOrderAvailableFlag",
            "market_order_available_flag": "marketOrderAvailableFlag",
            "bestprice_order_available_flag": "bestpriceOrderAvailableFlag",
        }.get(name)
        if camel:
            raw = _field(value, camel, None)
    if raw is None:
        raw = default
    if isinstance(raw, str):
        return raw.strip().casefold() in {"true", "1", "yes", "да"}
    return bool(raw)


def _uid(value: Any) -> str:
    return str(_field(value, "uid", _field(value, "instrument_uid", "")))


def _index(response: Any, name: str) -> dict[str, Any]:
    items = response if isinstance(response, list) else _field(response, name, []) or []
    return {uid: item for item in items if (uid := _uid(item))}


def _quotation_to_string(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        try:
            units = Decimal(str(value.get("units", 0)))
            nano = Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
            return format(units + nano, "f")
        except Exception:
            return str(value)
    units = getattr(value, "units", None)
    nano = getattr(value, "nano", None)
    if units is not None or nano is not None:
        try:
            return format(Decimal(str(units or 0)) + Decimal(str(nano or 0)) / Decimal("1000000000"), "f")
        except Exception:
            return str(value)
    return str(value)
