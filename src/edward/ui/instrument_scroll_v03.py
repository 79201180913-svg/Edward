from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


def install_instrument_scroll(app_class: type[Any]) -> None:
    """Wrap the instrument page workspace in a vertical scrolling canvas.

    Header and navigation stay fixed. The scroll handler is installed once at
    application level and always targets the currently active instrument canvas.
    """
    if getattr(app_class, "_instrument_scroll_v03_installed", False):
        return

    original_page = app_class._page_instrument

    def _canvas_alive(canvas: Any) -> bool:
        if canvas is None:
            return False
        try:
            return bool(canvas.winfo_exists())
        except tk.TclError:
            return False

    def _wheel(self: Any, event: Any) -> None:
        canvas = getattr(self, "_instrument_scroll_canvas", None)
        if not _canvas_alive(canvas):
            self._instrument_scroll_canvas = None
            return

        delta = getattr(event, "delta", 0)
        if delta:
            # Windows: positive delta means scroll up.
            canvas.yview_scroll(-1 if delta > 0 else 1, "units")
            return

        num = getattr(event, "num", None)
        if num == 4:
            canvas.yview_scroll(-1, "units")
        elif num == 5:
            canvas.yview_scroll(1, "units")

    def _install_global_wheel_binding(self: Any) -> None:
        if getattr(self, "_instrument_scroll_global_binding", False):
            return
        self.bind_all("<MouseWheel>", lambda event: _wheel(self, event), add="+")
        self.bind_all("<Button-4>", lambda event: _wheel(self, event), add="+")
        self.bind_all("<Button-5>", lambda event: _wheel(self, event), add="+")
        self._instrument_scroll_global_binding = True

    def page_instrument(self: Any) -> None:
        original_content = self.content
        outer = ttk.Frame(original_content)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        workspace = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=workspace, anchor="nw")

        def on_workspace_configure(_event: Any = None) -> None:
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                return

        def on_canvas_configure(event: Any) -> None:
            try:
                canvas.itemconfigure(window_id, width=event.width)
            except tk.TclError:
                return

        workspace.bind("<Configure>", on_workspace_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._instrument_scroll_canvas = canvas
        _install_global_wheel_binding(self)

        self.content = workspace
        try:
            original_page(self)
        finally:
            self.content = original_content

    app_class._page_instrument = page_instrument
    app_class._instrument_scroll_w03 = _wheel
    app_class._instrument_scroll_v03_installed = True
