from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import replace
from typing import Any
from tkinter import ttk

from edward.api.tinvest_multifactor_client_patch_v081 import install as install_client_patch
from edward.services.analysis_pipeline_service_v081 import AnalysisPipelineServiceV081
from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisServiceV082
from edward.services.semantic_robust_contract_analysis_data_service_v081 import SemanticRobustContractAnalysisDataServiceV081
from edward.services.news_intelligence_service_v081 import NewsIntelligenceServiceV081
from edward.services.news_overlay_service_v081 import NewsOverlayServiceV081
from edward.services.multifactor_diagnostics_v081 import emit_multifactor_diagnostics

logger = logging.getLogger(__name__)


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
        runtime._v082_fundamental_detail = None

        original(app)
        windows = [
            item
            for item in app.winfo_children()
            if isinstance(item, tk.Toplevel) and item.title().startswith("Анализ акции v0.8")
        ]
        if not windows:
            return
        window = windows[-1]
        content = getattr(window, "_analysis_content", window)

        panel = ttk.LabelFrame(content, text="v0.8.1 — Multi-Factor Evidence", padding=10)
        decision_frame = next(
            (
                item
                for item in content.winfo_children()
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

        fundamental_detail: Any = None

        def open_fundamental_detail() -> None:
            if fundamental_detail is None:
                return
            detail_window = tk.Toplevel(window)
            detail_window.title("v0.8.2 — Fundamental Analysis")
            detail_window.geometry("980x680")
            detail_window.minsize(760, 520)
            detail_window.transient(window)
            detail_window.grab_set()

            detail_container = ttk.Frame(detail_window)
            detail_container.pack(fill="both", expand=True)
            detail_container.rowconfigure(0, weight=1)
            detail_container.columnconfigure(0, weight=1)

            detail_canvas = tk.Canvas(detail_container, highlightthickness=0)
            detail_scrollbar = ttk.Scrollbar(detail_container, orient="vertical", command=detail_canvas.yview)
            detail_canvas.configure(yscrollcommand=detail_scrollbar.set)
            detail_canvas.grid(row=0, column=0, sticky="nsew")
            detail_scrollbar.grid(row=0, column=1, sticky="ns")

            detail_content = ttk.Frame(detail_canvas)
            detail_canvas_window = detail_canvas.create_window((0, 0), window=detail_content, anchor="nw")

            def update_detail_scroll_region(_event: Any = None) -> None:
                detail_canvas.configure(scrollregion=detail_canvas.bbox("all"))

            def update_detail_width(event: Any) -> None:
                detail_canvas.itemconfigure(detail_canvas_window, width=event.width)
                update_detail_scroll_region()

            detail_content.bind("<Configure>", update_detail_scroll_region)
            detail_canvas.bind("<Configure>", update_detail_width)

            header = ttk.Frame(detail_content, padding=12)
            header.pack(fill="x")
            ttk.Label(
                header,
                text=f"Fundamental Score: {fundamental_detail.overall_score:.1f} | "
                     f"Confidence: {fundamental_detail.confidence:.1f} | "
                     f"Coverage: {fundamental_detail.coverage:.1f}% | "
                     f"Profile: {fundamental_detail.strategy_profile}",
                font=("TkDefaultFont", 11, "bold"),
            ).pack(anchor="w")

            group_table = ttk.Treeview(
                detail_content,
                columns=("group", "score", "coverage", "confidence"),
                show="headings",
                height=7,
            )
            for key, title, width in (
                ("group", "Группа", 240),
                ("score", "Score", 100),
                ("coverage", "Coverage %", 110),
                ("confidence", "Confidence", 120),
            ):
                group_table.heading(key, text=title)
                group_table.column(key, width=width, anchor="center")
            group_table.pack(fill="x", padx=12, pady=(0, 10))

            group_map = {
                "business_quality": "Business Quality",
                "growth": "Growth",
                "cash_generation": "Cash Generation",
                "financial_health": "Financial Health",
                "valuation": "Valuation",
                "shareholder_return": "Shareholder Return",
                "fundamental_momentum": "Fundamental Momentum",
            }
            groups = (
                fundamental_detail.business_quality,
                fundamental_detail.growth,
                fundamental_detail.cash_generation,
                fundamental_detail.financial_health,
                fundamental_detail.valuation,
                fundamental_detail.shareholder_return,
                fundamental_detail.fundamental_momentum,
            )
            for group in groups:
                group_table.insert(
                    "", "end",
                    values=(
                        group_map.get(group.name, group.name),
                        f"{group.score:.1f}",
                        f"{group.coverage:.1f}",
                        f"{group.confidence:.1f}",
                    ),
                )

            metrics_text = tk.Text(detail_content, height=22, wrap="word")
            metrics_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            lines: list[str] = []
            for group in groups:
                lines.append(
                    f"{group_map.get(group.name, group.name)} — "
                    f"score={group.score:.1f}, coverage={group.coverage:.1f}%, confidence={group.confidence:.1f}"
                )
                if group.reason_codes:
                    lines.append(f"  reasons: {', '.join(group.reason_codes)}")
                for metric in group.metrics:
                    value = "N/A" if metric.value is None else f"{metric.value:.4g}"
                    lines.append(
                        f"  {metric.metric}: value={value}, score={metric.score:.1f}, "
                        f"available={metric.available}, direction={metric.direction}"
                    )
                lines.append("")
            metrics_text.insert("1.0", "\n".join(lines))
            metrics_text.configure(state="disabled")
            ttk.Button(detail_content, text="Закрыть", command=detail_window.destroy).pack(pady=(0, 10))

        fundamental_button = ttk.Button(panel, text="Детализация", command=open_fundamental_detail)
        fundamental_button.grid(row=3, column=0, sticky="w", padx=5, pady=(2, 0))

        def show_v081(result: Any, news_result: Any, failed_sources: tuple[str, ...], v082_fundamental: Any) -> None:
            nonlocal fundamental_detail
            fundamental_detail = v082_fundamental
            runtime._v081_last_result = result
            runtime._v081_last_news = news_result
            runtime._v081_last_failed_sources = failed_sources
            runtime._v082_fundamental_detail = v082_fundamental
            factors = result.multifactor
            values["fundamental"].set(
                f"{v082_fundamental.overall_score:.1f}"
                if v082_fundamental.status != "UNAVAILABLE" else "N/A"
            )
            fundamental_button.configure(state="normal" if v082_fundamental.status != "UNAVAILABLE" else "disabled")
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
            group_summary = "; ".join(
                f"{g.name}={g.score:.1f}({g.coverage:.0f}%)"
                for g in (
                    v082_fundamental.business_quality,
                    v082_fundamental.growth,
                    v082_fundamental.cash_generation,
                    v082_fundamental.financial_health,
                    v082_fundamental.valuation,
                    v082_fundamental.shareholder_return,
                    v082_fundamental.fundamental_momentum,
                )
            )
            logger.info(
                "[V082 FUNDAMENTAL BREAKDOWN] instrument_uid=%s overall=%.1f confidence=%.1f coverage=%.1f status=%s groups=%s",
                detail["instrument_uid"],
                v082_fundamental.overall_score,
                v082_fundamental.confidence,
                v082_fundamental.coverage,
                v082_fundamental.status,
                group_summary,
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
                    instrument_risk_metadata=data.instrument_risk_metadata,
                    session_name=data.session_name,
                )
                v082_fundamental = FundamentalAnalysisServiceV082.analyze(
                    data.fundamentals,
                    profile=kwargs.get("profile", "medium_term"),
                )
                news_result = NewsIntelligenceServiceV081.analyze(data.news, instrument_uid=str(detail["instrument_uid"]))
                adjusted_base, news_overlay = NewsOverlayServiceV081.apply(pipeline.base, news_result)
                pipeline = replace(pipeline, base=adjusted_base)
                emit_multifactor_diagnostics(
                    instrument_uid=str(detail["instrument_uid"]),
                    data=data,
                    result=pipeline,
                )
                show_v081(pipeline, news_result, data.failed_sources, v082_fundamental)
                return pipeline

        runtime.AnalysisPipelineServiceV08 = PipelineBridge
        window.protocol("WM_DELETE_WINDOW", lambda: (setattr(runtime, "AnalysisPipelineServiceV08", original_pipeline_class), window.destroy()))

    runtime._open_analysis_v08 = wrapped
    legacy._open_analysis = wrapped
    app_class._analysis_ui_v081_installed = True


__all__ = ["install"]
