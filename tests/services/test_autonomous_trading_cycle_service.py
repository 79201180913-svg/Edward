from __future__ import annotations

from dataclasses import dataclass

import pytest

from edward.services.autonomous_trading_cycle_service import AutonomousTradingCycleService


@dataclass(frozen=True)
class FakeState:
    available_cash: float = 1000.0


class FakeRefresh:
    def __init__(self, state: FakeState | None = None):
        self.state = state or FakeState()
        self.calls: list[str] = []

    def refresh(self, account_id: str):
        self.calls.append(account_id)
        return self.state


def make_service(refresh: FakeRefresh | None = None):
    refresh = refresh or FakeRefresh()
    marker = object()
    return AutonomousTradingCycleService(
        account_state_refresh=refresh,
        opportunity_search=marker,
        budget_planning=marker,
        reallocation=marker,
        execution_plan=marker,
        preflight=marker,
        execution=marker,
        sequence=marker,
        verification=marker,
        protection=marker,
        replanning=marker,
    ), refresh


def test_cycle_refreshes_live_state_before_analysis():
    service, refresh = make_service()

    result = service.run(cycle_id="C1", account_id="ACC")

    assert result.status == "ANALYSIS_READY"
    assert result.account_state is refresh.state
    assert refresh.calls == ["ACC"]


def test_cycle_accepts_explicit_state_provider():
    service, refresh = make_service()
    provided = FakeState(available_cash=2500.0)

    result = service.run(cycle_id="C1", account_id="ACC", state_provider=lambda: provided)

    assert result.account_state is provided
    assert refresh.calls == []


def test_cycle_requires_cycle_id():
    service, _ = make_service()

    with pytest.raises(ValueError, match="CYCLE_ID_REQUIRED"):
        service.run(cycle_id="", account_id="ACC")


def test_cycle_requires_account_id():
    service, _ = make_service()

    with pytest.raises(ValueError, match="ACCOUNT_ID_REQUIRED"):
        service.run(cycle_id="C1", account_id="")


def test_cycle_blocks_when_live_state_is_unavailable():
    refresh = FakeRefresh()
    refresh.state = None
    service, _ = make_service(refresh)

    result = service.run(cycle_id="C1", account_id="ACC")

    assert result.status == "BLOCKED"
    assert result.message == "ACCOUNT_STATE_UNAVAILABLE"


def test_cycle_does_not_bypass_execution_stage():
    service, _ = make_service()

    with pytest.raises(NotImplementedError, match="AUTONOMOUS_EXECUTION_STAGE_NOT_WIRED"):
        service.run(cycle_id="C1", account_id="ACC", execute=True)
