from __future__ import annotations


def test_progress_installer_wraps_existing_analysis_entrypoint(monkeypatch):
    import edward.ui.analysis_ui_v04 as legacy
    import edward.ui.analysis_ui_v088_frontend as frontend
    from edward.ui import analysis_ui_v088_progress as progress

    app_class = type("App", (), {})
    client_class = type("Client", (), {})
    original_open = lambda _app: None

    monkeypatch.setattr(frontend, "install", lambda _app_class, _client_class: setattr(legacy, "_open_analysis", original_open))
    monkeypatch.setattr(legacy, "_open_analysis", original_open, raising=False)
    monkeypatch.setattr(app_class, "_analysis_ui_v088_progress_installed", False, raising=False)

    progress.install(app_class, client_class)

    assert app_class._analysis_ui_v088_progress_installed is True
    assert legacy._open_analysis is not original_open


def test_progress_ui_contains_canonical_analysis_flow():
    from pathlib import Path

    source = Path("src/edward/ui/analysis_ui_v088_progress.py").read_text(encoding="utf-8")

    assert "v0.8.14 Adaptive Discovery · Canonical Path Runtime" in source
    assert "TRAIN → VALIDATION → OOS → Quality Gate" in source
    assert "Результаты будут показаны в окне canonical анализа." in source
    assert "Анализ завершён" not in source
