from edward.ui.opportunity_search_ui_v04 import install_opportunity_search_ui


def test_opportunity_search_ui_installer_is_callable():
    assert callable(install_opportunity_search_ui)
