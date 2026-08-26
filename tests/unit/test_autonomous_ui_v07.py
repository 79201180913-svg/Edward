from edward.ui.autonomous_ui_v07 import install_autonomous_ui


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
