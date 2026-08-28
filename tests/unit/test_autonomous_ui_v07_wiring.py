from pathlib import Path


UI_PATH = Path(__file__).parents[2] / "src" / "edward" / "ui" / "autonomous_ui_v07.py"


def test_autonomous_runtime_wires_live_budget_callbacks():
    source = UI_PATH.read_text(encoding="utf-8")

    assert "policy=policy" in source
    assert "progress_callback=on_progress" in source
    assert "result_callback=autonomous_result_callback" in source
    assert "scope_callback=autonomous_scope_callback" in source
    assert "planning_callback=run_runtime_cycle" not in source
    assert "planning_callback=autonomous_planning_callback" in source
    assert "run_cycle=run_runtime_cycle" in source


def test_manual_runtime_uses_runtime_control_result():
    source = UI_PATH.read_text(encoding="utf-8")

    assert "control_result = getattr(result, \"control\", result)" in source
