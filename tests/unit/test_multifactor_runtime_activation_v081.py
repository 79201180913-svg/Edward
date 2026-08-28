from __future__ import annotations

import os
import pytest


def test_multifactor_ui_runtime_module_exposes_install():
    from edward.ui.analysis_ui_v081_runtime import install

    assert callable(install)


def test_multifactor_client_patch_exposes_install():
    from edward.api.tinvest_multifactor_client_patch_v081 import install

    assert callable(install)


def test_gui_launcher_registers_multifactor_ui_on_windows():
    if os.name != "nt":
        pytest.skip("GUI launcher bindings are Windows-specific")
    import edward.ui.gui_launcher as launcher

    assert callable(launcher.install_analysis_ui_v081)
