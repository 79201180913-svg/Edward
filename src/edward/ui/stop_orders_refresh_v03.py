from __future__ import annotations

from typing import Any


def install_stop_orders_refresh(app_class: type[Any]) -> None:
    """Refresh the protective-orders screen together with the main 5s UI tick."""
    if getattr(app_class, "_stop_orders_refresh_v03_installed", False):
        return

    original_tick = app_class._tick

    def tick(self: Any) -> None:
        original_tick(self)
        try:
            if self.current_page == "stop_orders" and self.winfo_exists():
                self._clear()
                self._show_page("stop_orders")
        except Exception:
            pass

    app_class._tick = tick
    app_class._stop_orders_refresh_v03_installed = True
