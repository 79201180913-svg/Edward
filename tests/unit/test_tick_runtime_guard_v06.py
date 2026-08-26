from edward.ui.tick_runtime_guard_v06 import should_skip_network_tick


def test_network_tick_is_skipped_during_opportunity_scan():
    assert should_skip_network_tick(current_page="opportunities", execution_center_open=False) is True


def test_network_tick_is_skipped_when_execution_center_is_open():
    assert should_skip_network_tick(current_page="opportunities", execution_center_open=True) is True
    assert should_skip_network_tick(current_page="overview", execution_center_open=True) is True


def test_network_tick_remains_enabled_for_simple_pages():
    assert should_skip_network_tick(current_page="overview", execution_center_open=False) is False
    assert should_skip_network_tick(current_page="portfolio", execution_center_open=False) is False
