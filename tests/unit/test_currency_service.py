from decimal import Decimal

from edward.services.currency_service import CurrencyService


class Client:
    def find_instrument(self, query, trade_available_only=False):
        return {'instruments': [{'uid': 'USD_UID'}]}
    def get_last_prices(self, ids):
        return {'last_prices': [{'price': {'units': '100', 'nano': 0}}]}


def test_currency_conversion_rub_usd():
    service = CurrencyService(Client())
    assert service.convert(Decimal('1000'), 'RUB', 'USD') == Decimal('10')
    assert service.convert(Decimal('10'), 'USD', 'RUB') == Decimal('1000')
