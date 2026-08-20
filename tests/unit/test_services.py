from decimal import Decimal
from types import SimpleNamespace

from edward.services.account_context import AccountContext
from edward.services.account_service import AccountService
from edward.services.balance_service import BalanceService
from edward.services.market_service import MarketService


class FakeAccountsApi:
    def __init__(self, response):
        self.response = response

    def get_accounts(self):
        return self.response


class FakePortfolioApi:
    def __init__(self, positions, portfolio=None):
        self.positions = positions
        self.portfolio = portfolio

    def get_positions(self, account_id):
        return self.positions

    def get_portfolio(self, account_id):
        return self.portfolio


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


def test_account_context_switches_active_account():
    context = AccountContext()
    first = {"id": "A1", "name": "First", "status": "OPEN"}
    second = {"id": "A2", "name": "Second", "status": "OPEN"}
    context.set_active(first)
    assert context.active_account_id == "A1"
    context.set_active(second)
    assert context.active_account_id == "A2"
    assert context.require_account_id() == "A2"


def test_account_service_accepts_numeric_open_status():
    response = {"accounts": [{"id": "A1", "status": "2"}, {"id": "A2", "status": "CLOSED"}]}
    service = AccountService(FakeAccountsApi(response))
    assert [account["id"] for account in service.get_open_accounts()] == ["A1"]


def test_balance_service_extracts_money_and_security_positions():
    response = SimpleNamespace(money=["RUB"], securities=["SBER"])
    service = BalanceService(FakePortfolioApi(response))
    result = service.get_positions("A1")
    assert service.get_money_positions(result) == ["RUB"]
    assert service.get_security_positions(result) == ["SBER"]


def test_balance_service_builds_financial_summary_from_adapter_response():
    positions = {
        "money": [{"currency": "rub", "available": {"units": "100000", "nano": 500000000}, "blocked": {"units": "1000", "nano": 0}}],
        "securities": [{"currency": "rub", "quantity": {"units": "10", "nano": 0}, "current_price": {"units": "5000", "nano": 0}}],
    }
    portfolio = {"total_amount_portfolio": {"units": "151000", "nano": 500000000}}
    summary = BalanceService.build_summary(positions, portfolio)
    assert summary.currency == "RUB"
    assert summary.available == Decimal("100000.5")
    assert summary.blocked == Decimal("1000")
    assert summary.cash == Decimal("101000.5")
    assert summary.securities == Decimal("50000")
    assert summary.portfolio_value == Decimal("151000.5")


def test_balance_service_falls_back_to_positions_when_portfolio_value_missing():
    positions = {"money": [{"currency": "rub", "available": {"units": "100000", "nano": 0}, "blocked": {"units": "0", "nano": 0}}], "securities": []}
    summary = BalanceService.build_summary(positions)
    assert summary.portfolio_value == Decimal("100000")


def test_market_service_checks_api_trade_flag():
    assert MarketService.is_api_trade_available(SimpleNamespace(api_trade_available_flag=True))
    assert not MarketService.is_api_trade_available(SimpleNamespace(api_trade_available_flag=False))
