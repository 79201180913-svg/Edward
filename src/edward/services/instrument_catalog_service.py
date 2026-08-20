from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InstrumentCatalogService:
    client: Any

    def list(self, instrument_kind: str = 'SHARE', trade_available_only: bool = True) -> list[Any]:
        response = self.client.list_instruments(instrument_kind=instrument_kind, trade_available_only=trade_available_only)
        return self._enrich(self._as_list(response, 'instruments'), instrument_kind)

    def search(self, query: str, instrument_kind: str = 'SHARE', trade_available_only: bool = True) -> list[Any]:
        query = query.strip().casefold(); instruments = self.list(instrument_kind, trade_available_only)
        if not query: return instruments
        names = ('ticker','name','uid','instrument_uid','figi','isin')
        return [i for i in instruments if any(query in str(_field(i, n, '')).casefold() for n in names)]

    def trading_status(self, instrument_uid: str) -> Any: return self.client.get_trading_status(instrument_uid)

    def _enrich(self, instruments: list[Any], kind: str) -> list[Any]:
        ids = [_uid(i) for i in instruments if _uid(i)]
        prices = _index(self.client.get_last_prices(ids), 'last_prices') if ids else {}
        statuses = {}
        if ids:
            try: statuses = _index(self.client.get_trading_statuses(ids), 'trading_statuses')
            except Exception: pass
        result=[]
        for instrument in instruments:
            item=dict(instrument) if isinstance(instrument, dict) else instrument; uid=_uid(instrument); price=prices.get(uid); status=statuses.get(uid)
            if isinstance(item, dict):
                item['instrument_kind']=kind; item['last_price']=_field(price,'price',_field(price,'last_price','')); item['buy_available']=_field(instrument,'buy_available_flag',False); item['sell_available']=_field(instrument,'sell_available_flag',False); item['api_trade_available']=_field(status,'api_trade_available_flag',_field(instrument,'api_trade_available_flag',False)); item['trading_status']=_field(status,'trading_status',_field(status,'status','')); item['limit_order_available']=_field(status,'limit_order_available_flag',False); item['market_order_available']=_field(status,'market_order_available_flag',False); item['min_price_increment']=_field(instrument,'min_price_increment',_field(instrument,'min_price_increment_value',''))
            result.append(item)
        return result

    @staticmethod
    def _as_list(response: Any, name: str) -> list[Any]:
        if isinstance(response, list): return response
        value = response.get(name, []) if isinstance(response, dict) else []
        return list(value or [])


def _field(value: Any, name: str, default: Any = None) -> Any: return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)
def _uid(value: Any) -> str: return str(_field(value, 'uid', _field(value, 'instrument_uid', '')))
def _index(response: Any, name: str) -> dict[str, Any]:
    items=response if isinstance(response,list) else _field(response,name,[]) or []
    return {uid:item for item in items if (uid:=_uid(item))}
