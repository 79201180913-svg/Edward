from types import SimpleNamespace

from edward.ui.autonomous_ui_v07 import _display_opportunity_quantity, install_autonomous_ui


class FakeApp:
    _autonomous_ui_v07_installed = False

    def _shell(self):
        self.shell_called = True

    def _close(self):
        self.close_called = True


def test_installs_autonomous_page_and_navigation_hook():
    install_autonomous_ui(FakeApp)

    assert FakeApp._autonomous_ui_v07_installed is True
    assert callable(FakeApp._shell)
    assert callable(FakeApp._page_autonomous)
    assert callable(FakeApp._close)


def test_install_is_idempotent():
    class AnotherFakeApp:
        _autonomous_ui_v07_installed = False

        def _shell(self):
            pass

        def _close(self):
            pass

    install_autonomous_ui(AnotherFakeApp)
    first_shell = AnotherFakeApp._shell
    install_autonomous_ui(AnotherFakeApp)

    assert AnotherFakeApp._shell is first_shell


def test_pass_does_not_present_current_short_position_as_order_quantity():
    opportunity = SimpleNamespace(decision="PASS", recommended_quantity=0, quantity=-998000)
    assert _display_opportunity_quantity(opportunity) == 0


def test_actionable_opportunity_presents_recommended_order_quantity():
    opportunity = SimpleNamespace(decision="REDUCE", recommended_quantity=1500, quantity=2000)
    assert _display_opportunity_quantity(opportunity) == 1500


def test_missing_recommended_quantity_is_zero_for_actionable_opportunity():
    opportunity = SimpleNamespace(decision="SELL", recommended_quantity=0, quantity=500)
    assert _display_opportunity_quantity(opportunity) == 0
