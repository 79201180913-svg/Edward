import time
from types import SimpleNamespace

import pytest

from edward.services.autonomous_run_state_service import AutonomousRunMode, AutonomousRunStateService
from edward.services.autonomous_runtime_service import AutonomousRuntimeConfig, AutonomousRuntimeService


def _wait_for(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(0.01)
    assert predicate()


def _runtime(cycle, interval=0.02):
    state = AutonomousRunStateService(); state.set_mode(AutonomousRunMode.AUTONOMOUS)
    return AutonomousRuntimeService(cycle, state_service=state, config=AutonomousRuntimeConfig(interval_seconds=interval))


def test_requires_autonomous_mode_before_start():
    with pytest.raises(ValueError, match="AUTONOMOUS_MODE_REQUIRED"):
        AutonomousRuntimeService(lambda: None).start()


def test_repeated_cycles_run_until_stopped():
    calls = []; runtime = _runtime(lambda: calls.append(1))
    runtime.start(); _wait_for(lambda: len(calls) >= 2); runtime.stop()
    assert len(calls) >= 2; assert runtime.state.snapshot().status == "STOPPED"; assert runtime.state.snapshot().enabled is False


def test_repeated_start_does_not_create_second_worker():
    calls = []; runtime = _runtime(lambda: calls.append(1), interval=0.2)
    runtime.start(); _wait_for(lambda: len(calls) >= 1); first_thread = runtime._thread
    runtime.start(); assert runtime._thread is first_thread
    runtime.stop()


def test_pause_prevents_next_cycle_and_start_resumes():
    calls = []; runtime = _runtime(lambda: calls.append(time.monotonic()), interval=0.1)
    runtime.start(); _wait_for(lambda: len(calls) >= 1); runtime.pause(); paused_count = len(calls)
    time.sleep(0.15); assert len(calls) == paused_count; assert runtime.state.snapshot().status == "PAUSED"
    runtime.start(); _wait_for(lambda: len(calls) > paused_count); runtime.stop()


def test_stop_prevents_future_cycles():
    calls = []; runtime = _runtime(lambda: calls.append(1), interval=0.05)
    runtime.start(); _wait_for(lambda: len(calls) >= 1); runtime.stop(); stopped = len(calls)
    time.sleep(0.1); assert len(calls) == stopped; assert runtime.state.snapshot().enabled is False


def test_cycle_error_stops_autonomous_runtime():
    runtime = _runtime(lambda: (_ for _ in ()).throw(RuntimeError("boom")), interval=0.01)
    runtime.start(); _wait_for(lambda: runtime.state.snapshot().status == "ERROR")
    assert runtime.state.snapshot().enabled is False; runtime.stop()


def test_long_cycle_exposes_elapsed_progress():
    state = AutonomousRunStateService(); state.set_mode(AutonomousRunMode.AUTONOMOUS); release = False
    def long_cycle():
        while not release: time.sleep(0.02)
    runtime = AutonomousRuntimeService(long_cycle, state_service=state, config=AutonomousRuntimeConfig(interval_seconds=60))
    runtime.start(); _wait_for(lambda: state.snapshot().status == "EXECUTING"); time.sleep(1.1); snapshot = state.snapshot(); release = True; runtime.stop()
    assert snapshot.status == "EXECUTING"; assert "прошло" in snapshot.message; assert "сек." in snapshot.message


def test_completed_facade_result_is_published_before_waiting():
    result = SimpleNamespace(control=SimpleNamespace(executed=True, reason="COMPLETED")); runtime = _runtime(lambda: result, interval=60)
    runtime.start(); _wait_for(lambda: runtime.state.snapshot().status == "WAITING"); snapshot = runtime.state.snapshot(); runtime.stop()
    assert "Последний цикл выполнен: COMPLETED." in snapshot.message; assert "Следующий анализ через" in snapshot.message


def test_rejected_cycle_remains_enabled_and_exposes_reason():
    result = SimpleNamespace(control=SimpleNamespace(executed=False, reason="PREFLIGHT_REJECTED:LIMIT")); runtime = _runtime(lambda: result, interval=60)
    runtime.start(); _wait_for(lambda: runtime.state.snapshot().status == "WAITING"); snapshot = runtime.state.snapshot(); runtime.stop()
    assert snapshot.enabled is True; assert "Последний цикл не выполнен: PREFLIGHT_REJECTED:LIMIT." in snapshot.message


def test_interval_must_be_positive():
    with pytest.raises(ValueError, match="AUTONOMOUS_INTERVAL_MUST_BE_POSITIVE"):
        AutonomousRuntimeConfig(interval_seconds=0)
