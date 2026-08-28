from __future__ import annotations

import tkinter as tk
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

            panel = tk.LabelFrame(window, text="EV — статистическая надёжность", padx=12, pady=8)
            panel.pack(fill="x", padx=16, pady=(0, 10))
            for column in range(3):
                panel.columnconfigure(column, weight=1)
            ci_var = tk.StringVar(value="N/A")
            reliability_var = tk.StringVar(value="N/A")
            interpretation_var = tk.StringVar(value="Ожидание результата анализа…")
            tk.Label(panel, text="95% CI Historical EV", anchor="w").grid(row=0, column=0, sticky="w", padx=6)
            tk.Label(panel, text="Edge Reliability", anchor="w").grid(row=0, column=1, sticky="w", padx=6)
            tk.Label(panel, text="Интерпретация", anchor="w").grid(row=0, column=2, sticky="w", padx=6)
            tk.Label(panel, textvariable=ci_var, font=("TkDefaultFont", 10, "bold"), anchor="w").grid(row=1, column=0, sticky="w", padx=6, pady=(3, 0))
            tk.Label(panel, textvariable=reliability_var, font=("TkDefaultFont", 10, "bold"), anchor="w").grid(row=1, column=1, sticky="w", padx=6, pady=(3, 0))
            tk.Label(panel, textvariable=interpretation_var, wraplength=430, justify="left", anchor="w").grid(row=1, column=2, sticky="w", padx=6, pady=(3, 0))
            window.geometry("1250x950")
            window._ev_reliability_panel_added = True

            def refresh_metrics() -> None:
                try:
                    result = getattr(runtime, "_last_v08_pipeline_result", None)
                    if result is not None:
                        ev = result.expected_value
                        if ev.available and ev.ev_ci_low_pct is not None and ev.ev_ci_high_pct is not None:
                            ci_var.set(f"{ev.ev_ci_low_pct:+.2f}% → {ev.ev_ci_high_pct:+.2f}%")
                            reliability_var.set(
                                f"{ev.edge_reliability_pct:.1f}% — {ev.edge_reliability_level}"
                                if ev.edge_reliability_pct is not None
                                else "N/A"
                            )
                            if ev.ev_ci_low_pct > 0:
                                interpretation_var.set("95% CI выше 0%: положительный EV статистически устойчивее.")
                            elif ev.ev_ci_high_pct < 0:
                                interpretation_var.set("95% CI ниже 0%: положительный edge не подтверждён.")
                            else:
                                interpretation_var.set("95% CI пересекает 0%: данных недостаточно, чтобы подтвердить положительный edge.")
                        else:
                            ci_var.set("N/A")
                            reliability_var.set("N/A")
                            interpretation_var.set("Нет достаточного числа реализованных исходов для оценки EV.")
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
