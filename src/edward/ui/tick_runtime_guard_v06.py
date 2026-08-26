from __future__ import annotations

import tkinter as tk
from typing import Any


def should_skip_network_tick(*, current_page: str, execution_center_open: bool) -> bool:
    """Return True when the periodic UI tick must not perform blocking API calls."""
    return current_page == "opportunities" or execution_center_open


def install_tick_runtime_guard(app_class: type[Any]) -> None:
    """Prevent periodic synchronous API refreshes from blocking analysis/execution UI."""
    if getattr(app_class, "_tick_runtime_guard_v06_installed", False):
        return

    original_tick = app_class._tick

    def wrapped_tick(self: Any) -> None:
        try:
            window = getattr(self, "_execution_center_window", None)
            execution_center_open = False
            if window is not None:
                try:
                    execution_center_open = bool(window.winfo_exists())
                except tk.TclError:
                    execution_center_open = False

            if should_skip_network_tick(
                current_page=str(getattr(self, "current_page", "")),
                execution_center_open=execution_center_open,
            ):
                if self.winfo_exists():
                    self.after(5000, self._tick)
                return
        except Exception:
            pass
        return original_tick(self)

    app_class._tick = wrapped_tick
    app_class._tick_runtime_guard_v06_installed = True


__all__ = ["should_skip_network_tick", "install_tick_runtime_guard"]
