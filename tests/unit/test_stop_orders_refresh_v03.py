from edward.ui.stop_orders_refresh_v03 import install_stop_orders_refresh


def test_stop_orders_refresh_wraps_tick_once():
    class FakeWindow:
        _stop_orders_refresh_v03_installed = False
        _tick_calls = 0
        _clears = 0
        _shows = 0
        current_page = "stop_orders"

        def _tick(self):
            self._tick_calls += 1

        def _clear(self):
            self._clears += 1

        def _show_page(self, page):
            assert page == "stop_orders"
            self._shows += 1

        def winfo_exists(self):
            return True

    install_stop_orders_refresh(FakeWindow)
    install_stop_orders_refresh(FakeWindow)

    window = FakeWindow()
    window._tick()

    assert window._tick_calls == 1
    assert window._clears == 1
    assert window._shows == 1
    assert window._stop_orders_refresh_v03_installed is True
