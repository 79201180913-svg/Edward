from types import SimpleNamespace

from edward.services.autonomous_protection_service import AutonomousProtectionService
from edward.services.stop_order_service import StopOrderService


class Gateway:
    def __init__(self):
        self.created = []
        self.active = []

    def post_stop_order(self, request):
        self.created.append(request)
        self.active.append({"stop_order_id": f"stop-{len(self.created)}", "instrument_uid": request["instrument_id"], "status": "ACTIVE"})
        return {"stop_order_id": self.active[-1]["stop_order_id"]}

    def get_stop_orders(self, account_id): return list(self.active)
    def cancel_stop_order(self, account_id, stop_order_id): return None


class MissingAfterCreateGateway(Gateway):
    def post_stop_order(self, request):
        self.created.append(request)
        return {"stop_order_id": "stop-not-visible"}


def buy_result(stop_price=95):
    return SimpleNamespace(decision="BUY", instrument_uid="uid", trade_plan=SimpleNamespace(stop_price=stop_price))


def test_buy_fill_creates_and_verifies_stop_loss():
    gateway = Gateway(); service = AutonomousProtectionService(StopOrderService(gateway))
    protected = service.protect_fill(account_id="ACC", instrument_uid="uid", quantity=10, result=buy_result())
    assert protected.protected is True
    assert protected.status == "PROTECTED"
    assert protected.stop_order_id == "stop-1"
    assert gateway.created[0]["quantity"] == 10


def test_buy_fill_without_stop_price_is_blocked():
    service = AutonomousProtectionService(StopOrderService(Gateway()))
    protected = service.protect_fill(account_id="ACC", instrument_uid="uid", quantity=10, result=buy_result(None))
    assert protected.protected is False
    assert protected.reason == "PROTECTION_STOP_PRICE_MISSING"


def test_reduce_does_not_create_new_protection():
    gateway = Gateway(); service = AutonomousProtectionService(StopOrderService(gateway))
    result = SimpleNamespace(decision="REDUCE", instrument_uid="uid")
    protected = service.protect_fill(account_id="ACC", instrument_uid="uid", quantity=10, result=result)
    assert protected.protected is True
    assert protected.status == "NOT_REQUIRED"
    assert gateway.created == []


def test_existing_active_stop_is_reused_without_duplicate_creation():
    gateway = Gateway(); gateway.active = [{"stop_order_id": "existing", "instrument_uid": "uid", "status": "ACTIVE"}]
    service = AutonomousProtectionService(StopOrderService(gateway))
    protected = service.protect_fill(account_id="ACC", instrument_uid="uid", quantity=10, result=buy_result())
    assert protected.protected is True
    assert protected.stop_order_id == "existing"
    assert gateway.created == []


def test_stop_loss_creation_is_not_accepted_without_post_create_verification():
    gateway = MissingAfterCreateGateway(); service = AutonomousProtectionService(StopOrderService(gateway))
    protected = service.protect_fill(account_id="ACC", instrument_uid="uid", quantity=10, result=buy_result())
    assert protected.protected is False
    assert protected.status == "STOPPED"
    assert protected.reason == "PROTECTION_NOT_VERIFIED"
