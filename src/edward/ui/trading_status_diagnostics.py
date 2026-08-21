from __future__ import annotations

from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient


_SENTINEL = "__edward_trading_status_diagnostics__"


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def install_trading_status_diagnostics() -> None:
    if getattr(TInvestAdapterClient, _SENTINEL, False):
        return

    original = TInvestAdapterClient.get_trading_status

    def normalized(self: TInvestAdapterClient, instrument_id: str) -> dict[str, Any]:
        raw = original(self, instrument_id)
        data = dict(raw) if isinstance(raw, dict) else {}

        aliases = {
            "api_trade_available_flag": ("api_trade_available", "apiTradeAvailableFlag"),
            "market_order_available_flag": ("market_order_available", "marketOrderAvailableFlag"),
            "limit_order_available_flag": ("limit_order_available", "limitOrderAvailableFlag"),
            "bestprice_order_available_flag": ("bestprice_order_available", "bestPriceOrderAvailableFlag"),
        }
        for canonical, variants in aliases.items():
            if data.get(canonical) is None:
                for variant in variants:
                    if data.get(variant) is not None:
                        data[canonical] = data[variant]
                        break

        print(
            "[TRADING STATUS] "
            f"instrument_id={instrument_id} "
            f"ticker={data.get('ticker')} "
            f"api={data.get('api_trade_available_flag')!r} "
            f"market={data.get('market_order_available_flag')!r} "
            f"limit={data.get('limit_order_available_flag')!r} "
            f"bestprice={data.get('bestprice_order_available_flag')!r} "
            f"trading_status={data.get('trading_status')!r} "
            f"raw={data}",
            flush=True,
        )
        return data

    TInvestAdapterClient.get_trading_status = normalized
    setattr(TInvestAdapterClient, _SENTINEL, True)
