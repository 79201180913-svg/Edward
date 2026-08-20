from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

@dataclass(slots=True)
class CurrencyService:
    client: Any
    _rates: dict[tuple[str, str], Decimal] = field(default_factory=lambda: {('RUB','RUB'): Decimal('1'), ('USD','USD'): Decimal('1')}, init=False)
    def convert(self, amount: Decimal | int | float, source: str, target: str) -> Decimal:
        source, target = source.upper(), target.upper(); amount = Decimal(str(amount))
        if source == target: return amount
        rate = self._load_usd_rub()
        if source == 'USD' and target == 'RUB': return amount * rate
        if source == 'RUB' and target == 'USD': return amount / rate
        raise ValueError(f'Unsupported currency conversion: {source}->{target}')
    def _load_usd_rub(self) -> Decimal:
        cached = self._rates.get(('USD','RUB'))
        if cached: return cached
        for query in ('USD/RUB','USD000UTSTOM','USD000UTS'):
            try:
                response = self.client.find_instrument(query, trade_available_only=False); items = response.get('instruments', []) if isinstance(response, dict) else []
                for item in items:
                    uid = item.get('uid', item.get('instrument_uid', '')) if isinstance(item, dict) else getattr(item, 'uid', '')
                    if not uid: continue
                    prices = self.client.get_last_prices([str(uid)]); last = prices.get('last_prices', []) if isinstance(prices, dict) else []
                    if not last: continue
                    price = last[0].get('price') if isinstance(last[0], dict) else getattr(last[0], 'price', None); value = self._decimal(price)
                    if value > 0: self._rates[('USD','RUB')] = value; return value
            except Exception: continue
        raise RuntimeError('Курс USD/RUB недоступен через T-Invest API')
    @staticmethod
    def _decimal(value: Any) -> Decimal:
        if value is None: return Decimal('0')
        if isinstance(value, dict) and ('units' in value or 'nano' in value): return Decimal(str(value.get('units',0))) + Decimal(str(value.get('nano',0))) / Decimal('1000000000')
        try: return Decimal(str(value))
        except Exception: return Decimal('0')
