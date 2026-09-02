from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


def install(app_class: type[Any], client_class: type[Any]) -> None:
    import edward.ui.analysis_ui_v088_frontend as frontend

    if getattr(app_class, "_analysis_ui_v088_progress_installed", False):
        return

    frontend.install(app_class, client_class)

    import edward.ui.analysis_ui_v04 as legacy
    canonical_open_analysis = legacy._open_analysis

    def open_analysis_with_progress(app: Any) -> None:
        detail = getattr(app, "instrument_detail", None)
        ticker = str((detail or {}).get("ticker", ""))
        if not detail:
            canonical_open_analysis(app)
            return

        progress = tk.Toplevel(app)
        progress.title(f"Анализ {ticker} — v0.8.14")
        progress.geometry("560x210")
        progress.minsize(520, 190)
        progress.resizable(False, False)
        progress.transient(app)

        outer = ttk.Frame(progress, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=f"Анализ {ticker}", font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text="v0.8.14 Adaptive Discovery · Canonical Path Runtime").pack(anchor="w", pady=(3, 14))
        ttk.Label(outer, text="Запускаем TRAIN → VALIDATION → OOS → Quality Gate…", font=("TkDefaultFont", 11, "bold"), wraplength=500).pack(anchor="w")
        ttk.Label(outer, text="Результаты будут показаны в окне canonical анализа.", wraplength=500).pack(anchor="w", pady=(7, 12))
        bar = ttk.Progressbar(outer, mode="indeterminate")
        bar.pack(fill="x")
        bar.start(12)

        try:
            progress.update_idletasks()
            progress.update()
            canonical_open_analysis(app)
        finally:
            bar.stop()
            try:
                progress.destroy()
            except tk.TclError:
                pass

    legacy._open_analysis = open_analysis_with_progress
    app_class._analysis_ui_v088_progress_installed = True


__all__ = ["install"]
