from __future__ import annotations

import os
import pytest


def test_v08_ui_runtime_installer_imports_and_exposes_install():
    from edward.ui.analysis_ui_v08_runtime import install

    assert callable(install)


def test_gui_launcher_imports_v08_ui_runtime():
    if os.name != "nt":
        pytest.skip("GUI launcher uses Windows-only token dialog bindings")
    import edward.ui.gui_launcher as launcher

    assert callable(launcher.install_analysis_ui_v08)
