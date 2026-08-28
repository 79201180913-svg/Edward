from edward.services.protection_reconciliation_service import ProtectionReconciliationService


class Gateway:
    def __init__(self, stops):
        self.stops = stops

    def get_active(self, account_id):
        return self.stops


def test_reconciliation_accepts_matching_protection():
    service = ProtectionReconciliationService(Gateway([
        {"instrument_uid": "uid", "quantity": 10, "status": "ACTIVE"},
    ]))
    result = service.reconcile(account_id="ACC", positions=[{"instrument_uid": "uid", "quantity": 10}])
    assert result.status == "PROTECTED"
    assert result.protected is True
    assert result.reasons == ()


def test_reconciliation_detects_missing_protection():
    service = ProtectionReconciliationService(Gateway([]))
    result = service.reconcile(account_id="ACC", positions=[{"instrument_uid": "uid", "quantity": 10}])
    assert result.status == "RECONCILIATION_ERROR"
    assert result.protected is False
    assert result.reasons == ("PROTECTION_REQUIRED:uid",)


def test_reconciliation_detects_quantity_mismatch():
    service = ProtectionReconciliationService(Gateway([
        {"instrument_uid": "uid", "quantity": 5, "status": "ACTIVE"},
    ]))
    result = service.reconcile(account_id="ACC", positions=[{"instrument_uid": "uid", "quantity": 10}])
    assert result.reasons == ("PROTECTION_MISMATCH:uid:position=10:stop=5",)


def test_reconciliation_detects_orphan_protection():
    service = ProtectionReconciliationService(Gateway([
        {"instrument_uid": "orphan", "quantity": 10, "status": "ACTIVE"},
    ]))
    result = service.reconcile(account_id="ACC", positions=[])
    assert result.reasons == ("ORPHAN_PROTECTION:orphan",)
