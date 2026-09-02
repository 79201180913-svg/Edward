from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any

from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012
from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011

logger = logging.getLogger(__name__)


def _parse_candles(response: Any) -> list[Any]:
    from edward.ui.analysis_ui_v04 import _parse_candles
    return _parse_candles(response)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _value(value: Any, default: Any = "N/A") -> Any:
    return getattr(value, "value", value) if value is not None else default


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_bool(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "N/A"


def _unwrap_instrument(response: Any) -> Any:
    if isinstance(response, (list, tuple)):
        return response[0] if response else {}
    if isinstance(response, dict):
        for key in ("instrument", "item", "instrument_info"):
            if response.get(key) is not None:
                value = response[key]
                return value[0] if isinstance(value, (list, tuple)) and value else value
    return response


def install(app_class: type[Any], client_class: type[Any]) -> None:
    import edward.ui.analysis_ui_v04 as legacy

    if getattr(app_class, "_analysis_ui_v088_frontend_installed", False):
        return

    def open_analysis(app: Any) -> None:
        detail = getattr(app, "instrument_detail", None)
        if not detail:
            return

        ticker = str(detail.get("ticker", ""))
        uid = str(detail.get("instrument_uid", ""))
        window = tk.Toplevel(app)
        window.title(f"Канонический анализ v0.8.14 — {ticker}")
        window.geometry("1400x1050")
        window.minsize(1180, 820)
        window.transient(app)

        outer = ttk.Frame(window)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        content = ttk.Frame(canvas, padding=16)
        canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))

        header = ttk.Frame(content)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text=f"Анализ: {ticker}", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="v0.8.14 Adaptive Discovery · Canonical Path Runtime", font=("TkDefaultFont", 12, "bold")).pack(side="left", padx=(14, 0))
        profile_var = tk.StringVar(value="medium_term")
        ttk.Label(header, text="Профиль:").pack(side="left", padx=(28, 6))
        ttk.Combobox(header, textvariable=profile_var, state="readonly", values=("long_term", "medium_term", "speculative"), width=16).pack(side="left")
        status_var = tk.StringVar(value="Готов к анализу")
        ttk.Label(header, textvariable=status_var).pack(side="left", padx=(20, 0))
        run_button = ttk.Button(header, text="Запустить анализ")
        run_button.pack(side="right")

        summary = ttk.LabelFrame(content, text="Итог v0.8.14", padding=12)
        summary.pack(fill="x", pady=(0, 12))
        for i in range(7):
            summary.columnconfigure(i, weight=1)
        summary_vars = {k: tk.StringVar(value="—") for k in ("paths", "adaptive", "validated", "buy", "hold", "rejected", "stat")}
        summary_items = (("paths", "Final Paths"), ("adaptive", "Adaptive"), ("validated", "Validated"), ("buy", "BUY"), ("hold", "NO BUY"), ("rejected", "Rejected"), ("stat", "Stat Integrity"))
        for col, (key, title) in enumerate(summary_items):
            cell = ttk.Frame(summary, padding=6)
            cell.grid(row=0, column=col, sticky="nsew")
            ttk.Label(cell, text=title).pack(anchor="w")
            ttk.Label(cell, textvariable=summary_vars[key], font=("TkDefaultFont", 15, "bold")).pack(anchor="w", pady=(4, 0))

        decision_frame = ttk.LabelFrame(content, text="Финальный результат canonical runtime", padding=14)
        decision_frame.pack(fill="x", pady=(0, 12))
        decision_vars = {k: tk.StringVar(value="—") for k in ("decision", "state", "status", "ev", "risk", "score", "confidence", "reason")}
        ttk.Label(decision_frame, textvariable=decision_vars["decision"], font=("TkDefaultFont", 20, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
        for col, (key, title) in enumerate((("state", "State"), ("status", "Status"), ("ev", "Expected Value"), ("risk", "Risk"), ("score", "Opportunity Score"), ("confidence", "Confidence"))):
            ttk.Label(decision_frame, text=title).grid(row=1, column=col * 2, sticky="w", padx=(0, 6), pady=(10, 3))
            ttk.Label(decision_frame, textvariable=decision_vars[key], font=("TkDefaultFont", 10, "bold")).grid(row=1, column=col * 2 + 1, sticky="w", padx=(0, 18), pady=(10, 3))
        ttk.Label(decision_frame, textvariable=decision_vars["reason"], wraplength=1250, justify="left").grid(row=2, column=0, columnspan=12, sticky="w", pady=(8, 0))
        for col in range(12):
            decision_frame.columnconfigure(col, weight=1)

        context_frame = ttk.LabelFrame(content, text="Market Context — point-in-time", padding=10)
        context_frame.pack(fill="x", pady=(0, 12))
        context_vars = {k: tk.StringVar(value="—") for k in ("status", "benchmark", "regime", "relative", "volatility", "as_of")}
        for col, (key, title) in enumerate((("status", "Context"), ("benchmark", "Benchmark"), ("regime", "Market Regime"), ("relative", "Relative Strength"), ("volatility", "Relative Volatility"), ("as_of", "As Of"))):
            context_frame.columnconfigure(col, weight=1)
            cell = ttk.Frame(context_frame, padding=5)
            cell.grid(row=0, column=col, sticky="nsew")
            ttk.Label(cell, text=title).pack(anchor="w")
            ttk.Label(cell, textvariable=context_vars[key], font=("TkDefaultFont", 10, "bold"), wraplength=200).pack(anchor="w", pady=(3, 0))

        paths_frame = ttk.LabelFrame(content, text="Trading Paths — фактический результат v0.8.14", padding=8)
        paths_frame.pack(fill="both", expand=True, pady=(0, 12))
        columns = ("rank", "source", "path", "train", "excess", "stat", "overlap", "mt", "validation", "ev", "risk", "decision")
        tree = ttk.Treeview(paths_frame, columns=columns, show="headings", height=15)
        headings = (("rank", "#", 45), ("source", "Source", 80), ("path", "Trading Path", 430), ("train", "TRAIN N", 70), ("excess", "Excess", 85), ("stat", "Stat", 70), ("overlap", "Overlap", 80), ("mt", "MT", 60), ("validation", "Validation", 100), ("ev", "OOS EV", 85), ("risk", "Risk", 70), ("decision", "Decision", 90))
        for key, title, width in headings:
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="center" if key != "path" else "w")
        tree.pack(fill="both", expand=True)

        detail_frame = ttk.LabelFrame(content, text="Детализация выбранного пути", padding=10)
        detail_frame.pack(fill="x", pady=(0, 12))
        detail_text = tk.Text(detail_frame, height=18, wrap="word")
        detail_text.pack(fill="x")
        detail_text.configure(state="disabled")

        state: dict[str, Any] = {"results": (), "market_context": None, "candles": []}

        def show_path(index: int) -> None:
            results = state.get("results") or ()
            if index < 0 or index >= len(results):
                return
            item = results[index]
            rule = item
            evidence = item.evidence
            validation = item.validation
            opportunity = item.opportunity
            source = "adaptive" if str(item.strategy_family) == "Adaptive Discovery" or str(item.hypothesis).startswith("ADAPTIVE_RULE:") else "fixed"
            lines = [
                f"Source: {source}",
                f"Strategy Family: {_value(item.strategy_family)}",
                f"Trading Path: {item.hypothesis}",
                f"Regime: {item.regime} | Volatility: {item.volatility_bucket} | Direction: {item.direction} | Horizon: H={item.horizon}",
                "",
                "TRAIN / DISCOVERY EVIDENCE",
                f"Observations: {_field(evidence, 'observations')}",
                f"Mean: {_fmt_pct(_field(evidence, 'mean_forward_return_pct'))}",
                f"Median: {_fmt_pct(_field(evidence, 'median_forward_return_pct'))}",
                f"Win Rate: {_fmt_pct(_field(evidence, 'win_rate_pct'))}",
                f"Baseline: {_fmt_pct(_field(evidence, 'baseline_mean_return_pct'))}",
                f"Excess: {_fmt_pct(_field(evidence, 'excess_return_pct'))}",
                "",
                "STATISTICAL INTEGRITY",
                f"Statistically valid: {_fmt_bool(_field(validation, 'statistical_valid'))}",
                f"Overlap valid: {_fmt_bool(_field(validation, 'overlap_valid'))} | Overlap: {_fmt_pct(_field(validation, 'overlap_ratio_pct'))}",
                f"Multiple testing valid: {_fmt_bool(_field(validation, 'multiple_testing_valid'))}",
                f"Effective N: {_fmt_num(_field(validation, 'effective_sample_size'))}",
                f"SE: {_fmt_pct(_field(validation, 'standard_error_pct'))} | Z: {_fmt_num(_field(validation, 'z_score'), 4)}",
                f"p-value: {_fmt_num(_field(validation, 'p_value_one_sided'), 6)} | adjusted p: {_fmt_num(_field(validation, 'adjusted_p_value'), 6)}",
                f"Hypotheses tested: {_field(validation, 'hypotheses_tested')}",
                "",
                "VALIDATION / OOS / DECISION",
                f"Validation status: {_value(_field(validation, 'promotion_status'))}",
                f"WF persistence: {_fmt_pct(_field(validation, 'wf_persistence_pct'))}",
                f"Robustness: {_fmt_num(_field(validation, 'robustness_score'))}",
                f"Positive OOS windows: {_fmt_pct(_field(validation, 'positive_oos_windows_pct'))}",
                f"Expected Value: {_fmt_pct(_field(opportunity, 'expected_value_pct'))}",
                f"Risk score: {_fmt_num(_field(opportunity, 'risk_score'))}",
                f"Opportunity score: {_fmt_num(_field(opportunity, 'score'))}",
                f"Confidence: {_fmt_pct(_field(opportunity, 'confidence'))}",
                f"Current state: {_value(item.current_state)} | Decision: {_value(item.decision)} | Status: {_value(item.status)}",
            ]
            if source == "adaptive":
                lines.insert(3, "Adaptive rule is shown exactly as produced by TRAIN discovery.")
            detail_text.configure(state="normal")
            detail_text.delete("1.0", "end")
            detail_text.insert("1.0", "\n".join(lines))
            detail_text.configure(state="disabled")

        def populate(results: tuple[Any, ...]) -> None:
            state["results"] = results
            for item in tree.get_children():
                tree.delete(item)
            buy_count = sum(str(_value(item.decision, "")).lower() == "buy" for item in results)
            adaptive_count = sum(str(item.strategy_family) == "Adaptive Discovery" or str(item.hypothesis).startswith("ADAPTIVE_RULE:") for item in results)
            stat_valid_count = sum(_field(item.validation, "statistical_valid") is True for item in results)
            summary_vars["paths"].set(str(len(results)))
            summary_vars["adaptive"].set(str(adaptive_count))
            summary_vars["validated"].set(str(sum(_value(item.validation.promotion_status) == "validated" for item in results)))
            summary_vars["buy"].set(str(buy_count))
            summary_vars["hold"].set(str(len(results) - buy_count))
            summary_vars["rejected"].set("0 — final only")
            summary_vars["stat"].set(f"{stat_valid_count}/{len(results)} PASS" if results else "N/A")

            for idx, item in enumerate(results):
                evidence = item.evidence
                validation = item.validation
                opportunity = item.opportunity
                source = "adaptive" if str(item.strategy_family) == "Adaptive Discovery" or str(item.hypothesis).startswith("ADAPTIVE_RULE:") else "fixed"
                path = f"{item.hypothesis} | {item.regime} | {item.volatility_bucket} | {item.direction} | H={item.horizon}"
                tree.insert("", "end", iid=str(idx), values=(
                    item.rank,
                    source,
                    path,
                    _field(evidence, "observations", "N/A"),
                    _fmt_pct(_field(evidence, "excess_return_pct")),
                    _fmt_bool(_field(validation, "statistical_valid")),
                    _fmt_pct(_field(validation, "overlap_ratio_pct")),
                    _fmt_bool(_field(validation, "multiple_testing_valid")),
                    _value(_field(validation, "promotion_status")),
                    _fmt_pct(_field(opportunity, "expected_value_pct")),
                    _fmt_num(_field(opportunity, "risk_score")),
                    str(_value(item.decision)),
                ))

            if results:
                tree.selection_set("0")
                tree.focus("0")
                show_path(0)
                best = results[0]
                opportunity = best.opportunity
                decision_vars["decision"].set(f"Решение: {str(_value(best.decision)).upper()}")
                decision_vars["state"].set(str(_value(best.current_state)))
                decision_vars["status"].set(str(_value(best.status)))
                decision_vars["ev"].set(_fmt_pct(_field(opportunity, "expected_value_pct")))
                decision_vars["risk"].set(_fmt_num(_field(opportunity, "risk_score")))
                decision_vars["score"].set(_fmt_num(_field(opportunity, "score")))
                decision_vars["confidence"].set(_fmt_pct(_field(opportunity, "confidence")))
                decision_vars["reason"].set("Итог сформирован canonical v0.8.14 runtime; решение не создаётся отдельно от этого pipeline.")
            else:
                decision_vars["decision"].set("Решение: NO VALIDATED PATH")
                decision_vars["reason"].set("После TRAIN discovery → validation → OOS → Quality Gate финальных путей нет.")

        def populate_market_context(benchmark: Any, snapshot: Any) -> None:
            state["market_context"] = snapshot
            context_vars["status"].set(_field(snapshot, "context_status", "UNAVAILABLE"))
            context_vars["benchmark"].set(f"{_field(benchmark, 'benchmark_id', 'N/A')} / {_field(benchmark, 'benchmark_kind', 'N/A')}")
            regime_result = _field(_field(snapshot, "market_regime"), "result")
            context_vars["regime"].set(str(_field(regime_result, "regime", "UNAVAILABLE")))
            relative = _field(snapshot, "relative_strength")
            context_vars["relative"].set(f"{_field(relative, 'classification', 'UNAVAILABLE')} ({_fmt_pct(_field(relative, 'excess_return_pct'))})")
            volatility = _field(snapshot, "volatility")
            relative_vol = _field(volatility, "relative_volatility")
            context_vars["volatility"].set(f"{_field(volatility, 'classification', 'UNAVAILABLE')} ({_fmt_num(relative_vol, 2)}x)" if relative_vol is not None else "UNAVAILABLE")
            context_vars["as_of"].set(str(_field(snapshot, "as_of", "N/A")))

        def on_select(_event: Any) -> None:
            selected = tree.selection()
            if selected:
                show_path(int(selected[0]))

        tree.bind("<<TreeviewSelect>>", on_select)

        def set_running(value: bool) -> None:
            run_button.configure(state="disabled" if value else "normal")
            status_var.set("Выполнение canonical v0.8.14…" if value else "Готово")

        def run() -> None:
            set_running(True)
            try:
                response = app.client.get_candles(uid, interval="CANDLE_INTERVAL_DAY", days=2400)
                candles = _parse_candles(response)
                if not candles:
                    raise RuntimeError("Исторические свечи не получены")
                state["candles"] = candles

                metadata = _unwrap_instrument(app.client.get_instrument(uid))
                if not _field(metadata, "instrument_type"):
                    metadata = dict(detail)
                    metadata["instrument_type"] = detail.get("instrument_kind", "SHARE")
                if not _field(metadata, "instrument_uid") and isinstance(metadata, dict):
                    metadata["instrument_uid"] = uid

                try:
                    market_service = MarketContextRuntimeServiceV011(fetcher=app.client.get_candles, indicatives_fetcher=app.client.get_indicatives, find_instrument_fetcher=app.client.find_instrument)
                    benchmark, snapshot = market_service.build(instrument_metadata=metadata, asset_candles=candles, as_of=max(candle.timestamp for candle in candles))
                    populate_market_context(benchmark, snapshot)
                except Exception as exc:
                    logger.warning("[V014 UI] market context unavailable ticker=%s error=%s", ticker, exc)
                    context_vars["status"].set("UNAVAILABLE — path analysis continues")

                runtime = AnalysisPathRuntimeServiceV012()
                results = runtime.analyze_paths(instrument_uid=uid, ticker=ticker, candles=candles, profile=profile_var.get())
                populate(results)
                status_var.set(f"v0.8.14 завершён: {len(results)} финальных Trading Paths")
                logger.warning("[V014 UI] ticker=%s final_paths=%d adaptive=%d", ticker, len(results), sum(str(x.strategy_family) == "Adaptive Discovery" for x in results))
            except Exception as exc:
                status_var.set("Ошибка canonical анализа")
                logger.exception("[V014 UI] ticker=%s canonical runtime failed", ticker)
                messagebox.showerror("Анализ v0.8.14", str(exc))
            finally:
                set_running(False)

        run_button.configure(command=run)
        run()

    legacy._open_analysis = open_analysis
    app_class._analysis_ui_v088_frontend_installed = True


__all__ = ["install"]
