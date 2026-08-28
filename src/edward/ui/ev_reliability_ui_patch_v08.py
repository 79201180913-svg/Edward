from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


def install() -> None:
    import edward.ui.analysis_ui_v08_runtime as runtime
    from edward.services.analysis_pipeline_service_v08_fixed import AnalysisPipelineServiceV08 as FixedPipeline

    if getattr(runtime, "_ev_reliability_ui_patch_installed", False):
        return

    class PipelineForUI(FixedPipeline):
        def analyze(self, *args: Any, **kwargs: Any):
            result = super().analyze(*args, **kwargs)
            runtime._last_v08_pipeline_result = result
            return result

    runtime.AnalysisPipelineServiceV08 = PipelineForUI
    original = runtime._open_analysis_v08

    def wrapped(app: Any) -> None:
        runtime._last_v08_pipeline_result = None
        original(app)
        for window in app.winfo_children():
            if not isinstance(window, tk.Toplevel) or not window.title().startswith("Анализ акции v0.8"):
                continue
            if getattr(window, "_ev_reliability_panel_added", False):
                continue

            content = getattr(window, "_analysis_content", window)
            metrics = next(
                (
                    item
                    for item in content.winfo_children()
                    if isinstance(item, ttk.LabelFrame)
                    and item.cget("text") == "v0.8 — Expected Value / Forecast / Portfolio"
                ),
                None,
            )
            if metrics is None:
                continue

            ci_var = tk.StringVar(value="N/A")
            reliability_var = tk.StringVar(value="N/A")

            ci_cell = ttk.Frame(metrics, padding=6)
            ci_cell.grid(row=2, column=0, sticky="nsew")
            ttk.Label(ci_cell, text="EV 95% CI").pack(anchor="w")
            ttk.Label(ci_cell, textvariable=ci_var, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(3, 0))

            reliability_cell = ttk.Frame(metrics, padding=6)
            reliability_cell.grid(row=2, column=1, sticky="nsew")
            ttk.Label(reliability_cell, text="Edge Reliability").pack(anchor="w")
            ttk.Label(reliability_cell, textvariable=reliability_var, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(3, 0))

            window._ev_reliability_panel_added = True

            def refresh_metrics() -> None:
                try:
                    result = getattr(runtime, "_last_v08_pipeline_result", None)
                    if result is None:
                        result = getattr(runtime, "_v081_last_result", None)
                    if result is not None:
                        ev = getattr(result, "expected_value", None)
                        if ev is not None and ev.available and ev.ev_ci_low_pct is not None and ev.ev_ci_high_pct is not None:
                            ci_var.set(f"{ev.ev_ci_low_pct:+.2f}% → {ev.ev_ci_high_pct:+.2f}%")
                            reliability_var.set(
                                f"{ev.edge_reliability_pct:.1f}% — {ev.edge_reliability_level}"
                                if ev.edge_reliability_pct is not None
                                else "N/A"
                            )
                        else:
                            ci_var.set("N/A")
                            reliability_var.set("N/A")
                        return
                except tk.TclError:
                    return
                if window.winfo_exists():
                    window.after(250, refresh_metrics)

            window.after(250, refresh_metrics)
            break

    runtime._open_analysis_v08 = wrapped
    runtime._ev_reliability_ui_patch_installed = True


__all__ = ["install"]
