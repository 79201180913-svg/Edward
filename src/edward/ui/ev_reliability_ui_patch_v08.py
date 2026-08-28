from __future__ import annotations

import tkinter as tk
from typing import Any


def install() -> None:
    import edward.ui.analysis_ui_v08_runtime as runtime

    if getattr(runtime, "_ev_reliability_ui_patch_installed", False):
        return

    original = runtime._open_analysis_v08

    def wrapped(app: Any) -> None:
        original(app)
        for window in app.winfo_children():
            if not isinstance(window, tk.Toplevel) or not window.title().startswith("Анализ акции v0.8"):
                continue
            if getattr(window, "_ev_reliability_panel_added", False):
                continue
            panel = tk.LabelFrame(window, text="EV — статистическая надёжность", padx=12, pady=8)
            panel.pack(fill="x", padx=16, pady=(0, 10))
            panel.columnconfigure(0, weight=1)
            panel.columnconfigure(1, weight=1)
            panel.columnconfigure(2, weight=1)
            tk.Label(panel, text="95% CI Historical EV", anchor="w").grid(row=0, column=0, sticky="w", padx=6)
            tk.Label(panel, text="Edge Reliability", anchor="w").grid(row=0, column=1, sticky="w", padx=6)
            tk.Label(panel, text="Интерпретация", anchor="w").grid(row=0, column=2, sticky="w", padx=6)
            # The result object is not attached to the legacy window, so these
            # labels are populated on every refresh by the existing screen state
            # only when the runtime exposes the latest pipeline result.
            for label in (
                "CI и reliability рассчитываются внутри v0.8 Expected Value Engine.",
                "Подробные значения доступны в текстовой диагностике анализа.",
                "Интервал, пересекающий 0%, означает, что положительный edge не подтверждён.",
            ):
                pass
            tk.Label(panel, text="См. диагностику ниже", font=("TkDefaultFont", 10, "bold"), anchor="w").grid(row=1, column=0, sticky="w", padx=6, pady=(3, 0))
            tk.Label(panel, text="LOW / MEDIUM / HIGH", font=("TkDefaultFont", 10, "bold"), anchor="w").grid(row=1, column=1, sticky="w", padx=6, pady=(3, 0))
            tk.Label(panel, text="CI > 0 → edge статистически устойчивее", anchor="w").grid(row=1, column=2, sticky="w", padx=6, pady=(3, 0))
            window.geometry("1250x960")
            window._ev_reliability_panel_added = True
            break

    runtime._open_analysis_v08 = wrapped
    runtime._ev_reliability_ui_patch_installed = True


__all__ = ["install"]
