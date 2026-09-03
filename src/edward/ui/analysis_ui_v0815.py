from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.trading_path_ui_evidence_projection_v015 import (
    TradingPathUIEvidenceProjectionServiceV015,
)

logger = logging.getLogger(__name__)

_LATEST_RESULTS: dict[str, tuple[Any, ...]] = {}


def _value(value: Any, default: Any = "N/A") -> Any:
    if value is None:
        return default
    return getattr(value, "value", value)


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_bool(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "N/A"


def _find_tree(widget: Any) -> Any | None:
    try:
        if isinstance(widget, ttk.Treeview):
            columns = tuple(widget["columns"] or ())
            if len(columns) >= 12:
                return widget
        for child in widget.winfo_children():
            found = _find_tree(child)
            if found is not None:
                return found
    except tk.TclError:
        return None
    return None


def _find_content(widget: Any) -> Any | None:
    try:
        for child in widget.winfo_children():
            if isinstance(child, ttk.LabelFrame) and "Детализация выбранного пути" in str(child.cget("text")):
                return child.master
            found = _find_content(child)
            if found is not None:
                return found
    except tk.TclError:
        return None
    return None


def _render_projection(text: tk.Text, item: Any) -> None:
    projection = TradingPathUIEvidenceProjectionServiceV015.build(item)
    reasons = ", ".join(projection.quality_gate_reasons) if projection.quality_gate_reasons else "—"
    lines = [
        f"Statistical Evidence: {_fmt_bool(projection.statistical_gate)}",
        f"WF Persistence: {_fmt_pct(projection.wf_persistence_pct)} | WF Worst Window: {_fmt_pct(projection.wf_worst_window_excess_pct)}",
        f"Independent OOS Edge: {_fmt_pct(projection.oos_excess_pct)} | OOS Worst Window: {_fmt_pct(projection.oos_worst_window_excess_pct)}",
        f"Regime Excess: {_fmt_pct(projection.regime_excess_pct)} | Market Excess: {_fmt_pct(projection.market_excess_pct)}",
        f"EV: {_fmt_pct(projection.ev_pct)} | CI: {_fmt_pct(projection.ev_ci_low_pct)} … {_fmt_pct(projection.ev_ci_high_pct)}",
        f"EV Reliability: {_fmt_pct(projection.ev_reliability_pct)} | Confidence: {_fmt_pct(projection.confidence_score)}",
        f"Risk Gate: {_fmt_bool(projection.risk_gate)}",
        f"Current State: {_value(projection.current_state)}",
        f"QUALITY GATE: {_fmt_bool(projection.quality_gate_passed)}",
        f"REASON: {reasons}",
        f"DECISION: {str(_value(projection.decision)).upper()} | STATUS: {str(_value(projection.status)).upper()}",
        "",
        "Opportunity Score / legacy confidence are diagnostic only; they do not override critical gates.",
    ]
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.insert("1.0", "\n".join(lines))
    text.configure(state="disabled")


def _attach_evidence_panel(window: Any, ticker: str) -> None:
    tree = _find_tree(window)
    content = _find_content(window)
    if tree is None or content is None:
        logger.warning("[V815 UI] canonical widgets not found ticker=%s", ticker)
        return

    panel = ttk.LabelFrame(content, text="v0.8.15 — Canonical Evidence / Quality Gate", padding=10)
    panel.pack(fill="x", pady=(0, 12))
    text = tk.Text(panel, height=12, wrap="word")
    text.pack(fill="x")
    text.configure(state="disabled")

    def refresh(_event: Any = None) -> None:
        results = _LATEST_RESULTS.get(ticker, ())
        if not results:
            return
        selected = tree.selection()
        index = int(selected[0]) if selected and str(selected[0]).isdigit() else 0
        if index >= len(results):
            index = 0
        try:
            _render_projection(text, results[index])
        except Exception:
            logger.exception("[V815 UI] evidence projection render failed ticker=%s index=%s", ticker, index)

    tree.bind("<<TreeviewSelect>>", refresh, add="+")

    def poll() -> None:
        try:
            if not window.winfo_exists():
                return
            refresh()
            window.after(500, poll)
        except tk.TclError:
            return

    refresh()
    window.after(500, poll)


def install(app_class: type[Any], client_class: type[Any]) -> None:
    if getattr(app_class, "_analysis_ui_v0815_installed", False):
        return

    original_analyze_paths = AnalysisPathRuntimeServiceV012.analyze_paths

    def analyze_paths(self: Any, *args: Any, **kwargs: Any) -> Any:
        results = original_analyze_paths(self, *args, **kwargs)
        ticker = str(kwargs.get("ticker", ""))
        if not ticker and len(args) >= 2:
            ticker = str(args[1])
        _LATEST_RESULTS[ticker] = tuple(results or ())
        return results

    AnalysisPathRuntimeServiceV012.analyze_paths = analyze_paths

    import edward.ui.analysis_ui_v04 as legacy

    original_open = legacy._open_analysis

    def open_analysis(app: Any) -> Any:
        before = set(app.winfo_children())
        result = original_open(app)
        try:
            candidates = [child for child in app.winfo_children() if child not in before]
            windows = [child for child in candidates if isinstance(child, tk.Toplevel)]
            if windows:
                ticker = str(getattr(app, "instrument_detail", {}).get("ticker", ""))
                _attach_evidence_panel(windows[-1], ticker)
        except Exception:
            logger.exception("[V815 UI] failed to attach evidence panel")
        return result

    legacy._open_analysis = open_analysis
    app_class._analysis_ui_v0815_installed = True


__all__ = ["install"]
