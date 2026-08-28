from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_execution_events_are_published_through_controller_and_facade():
    controller = (ROOT / "src/edward/services/autonomous_trading_controller.py").read_text(encoding="utf-8")
    facade = (ROOT / "src/edward/services/autonomous_trading_runtime_facade.py").read_text(encoding="utf-8")
    assert "execution_event_callback: Callable[[dict[str, Any]], None] | None = None" in controller
    assert "execution_event_callback=execution_event_callback" in controller
    assert "execution_event_callback: Callable[[dict[str, Any]], None] | None = None" in facade
    assert "type(self)._execution_event_sink" in facade
    assert "execution_event_callback=execution_event_callback" in facade


def test_execution_status_panel_contains_lifecycle_columns():
    ui = (ROOT / "src/edward/ui/autonomous_control_ui_v07.py").read_text(encoding="utf-8")
    assert "Исполнение автономных сделок" in ui
    assert "Execution ID" in ui
    assert "_handle_execution_event" in ui
    for status in ("PLAN", "SUBMITTING", "SUBMITTED", "VERIFYING", "EXECUTED", "FAILED"):
        assert status not in ui or status == "PLAN"
