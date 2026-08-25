from decimal import Decimal

from edward.domain.execution import ExecutionDecision, ExecutionRequest
from edward.services.live_pretrade_validator_v06 import LivePreTradeValidator


class FakeClient:
    def __init__(self):
        self.accounts = [{"id": "acc-1", "status": "OPEN"}]
        self.instrument = {"instrument_uid": "uid-1", "min_price_increment": {"units": "0", "nano": 10000000}}
        self.price = {"last_prices": [{"instrument_uid": "uid-1", "price": {"units": "10", "nano": 0}}]}
        self.status = {"api_trade_available": True, "market_order_available": True, "limit_order_available": True}
        self.positions = {"securities": [{"instrument_uid": "uid-1", "balance": "100"}]}
        self.portfolio = {"available_cash": {"units": "10000", "nano": 0}}
        self.max_lots = {"max_lots": 100}

    def get_accounts(self): return {"accounts": self.accounts}
    def get_instrument(self, instrument_uid): return self.instrument
    def get_last_prices(self, instrument_ids): return self.price
    def get_trading_status(self, instrument_id): return self.status
    def get_positions(self, account_id): return self.positions
    def get_portfolio(self, account_id): return self.portfolio
    def get_max_lots(self, account_id, instrument_id, price): return self.max_lots


def request(decision=ExecutionDecision.BUY, quantity=10, order_type="MARKET", entry_price=None):
    return ExecutionRequest(
        execution_id="ex-1",
        account_id="acc-1",
        instrument_uid="uid-1",
        ticker="TEST",
        decision=decision,
        side="BUY" if decision in {ExecutionDecision.BUY, ExecutionDecision.ADD} else "SELL",
        quantity=Decimal(str(quantity)),
        order_type=order_type,
        entry_price=Decimal(str(entry_price)) if entry_price is not None else None,
        execution_ready=True,
    )


def test_live_pretrade_validator_accepts_ready_buy():
    passed, reasons = LivePreTradeValidator(FakeClient()).validate(request())
    assert passed is True
    assert reasons == ()


def test_blocks_when_account_is_not_available():
    client = FakeClient(); client.accounts = []
    passed, reasons = LivePreTradeValidator(client).validate(request())
    assert passed is False
    assert "ACCOUNT_NOT_AVAILABLE" in reasons


def test_blocks_when_trading_status_is_closed():
    client = FakeClient(); client.status = {"api_trade_available": False, "status": "NOT_AVAILABLE_FOR_TRADING"}
    passed, reasons = LivePreTradeValidator(client).validate(request())
    assert passed is False
    assert "TRADING_STATUS_NOT_OK" in reasons


def test_blocks_when_live_price_is_missing():
    client = FakeClient(); client.price = {"last_prices": []}
    passed, reasons = LivePreTradeValidator(client).validate(request())
    assert passed is False
    assert "LIVE_PRICE_UNAVAILABLE" in reasons


def test_blocks_buy_when_cash_is_insufficient():
    client = FakeClient(); client.portfolio = {"available_cash": "5"}
    passed, reasons = LivePreTradeValidator(client).validate(request(quantity=1))
    assert passed is False
    assert "INSUFFICIENT_CASH" in reasons


def test_blocks_sell_when_position_is_insufficient():
    client = FakeClient(); client.positions = {"securities": [{"instrument_uid": "uid-1", "balance": "2"}]}
    passed, reasons = LivePreTradeValidator(client).validate(request(decision=ExecutionDecision.SELL, quantity=3))
    assert passed is False
    assert "INSUFFICIENT_POSITION" in reasons


def test_blocks_limit_price_on_wrong_step():
    passed, reasons = LivePreTradeValidator(FakeClient()).validate(request(order_type="LIMIT", entry_price="10.005"))
    assert passed is False
    assert "INVALID_PRICE_STEP" in reasons


def test_blocks_when_max_lots_are_insufficient():
    client = FakeClient(); client.max_lots = {"max_lots": 3}
    passed, reasons = LivePreTradeValidator(client).validate(request(quantity=10))
    assert passed is False
    assert "INSUFFICIENT_MAX_LOTS" in reasons
