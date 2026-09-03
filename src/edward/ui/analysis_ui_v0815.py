from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.trading_path_analysis_builder_v012 import TradingPathAnalysisBuilderV012
from edward.services.trading_path_walk_forward_service_v015 import TradingPathWalkForwardServiceV015
from edward.services.trading_path_ui_evidence_projection_v015 import (
    TradingPathUIEvidenceProjectionServiceV015,
)

logger = logging.getLogger(__name__)

_LATEST_RESULTS: dict[str, tuple[Any, ...]] = {}
_LATEST_PIPELINE: dict[str, dict[str, Any]] = {}


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


def _analysis_key(item: Any) -> tuple[Any, ...]:
    return (
        getattr(item, "instrument_uid", None),
        getattr(item, "ticker", None),
        getattr(item, "hypothesis", None),
        getattr(item, "regime", None),
        getattr(item, "volatility_bucket", None),
        getattr(item, "direction", None),
        getattr(item, "horizon", None),
    )


def _pipeline_snapshot(
    validation_results: tuple[Any, ...],
    nested_result: Any,
    final_results: tuple[Any, ...],
) -> dict[str, Any]:
    stable_keys = {
        _analysis_key(candidate)
        for candidate, summary in (getattr(nested_result, "candidate_summaries", ()) or ())
        if getattr(summary, "passed", False) is True
    }
    validated = tuple(
        item
        for item in validation_results
        if _value(getattr(getattr(item, "validation", None), "promotion_status", None)) == "validated"
    )
    adaptive = tuple(
        item
        for item in validation_results
        if str(getattr(item, "strategy_family", "")) == "Adaptive Discovery"
        or str(getattr(item, "hypothesis", "")).startswith("ADAPTIVE_RULE:")
    )
    buy = sum(str(_value(getattr(item, "decision", ""))).lower() == "buy" for item in final_results)
    wait = sum(str(_value(getattr(item, "decision", ""))).lower() == "wait" for item in final_results)
    passed = sum(str(_value(getattr(item, "decision", ""))).lower() == "pass" for item in final_results)
    return {
        "discovered": len(validation_results),
        "validated": len(validated),
        "adaptive": len(adaptive),
        "wf_stable": len(stable_keys),
        "nested_folds": len(getattr(nested_result, "folds", ()) or ()),
        "nested_candidates": len(getattr(nested_result, "candidate_summaries", ()) or ()),
        "final": len(final_results),
        "buy": buy,
        "wait": wait,
        "pass": passed,
    }


def _render_pipeline_summary(text: tk.Text, snapshot: dict[str, Any]) -> None:
    lines = [
        "CANONICAL PIPELINE v0.8.15",
        f"Discovery candidates: {snapshot.get('discovered', 0)}",
        f"Statistically validated: {snapshot.get('validated', 0)}",
        f"Nested WF stable: {snapshot.get('wf_stable', 0)} / {snapshot.get('nested_candidates', 0)} evaluated candidates",
        f"Nested WF folds: {snapshot.get('nested_folds', 0)}",
        f"Final paths: {snapshot.get('final', 0)}",
        f"BUY: {snapshot.get('buy', 0)} | WAIT: {snapshot.get('wait', 0)} | PASS: {snapshot.get('pass', 0)}",
        "",
        "Interpretation: validation and final promotion are separate stages. A path can pass statistical validation and still be rejected by Nested Walk-Forward stability.",
    ]
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.insert("1.0", "\n".join(lines))
    text.configure(state="disabled")


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


def _find_label_frame(widget: Any, title_fragment: str) -> Any | None:
    try:
        if isinstance(widget, ttk.LabelFrame) and title_fragment in str(widget.cget("text")):
            return widget
        for child in widget.winfo_children():
            found = _find_label_frame(child, title_fragment)
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

    legacy_summary = _find_label_frame(window, "Итог v0.8.14")
    legacy_decision = _find_label_frame(window, "Финальный результат canonical runtime")
    legacy_paths = _find_label_frame(window, "Trading Paths — фактический результат v0.8.14")
    if legacy_summary is not None:
        legacy_summary.pack_forget()
    if legacy_decision is not None:
        legacy_decision.pack_forget()
    if legacy_paths is not None:
        legacy_paths.configure(text="Trading Paths — Final canonical paths v0.8.15")

    pipeline_panel = ttk.LabelFrame(content, text="v0.8.15 — Canonical Pipeline", padding=10)
    first_child = content.winfo_children()[0] if content.winfo_children() else None
    if first_child is not None and first_child is not pipeline_panel:
        pipeline_panel.pack(fill="x", pady=(0, 12), before=first_child)
    else:
        pipeline_panel.pack(fill="x", pady=(0, 12))
    pipeline_text = tk.Text(pipeline_panel, height=9, wrap="word")
    pipeline_text.pack(fill="x")
    pipeline_text.configure(state="disabled")

    evidence_panel = ttk.LabelFrame(content, text="v0.8.15 — Canonical Evidence / Quality Gate", padding=10)
    evidence_panel.pack(fill="x", pady=(0, 12))
    evidence_text = tk.Text(evidence_panel, height=12, wrap="word")
    evidence_text.pack(fill="x")
    evidence_text.configure(state="disabled")

    def refresh(_event: Any = None) -> None:
        snapshot = _LATEST_PIPELINE.get(ticker)
        if snapshot is not None:
            _render_pipeline_summary(pipeline_text, snapshot)
        results = _LATEST_RESULTS.get(ticker, ())
        if not results:
            evidence_text.configure(state="normal")
            evidence_text.delete("1.0", "end")
            evidence_text.insert(
                "1.0",
                "No final canonical path reached the Evidence / Quality Gate stage.\n\n"
                "See the pipeline summary above for the exact validation → Nested WF funnel.",
            )
            evidence_text.configure(state="disabled")
            return
        selected = tree.selection()
        index = int(selected[0]) if selected and str(selected[0]).isdigit() else 0
        if index >= len(results):
            index = 0
        try:
            _render_projection(evidence_text, results[index])
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
    original_builder_build = TradingPathAnalysisBuilderV012.build.__func__
    original_nested_validate = TradingPathWalkForwardServiceV015.nested_validate.__func__
    capture: dict[str, Any] = {"validation": (), "nested": None}

    def build(cls: Any, candidates: Any, candles: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_builder_build(cls, candidates, candles, *args, **kwargs)
        capture["validation"] = tuple(result or ())
        return result

    def nested_validate(cls: Any, candles: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_nested_validate(cls, candles, *args, **kwargs)
        capture["nested"] = result
        return result

    TradingPathAnalysisBuilderV012.build = classmethod(build)
    TradingPathWalkForwardServiceV015.nested_validate = classmethod(nested_validate)

    def analyze_paths(self: Any, *args: Any, **kwargs: Any) -> Any:
        capture["validation"] = ()
        capture["nested"] = None
        results = original_analyze_paths(self, *args, **kwargs)
        ticker = str(kwargs.get("ticker", ""))
        if not ticker and len(args) >= 2:
            ticker = str(args[1])
        final_results = tuple(results or ())
        _LATEST_RESULTS[ticker] = final_results
        nested_result = capture.get("nested")
        if nested_result is not None:
            _LATEST_PIPELINE[ticker] = _pipeline_snapshot(
                tuple(capture.get("validation") or ()),
                nested_result,
                final_results,
            )
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
            logger.exception("[V815 UI] failed to attach canonical evidence UI")
        return result

    legacy._open_analysis = open_analysis
    app_class._analysis_ui_v0815_installed = True


__all__ = ["install"]
