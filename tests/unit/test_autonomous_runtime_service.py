import time
from types import SimpleNamespace

import pytest

from edward.services.autonomous_run_state_service import AutonomousRunMode, AutonomousRunStateService
from edward.services.autonomous_runtime_service import AutonomousRuntimeConfig, AutonomousRuntimeService


def _wait_for(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def test_requires_autonomous_mode_before_start():
    runtime = AutonomousRuntimeService(lambda: None)
    with pytest.raises(ValueError, match="AUTONOMOUS_MODE_REQUIRED"):
        runtime.start()


def test_repeated_cycles_run_until_stopped():
    calls = []
    state = AutonomousRunStateService()
    state.set_mode(AutonomousRunMode.AUTONOMOUS)
    runtime = AutonomousRuntimeService(
        lambda: calls.append(1),
        state_service=state,
        config=AutonomousRuntimeConfig(interval_seconds=0.02),
    )

    runtime.start()
    _wait_for(lambda: len(calls) >= 2)
    runtime.stop()

    assert len(calls) >= 2
    assert runtime.state.snapshot().status == "STOPPED"
    assert runtime.state.snapshot().enabled is False


def test_pause_prevents_next_cycle_and_start_resumes():
    calls = []
    state = AutonomousRunStateService()
    state.set_mode(AutonomousRunMode.AUTONOMOUS)
    runtime = AutonomousRuntimeService(
        lambda: calls.append(time.monotonic()),
        state_service=state,
        config=AutonomousRuntimeConfig(interval_seconds=0.1),
    )

    runtime.start()
    _wait_for(lambda: len(calls) >= 1)
    runtime.pause()
    paused_count = len(calls)
    time.sleep(0.15)
    assert len(calls) == paused_count
    assert runtime.state.snapshot().status == "PAUSED"

    runtime.start()
    _wait_for(lambda: len(calls) > paused_count)
    runtime.stop()


def test_cycle_error_stops_autonomous_runtime():
    state = AutonomousRunStateService()
    state.set_mode(AutonomousRunMode.AUTONOMOUS)

    runtime = AutonomousRuntimeService(
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        state_service=state,
        config=AutonomousRuntimeConfig(interval_seconds=0.01),
    )
    runtime.start()
    _wait_for(lambda: runtime.state.snapshot().status == "ERROR")

    assert runtime.state.snapshot().enabled is False
    runtime.stop()


def test_long_cycle_exposes_elapsed_progress():
    state = AutonomousRunStateService()
    state.set_mode(AutonomousRunMode.AUTONOMOUS)
    release = False

    def long_cycle():
        nonlocal release
        while not release:
            time.sleep(0.02)

    runtime = AutonomousRuntimeService(
        long_cycle,
        state_service=state,
        config=AutonomousRuntimeConfig(interval_seconds=60),
    )

    runtime.start()
    _wait_for(lambda: state.snapshot().status == "EXECUTING")
    time.sleep(1.1)
    snapshot = state.snapshot()
    release = True
    runtime.stop()

    assert snapshot.status == "EXECUTING"
    assert "прошло" in snapshot.message
    assert "сек." in snapshot.message


def test_completed_facade_result_is_published_before_waiting():
    state = AutonomousRunStateService()
    state.set_mode(AutonomousRunMode.AUTONOMOUS)
    result = SimpleNamespace(control=SimpleNamespace(executed=True, reason="COMPLETED"))
    runtime = AutonomousRuntimeService(
        lambda: result,
        state_service=state,
        config=AutonomousRuntimeConfig(interval_seconds=60),
    )

    runtime.start()
    _wait_for(lambda: state.snapshot().status == "WAITING")
    snapshot = state.snapshot()
    runtime.stop()

    assert "Последний цикл выполнен: COMPLETED." in snapshot.message
    assert "Следующий анализ через" in snapshot.message


def test_rejected_cycle_remains_enabled_and_exposes_reason():
    state = AutonomousRunStateService()
    state.set_mode(AutonomousRunMode.AUTONOMOUS)
    result = SimpleNamespace(control=SimpleNamespace(executed=False, reason="PREFLIGHT_REJECTED:LIMIT"))
    runtime = AutonomousRuntimeService(
        lambda: result,
        state_service=state,
        config=AutonomousRuntimeConfig(interval_seconds=60),
    )

    runtime.start()
    _wait_for(lambda: state.snapshot().status == "WAITING")
    snapshot = state.snapshot()
    runtime.stop()

    assert snapshot.enabled is True
    assert "Последний цикл не выполнен: PREFLIGHT_REJECTED:LIMIT." in snapshot.message


def test_interval_must_be_positive():
    with pytest.raises(ValueError, match="AUTONOMOUS_INTERVAL_MUST_BE_POSITIVE"):
        AutonomousRuntimeConfig(interval_seconds=0)
