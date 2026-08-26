from decimal import Decimal
from types import SimpleNamespace

from edward.services.autonomous_protection_service import AutonomousProtectionService
from edward.services.protection_reconciliation_service import ProtectionReconciliationService


class StopGateway:
    def __init__(self):
        self.stops = []
        self.created = []

    def get_stop_orders(self, account_id):
        return list(self.stops)

    def post_stop_order(self, account_id, payload):
        order = {**payload, "id": "stop-1", "status": "ACTIVE"}
        self.created.append(order)
        self.stops.append(order)
        return order


def test_buy_fill_protection_then_reconciliation():
    gateway = StopGateway()
    protection = AutonomousProtectionService(gateway)
    result = SimpleNamespace(decision="BUY", instrument_uid="uid", trade_plan=SimpleNamespace(stop_price=Decimal("95")))

    protected = protection.protect_fill(account_id="ACC", instrument_uid="uid", quantity=10, result=result)

    assert protected.protected is True
    assert protected.status == "PROTECTED"
    assert protected.stop_order_id == "stop-1"
    assert gateway.created[0]["quantity"] == 10

    reconciliation = ProtectionReconciliationService(gateway).reconcile(
        account_id="ACC",
        positions=[{"instrument_uid": "uid", "quantity": 10}],
    )
    assert reconciliation.protected is True
    assert reconciliation.status == "PROTECTED"
