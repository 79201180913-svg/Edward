from decimal import Decimal

from edward.domain.execution import ExecutionDecision, ExecutionRequest, ExecutionStatus
from edward.services.execution_center_controller_v06 import ExecutionCenterController
from edward.services.execution_confirmation_service import ControlledExecutionService
from edward.services.execution_engine import ExecutionEngine
from edward.services.live_pretrade_validator_v06 import LivePreTradeValidator
from edward.services.tinvest_execution_adapter import TInvestExecutionAdapter


class FakeSandboxClient:
    def __init__(self):
        self.accounts = [{"id": "acc-1", "status": "OPEN"}]
        self.instrument = {"instrument_uid": "uid-1", "min_price_increment": {"units": "0", "nano": 10000000}}
        self.price = {"last_prices": [{"instrument_uid": "uid-1", "price": {"units": "10", "nano": 0}}]}
        self.status = {"api_trade_available": True, "market_order_available": True, "limit_order_available": True}
        self.positions = {"securities": []}
        self.portfolio = {"available_cash": {"units": "10000", "nano": 0}}
        self.max_lots = {"max_lots": 100}
        self.submitted = []
        self.state = {}

    def get_accounts(self): return {"accounts": self.accounts}
    def get_instrument(self, instrument_uid): return self.instrument
    def get_last_prices(self, instrument_ids): return self.price
    def get_trading_status(self, instrument_id): return self.status
    def get_positions(self, account_id): return self.positions
    def get_portfolio(self, account_id): return self.portfolio
    def get_max_lots(self, account_id, instrument_id, price): return self.max_lots

    def post_order(self, request):
        self.submitted.append(request)
        self.state[(request.account_id, "broker-1")] = {"status": "EXECUTION_REPORT_STATUS_NEW", "lots_executed": "0"}
        return {"order_id": "broker-1"}

    def get_order_state(self, account_id, order_id):
        return self.state[(account_id, order_id)]

    def cancel_order(self, account_id, order_id):
        self.state[(account_id, order_id)] = {"status": "EXECUTION_REPORT_STATUS_CANCELLED", "lots_executed": "0"}
        return {}


def request():
    return ExecutionRequest(
        execution_id="sandbox-e2e-1",
        account_id="acc-1",
        instrument_uid="uid-1",
        ticker="TEST",
        decision=ExecutionDecision.BUY,
        side="BUY",
        quantity=Decimal("10"),
        order_type="LIMIT",
        entry_price=Decimal("10"),
        execution_ready=True,
    )


def test_sandbox_confirmed_execution_path_submits_and_updates_journal():
    client = FakeSandboxClient()
    adapter = TInvestExecutionAdapter(client)
    engine = ExecutionEngine(adapter=adapter)
    validator = LivePreTradeValidator(client)
    controller = ExecutionCenterController(ControlledExecutionService(engine, validator))
    engine.event_callback = controller.accept_event

    controller.load_request(request())
    assert controller.prepare().status is ExecutionStatus.READY
    assert controller.request_confirmation().status is ExecutionStatus.WAITING_CONFIRMATION
    result = controller.confirm_and_submit()

    assert result.status is ExecutionStatus.SUBMITTED
    assert result.broker_order_id == "broker-1"
    assert client.submitted == [request()]
    assert controller.state.events
    assert any(event.status is ExecutionStatus.SUBMITTED for event in controller.state.events)


def test_sandbox_confirmation_is_blocked_when_live_validation_fails():
    client = FakeSandboxClient()
    client.status = {"api_trade_available": False, "status": "NOT_AVAILABLE_FOR_TRADING"}
    adapter = TInvestExecutionAdapter(client)
    engine = ExecutionEngine(adapter=adapter)
    controller = ExecutionCenterController(ControlledExecutionService(engine, LivePreTradeValidator(client)))

    controller.load_request(request())
    assert controller.prepare().status is ExecutionStatus.READY
    assert controller.request_confirmation().status is ExecutionStatus.WAITING_CONFIRMATION
    result = controller.confirm_and_submit()

    assert result.status is ExecutionStatus.BLOCKED
    assert client.submitted == []
