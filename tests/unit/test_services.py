from types import SimpleNamespace

from edward.services.account_service import AccountService
from edward.services.balance_service import BalanceService
from edward.services.market_service import MarketService


class FakeAccountsApi:
    def __init__(self, response):
        self.response = response

    def get_accounts(self):
        return self.response


class FakePortfolioApi:
    def __init__(self, positions):
        self.positions = positions

    def get_positions(self, account_id):
        return self.positions


def test_select_account_returns_requested_account():
    account = SimpleNamespace(id="A1")
    response = SimpleNamespace(accounts=[account])

    service = AccountService(FakeAccountsApi(response))

    assert service.select_account(response, "A1") is account


def test_select_account_raises_for_unknown_account():
    response = SimpleNamespace(accounts=[])
    service = AccountService(FakeAccountsApi(response))

    try:
        service.select_account(response, "UNKNOWN")
    except ValueError as exc:
        assert str(exc) == "Account not found: UNKNOWN"
    else:
        raise AssertionError("ValueError was not raised")


def test_balance_service_extracts_money_and_security_positions():
    response = SimpleNamespace(money=["RUB"], securities=["SBER"])
    service = BalanceService(FakePortfolioApi(response))

    result = service.get_positions("A1")

    assert service.get_money_positions(result) == ["RUB"]
    assert service.get_security_positions(result) == ["SBER"]


def test_market_service_checks_api_trade_flag():
    assert MarketService.is_api_trade_available(
        SimpleNamespace(api_trade_available_flag=True)
    )
    assert not MarketService.is_api_trade_available(
        SimpleNamespace(api_trade_available_flag=False)
    )
