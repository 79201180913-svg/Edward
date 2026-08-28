from __future__ import annotations

import sys
import types

import edward.ui.analysis_ui_v081_runtime as target


def test_v081_installer_replaces_active_analysis_entrypoint(monkeypatch):
    legacy = types.SimpleNamespace(_open_analysis=lambda _app: None)
    runtime = types.SimpleNamespace(
        _open_analysis_v08=lambda _app: None,
        AnalysisPipelineServiceV08=object,
    )
    monkeypatch.setitem(sys.modules, "edward.ui.analysis_ui_v04", legacy)
    monkeypatch.setitem(sys.modules, "edward.ui.analysis_ui_v08_runtime", runtime)
    monkeypatch.setattr(target, "install_client_patch", lambda: None)

    app_class = type("FakeApp", (), {})
    target.install(app_class, object)

    assert legacy._open_analysis is runtime._open_analysis_v08
    assert app_class._analysis_ui_v081_installed is True


def test_unavailable_fundamental_group_is_displayed_as_na_not_zero():
    group = types.SimpleNamespace(score=0.0, coverage=0.0)
    assert target._fundamental_group_score_text(group) == "N/A"


def test_available_fundamental_group_keeps_numeric_score():
    group = types.SimpleNamespace(score=61.8, coverage=50.0)
    assert target._fundamental_group_score_text(group) == "61.8"
