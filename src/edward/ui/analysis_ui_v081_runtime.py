from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from typing import Any
from tkinter import ttk

from edward.api.tinvest_multifactor_client_patch_v081 import install as install_client_patch
from edward.services.analysis_pipeline_service_v081 import AnalysisPipelineServiceV081
from edward.services.semantic_robust_contract_analysis_data_service_v081 import SemanticRobustContractAnalysisDataServiceV081
from edward.services.news_intelligence_service_v081 import NewsIntelligenceServiceV081
from edward.services.news_overlay_service_v081 import NewsOverlayServiceV081
from edward.services.multifactor_diagnostics_v081 import emit_multifactor_diagnostics


def install(app_class: type[Any], client_class: type[Any]) -> None:
    import edward.ui.analysis_ui_v04 as legacy
    import edward.ui.analysis_ui_v08_runtime as runtime

    if getattr(app_class, "_analysis_ui_v081_installed", False):
        return
    install_client_patch()
    original = runtime._open_analysis_v08

    def wrapped(app: Any) -> None:
        detail = getattr(app, "instrument_detail", None)
        if not detail:
            return
        runtime._v081_last_result = None
        runtime._v081_last_news = None
        runtime._v081_last_failed_sources = ()

        original(app)
        windows = [
            item
            for item in app.winfo_children()
            if isinstance(item, tk.Toplevel) and item.title().startswith("Анализ акции v0.8")
        ]
        if not windows:
            return
        window = windows[-1]

        panel = ttk.LabelFrame(window, text="v0.8.1 — Multi-Factor Evidence", padding=10)
        decision_frame = next(
            (
                item
                for item in window.winfo_children()
                if isinstance(item, ttk.LabelFrame) and item.cget("text") == "Торговое решение"
            ),
            None,
        )
        panel.pack(fill="x", padx=16, pady=(0, 10), before=decision_frame)
        for column in range(5):
            panel.columnconfigure(column, weight=1)
        values = {key: tk.StringVar(value="N/A") for key in (
            "fundamental", "micro", "volume", "signals", "events", "news", "insider", "session", "instrument_risk", "evidence"
        )}
        labels = (
            ("fundamental", "Fundamental"), ("micro", "Microstructure"), ("volume", "Volume Pressure"),
            ("signals", "T-Invest Signals"), ("events", "Event Risk"), ("news", "News Risk"),
            ("insider", "Insider"), ("session", "Session"), ("instrument_risk", "Instrument Risk"),
            ("evidence", "Evidence Reliability"),
        )
        for index, (key, title) in enumerate(labels):
            row, col = divmod(index, 5)
            cell = ttk.Frame(panel, padding=5)
            cell.grid(row=row, column=col, sticky="nsew")
            ttk.Label(cell, text=title).pack(anchor="w")
            ttk.Label(cell, textvariable=values[key], font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(2, 0))

        status = tk.StringVar(value="")
        ttk.Label(panel, textvariable=status, wraplength=1100, justify="left").grid(row=2, column=0, columnspan=5, sticky="w", padx=5, pady=(6, 0))

        def show_v081(result: Any, news_result: Any, failed_sources: tuple[str, ...]) -> None:
            runtime._v081_last_result = result
            runtime._v081_last_news = news_result
            runtime._v081_last_failed_sources = failed_sources
            factors = result.multifactor
            values["fundamental"].set(
                f"{factors.fundamentals.quality_score:.1f}"
                if factors.fundamentals.evidence.available else "N/A"
            )
            values["micro"].set(f"{factors.microstructure.entry_quality_score:.1f}" if factors.microstructure.evidence.available else "N/A")
            values["volume"].set(f"{factors.volume_pressure.accumulation_score:.1f}" if factors.volume_pressure.evidence.available else "N/A")
            values["signals"].set(f"{factors.signals.reliability_pct:.1f}" if factors.signals.evidence.available else "N/A")
            values["events"].set(f"{factors.event_risk.event_risk_score:.1f}" if factors.event_risk.evidence.available else "N/A")
            values["news"].set(f"{news_result.news_risk_score:.1f}" if news_result.evidence_available else "N/A")
            values["insider"].set(f"{factors.insider.activity_score:.1f}" if factors.insider.evidence.available else "N/A")
            values["session"].set(f"{factors.session.quality_score:.1f}" if factors.session.evidence.available else "N/A")
            values["instrument_risk"].set(f"{factors.instrument_risk.risk_score:.1f}" if factors.instrument_risk.evidence.available else "N/A")
            values["evidence"].set(f"{result.overlay.evidence_reliability:.1f}")
            failure_text = f" Недоступны: {', '.join(failed_sources)}." if failed_sources else ""
            status.set(
                f"Opportunity: {result.overlay.adjusted_opportunity_score:.1f} | "
                f"Confidence: {result.overlay.adjusted_confidence:.1f} | "
                f"Conflicts: {result.overlay.conflict_penalty:.1f}." + failure_text
            )

        original_pipeline_class = runtime.AnalysisPipelineServiceV08

        class PipelineBridge:
            def __init__(self) -> None:
                self.client = app.client

            def analyze(self, **kwargs: Any):
                collector = SemanticRobustContractAnalysisDataServiceV081(self.client)
                data = collector.collect(str(detail["instrument_uid"]))
                reports = list(data.reports)
                event = reports[0] if reports else None
                current_signal = data.signals[0] if data.signals else None
                pipeline = AnalysisPipelineServiceV081().analyze(
                    **kwargs,
                    fundamentals=data.fundamentals,
                    order_book=data.order_book,
                    trades=data.trades,
                    current_signal=current_signal,
                    historical_signals=data.signals,
                    event=event,
                    dividend_data=data.dividends,
                    insider_transactions=data.insider_transactions,
                    risk_data=data.risk_data,
                    session_name=data.session_name,
                )
                news_result = NewsIntelligenceServiceV081.analyze(data.news, instrument_uid=str(detail["instrument_uid"]))
                adjusted_base, news_overlay = NewsOverlayServiceV081.apply(pipeline.base, news_result)
                pipeline = replace(pipeline, base=adjusted_base)
                emit_multifactor_diagnostics(
                    instrument_uid=str(detail["instrument_uid"]),
                    data=data,
                    result=pipeline,
                )
                show_v081(pipeline, news_result, data.failed_sources)
                return pipeline

        runtime.AnalysisPipelineServiceV08 = PipelineBridge
        window.protocol("WM_DELETE_WINDOW", lambda: (setattr(runtime, "AnalysisPipelineServiceV08", original_pipeline_class), window.destroy()))

    runtime._open_analysis_v08 = wrapped
    legacy._open_analysis = wrapped
    app_class._analysis_ui_v081_installed = True


__all__ = ["install"]
