from __future__ import annotations

from typing import Any
import tkinter as tk
from tkinter import ttk


def install_instrument_scroll(app_class: type[Any]) -> None:
    """Wrap the instrument page content in a vertical scrolling canvas.

    The shell/header/navigation stay fixed; only the instrument workspace scrolls.
    """
    if getattr(app_class, "_instrument_scroll_v03_installed", False):
        return

    original_page = app_class._page_instrument

    def page_instrument(self: Any) -> None:
        original_content = self.content
        outer = ttk.Frame(original_content)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        workspace = ttk.Frame(canvas)

        window_id = canvas.create_window((0, 0), window=workspace, anchor="nw")

        def on_workspace_configure(_event: Any = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event: Any) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        workspace.bind("<Configure>", on_workspace_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        original_content.winfo_children()
        # Temporarily redirect the page renderer to the scrollable workspace.
        self.content = workspace
        try:
            original_page(self)
        finally:
            self.content = original_content

        def wheel(event: Any) -> None:
            delta = -1 if getattr(event, "delta", 0) > 0 else 1
            canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", wheel, add="+")
        canvas.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"), add="+")
        canvas.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"), add="+")

    app_class._page_instrument = page_instrument
    app_class._instrument_scroll_v03_installed = True
