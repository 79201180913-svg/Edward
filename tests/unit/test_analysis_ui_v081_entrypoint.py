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
