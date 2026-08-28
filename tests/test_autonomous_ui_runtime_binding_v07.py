from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


UI_SOURCE = ROOT / "src" / "edward" / "ui" / "autonomous_ui_v07.py"
FACADE_SOURCE = ROOT / "src" / "edward" / "services" / "autonomous_trading_runtime_facade.py"


def test_autonomous_runtime_passes_live_ui_callbacks():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert 'policy=policy, profile=profile_var.get()' in source
    assert '"progress_callback": on_progress' in source
    assert '"result_callback": autonomous_result_callback' in source
    assert '"scope_callback": autonomous_scope_callback' in source
    assert '"planning_callback": autonomous_planning_callback' in source
    assert '"cycle_result_callback": render_result' in source
    assert 'run_cycle=lambda: facade.run_cycle(max_iterations=50, **callbacks)' in source


def test_runtime_facade_publishes_completed_cycle_result_to_ui():
    source = FACADE_SOURCE.read_text(encoding="utf-8")

    assert 'cycle_result_callback: Callable[[Any], None] | None = None' in source
    assert 'if cycle_result_callback is not None:' in source
    assert 'cycle_result_callback(result)' in source
