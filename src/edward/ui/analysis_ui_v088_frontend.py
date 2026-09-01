from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088
from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011
from edward.storage.sqlite_store import SQLiteStore
from edward.config.application_settings import ApplicationSettingsStore

logger = logging.getLogger(__name__)


def _parse_candles(response: Any) -> list[Any]:
    from edward.ui.analysis_ui_v04 import _parse_candles
    return _parse_candles(response)


def _status_text(status: Any) -> str:
    value = getattr(status, "value", status)
    return {
        "promoted": "PROMOTED",
        "research_only": "RESEARCH ONLY",
        "rejected": "REJECTED",
    }.get(str(value), str(value).upper())


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_ratio(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "N/A"


def _unwrap_instrument(response: Any) -> Any:
    if isinstance(response, (list, tuple)):
        return response[0] if response else {}
    if isinstance(response, dict):
        for key in ("instrument", "item", "instrument_info"):
            if response.get(key) is not None:
                value = response[key]
                if isinstance(value, (list, tuple)):
                    return value[0] if value else {}
                return value
    return response


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def install(app_class: type[Any], client_class: type[Any]) -> None:
    import edward.ui.analysis_ui_v04 as legacy

    if getattr(app_class, "_analysis_ui_v088_frontend_installed", False):
        return

    def open_analysis(app: Any) -> None:
        detail = getattr(app, "instrument_detail", None)
        if not detail:
            return

        window = tk.Toplevel(app)
        ticker = str(detail.get("ticker", ""))
        window.title(f"Анализ акции v0.8.8 — {ticker}")
        window.geometry("1350x980")
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
        ttk.Label(header, text="v0.8.8 Trading Paths + v0.8.11 Market Context", font=("TkDefaultFont", 12, "bold")).pack(side="left", padx=(14, 0))
        profile_var = tk.StringVar(value="medium_term")
        ttk.Label(header, text="Профиль:").pack(side="left", padx=(28, 6))
        ttk.Combobox(header, textvariable=profile_var, state="readonly", values=("long_term", "medium_term", "speculative"), width=16).pack(side="left")
        status_var = tk.StringVar(value="Готов к анализу")
        ttk.Label(header, textvariable=status_var).pack(side="left", padx=(20, 0))
        run_button = ttk.Button(header, text="Запустить анализ")
        run_button.pack(side="right")

        summary = ttk.LabelFrame(content, text="Итог анализа", padding=12)
        summary.pack(fill="x", pady=(0, 12))
        for i in range(6):
            summary.columnconfigure(i, weight=1)
        summary_vars = {k: tk.StringVar(value="—") for k in ("legacy", "candidates", "validated", "promoted", "research", "rejected")}
        summary_items = (
            ("legacy", "Legacy QG"),
            ("candidates", "Trading Paths"),
            ("validated", "Validated"),
            ("promoted", "Promoted"),
            ("research", "Research Only"),
            ("rejected", "Rejected"),
        )
        for col, (key, title) in enumerate(summary_items):
            cell = ttk.Frame(summary, padding=6)
            cell.grid(row=0, column=col, sticky="nsew")
            ttk.Label(cell, text=title).pack(anchor="w")
            ttk.Label(cell, textvariable=summary_vars[key], font=("TkDefaultFont", 15, "bold")).pack(anchor="w", pady=(4, 0))

        context_frame = ttk.LabelFrame(content, text="v0.8.11 Market Context — point-in-time evidence", padding=10)
        context_frame.pack(fill="x", pady=(0, 12))
        for col in range(6):
            context_frame.columnconfigure(col, weight=1)
        context_vars = {k: tk.StringVar(value="—") for k in ("status", "benchmark", "regime", "relative", "volatility", "as_of")}
        context_items = (
            ("status", "Context"),
            ("benchmark", "Benchmark"),
            ("regime", "Market Regime"),
            ("relative", "Relative Strength"),
            ("volatility", "Relative Volatility"),
            ("as_of", "As Of"),
        )
        for col, (key, title) in enumerate(context_items):
            cell = ttk.Frame(context_frame, padding=5)
            cell.grid(row=0, column=col, sticky="nsew")
            ttk.Label(cell, text=title).pack(anchor="w")
            ttk.Label(cell, textvariable=context_vars[key], font=("TkDefaultFont", 10, "bold"), wraplength=190).pack(anchor="w", pady=(3, 0))

        best_frame = ttk.LabelFrame(content, text="Лучший исследованный путь", padding=12)
        best_frame.pack(fill="x", pady=(0, 12))
        best_vars = {k: tk.StringVar(value="—") for k in ("path", "status", "net", "mean", "ci", "blocks", "overlap", "reason")}
        ttk.Label(best_frame, textvariable=best_vars["path"], font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
        for row, (key, label) in enumerate((("status", "Статус"), ("net", "Net Return"), ("mean", "Mean"), ("ci", "Adjusted CI"), ("blocks", "Temporal"), ("overlap", "Overlap"))):
            r, c = divmod(row, 3)
            ttk.Label(best_frame, text=label).grid(row=r + 1, column=c * 2, sticky="w", padx=(0, 6), pady=4)
            ttk.Label(best_frame, textvariable=best_vars[key], font=("TkDefaultFont", 10, "bold")).grid(row=r + 1, column=c * 2 + 1, sticky="w", padx=(0, 18), pady=4)
        ttk.Label(best_frame, textvariable=best_vars["reason"], wraplength=1200, justify="left").grid(row=3, column=0, columnspan=6, sticky="w", pady=(6, 0))
        for c in range(6):
            best_frame.columnconfigure(c, weight=1)

        paths_frame = ttk.LabelFrame(content, text="Trading Paths — результат проверки", padding=8)
        paths_frame.pack(fill="both", expand=True, pady=(0, 12))
        columns = ("rank", "path", "n", "net", "mean", "ci", "temporal", "event", "holding", "multiple", "status")
        tree = ttk.Treeview(paths_frame, columns=columns, show="headings", height=14)
        headings = (
            ("rank", "#", 45), ("path", "Trading Path", 340), ("n", "N", 55),
            ("net", "Net %", 90), ("mean", "Mean %", 90), ("ci", "Adjusted CI95", 150),
            ("temporal", "Temporal", 80), ("event", "Event", 75), ("holding", "Holding", 75),
            ("multiple", "MT", 65), ("status", "Статус", 125),
        )
        for key, title, width in headings:
            tree.heading(key, text=title)
            tree.column(key, width=width, anchor="center" if key != "path" else "w")
        tree.pack(fill="both", expand=True)

        detail_frame = ttk.LabelFrame(content, text="Детализация выбранного Trading Path", padding=10)
        detail_frame.pack(fill="x", pady=(0, 12))
        detail_text = tk.Text(detail_frame, height=10, wrap="word")
        detail_text.pack(fill="x")
        detail_text.configure(state="disabled")

        legacy_frame = ttk.LabelFrame(content, text="Legacy v0.8.7 — стратегии / Quality Gate", padding=8)
        legacy_frame.pack(fill="x")
        legacy_tree = ttk.Treeview(legacy_frame, columns=("strategy", "score", "return", "dd", "sharpe", "robust", "gate"), show="headings", height=4)
        for key, title, width in (("strategy", "Стратегия", 190), ("score", "Score", 80), ("return", "OOS Return %", 110), ("dd", "OOS DD %", 100), ("sharpe", "Sharpe", 80), ("robust", "Robustness", 110), ("gate", "Quality Gate", 110)):
            legacy_tree.heading(key, text=title)
            legacy_tree.column(key, width=width, anchor="center")
        legacy_tree.pack(fill="x")

        state: dict[str, Any] = {"research": None, "market_context": None}

        def show_path(index: int) -> None:
            research = state.get("research")
            if research is None or index < 0 or index >= len(research.ranked_candidates):
                return
            ranked = research.ranked_candidates[index]
            validation = research.validation_results[index]
            overlap = research.overlap_evidence[index]
            multiple = research.multiple_testing_evidence[index]
            promotion = research.promotion_results[index]
            rule = ranked.candidate.rule
            evidence = validation.statistical_evidence
            temporal = validation.temporal_evidence
            path = f"{rule.hypothesis} / {rule.regime} / {rule.volatility_bucket} / {rule.direction} / H={rule.horizon}"
            temporal_text = f"{evidence.positive_temporal_blocks}/{len(evidence.temporal_blocks)} positive blocks"
            reason_text = ", ".join(promotion.reasons) if promotion.reasons else "NONE — all promotion checks passed"
            lines = (
                f"Trading Path: {path}",
                f"Ranking score: {ranked.score:.6f}",
                f"Observations: {evidence.observations}",
                f"Gross Return: {_fmt_pct(validation.gross_return_pct)} | Net Return: {_fmt_pct(validation.net_return_pct)}",
                f"Mean: {_fmt_pct(evidence.mean_return_pct)} | Median: {_fmt_pct(evidence.median_return_pct)} | Win Rate: {evidence.win_rate_pct:.1f}%",
                f"CI95: {_fmt_pct(evidence.ci95_low_pct)} → {_fmt_pct(evidence.ci95_high_pct)}",
                f"Adjusted CI95: {_fmt_pct(multiple.adjusted_ci95_low_pct)} → {_fmt_pct(multiple.adjusted_ci95_high_pct)}",
                f"Temporal: {temporal_text} | Stable: {'YES' if getattr(temporal, 'temporal_stable', False) else 'NO'}",
                f"Overlap: event={_fmt_ratio(overlap.max_event_overlap_ratio)}, holding={_fmt_ratio(overlap.max_holding_overlap_ratio)}",
                f"Multiple testing: {multiple.tests_count} tests | adjusted alpha={multiple.adjusted_alpha:.6f} | PASS={'YES' if multiple.passes else 'NO'}",
                f"Promotion: {_status_text(promotion.status)}",
                f"Blocking reasons: {reason_text}",
            )
            detail_text.configure(state="normal")
            detail_text.delete("1.0", "end")
            detail_text.insert("1.0", "\n".join(lines))
            detail_text.configure(state="disabled")

        def populate(research: Any) -> None:
            state["research"] = research
            for item in tree.get_children():
                tree.delete(item)
            for item in legacy_tree.get_children():
                legacy_tree.delete(item)
            legacy_result = research.analysis
            passed = sum(1 for item in legacy_result.strategies if item.quality_gate)
            summary_vars["legacy"].set(f"{passed}/{len(legacy_result.strategies)} PASS")
            summary_vars["candidates"].set(str(len(research.ranked_candidates)))
            summary_vars["validated"].set(str(len(research.validation_results)))
            statuses = [getattr(item.status, "value", item.status) for item in research.promotion_results]
            summary_vars["promoted"].set(str(statuses.count("promoted")))
            summary_vars["research"].set(str(statuses.count("research_only")))
            summary_vars["rejected"].set(str(statuses.count("rejected")))
            for idx, ranked in enumerate(research.ranked_candidates):
                result = research.validation_results[idx]
                overlap = research.overlap_evidence[idx]
                multiple = research.multiple_testing_evidence[idx]
                promotion = research.promotion_results[idx]
                rule = ranked.candidate.rule
                evidence = result.statistical_evidence
                temporal = result.temporal_evidence
                path = f"{rule.hypothesis} | {rule.regime} | {rule.volatility_bucket} | {rule.direction} | H={rule.horizon}"
                ci = f"{multiple.adjusted_ci95_low_pct:+.2f}…{multiple.adjusted_ci95_high_pct:+.2f}%"
                tree.insert("", "end", iid=str(idx), values=(idx + 1, path, evidence.observations, _fmt_pct(result.net_return_pct), _fmt_pct(evidence.mean_return_pct), ci, f"{evidence.positive_temporal_blocks}/{len(evidence.temporal_blocks)}", _fmt_ratio(overlap.max_event_overlap_ratio), _fmt_ratio(overlap.max_holding_overlap_ratio), "PASS" if multiple.passes else "FAIL", _status_text(promotion.status)))
            for item in legacy_result.strategies:
                legacy_tree.insert("", "end", values=(item.strategy, f"{item.score:.1f}", f"{item.return_pct:.2f}", f"{item.max_drawdown_pct:.2f}", f"{item.sharpe:.2f}", f"{item.stability:.1f}", "PASS" if item.quality_gate else "FAIL"))
            if research.ranked_candidates:
                tree.selection_set("0")
                tree.focus("0")
                show_path(0)
                ranked = research.ranked_candidates[0]
                best_result = research.validation_results[0]
                best_overlap = research.overlap_evidence[0]
                best_multiple = research.multiple_testing_evidence[0]
                best_promotion = research.promotion_results[0]
                rule = ranked.candidate.rule
                best_vars["path"].set(f"{rule.hypothesis} / {rule.regime} / {rule.volatility_bucket} / {rule.direction} / H={rule.horizon} | score {ranked.score:.4f}")
                best_vars["status"].set(_status_text(best_promotion.status))
                best_vars["net"].set(_fmt_pct(best_result.net_return_pct))
                best_vars["mean"].set(_fmt_pct(best_result.statistical_evidence.mean_return_pct))
                best_vars["ci"].set(f"{best_multiple.adjusted_ci95_low_pct:+.2f}% → {best_multiple.adjusted_ci95_high_pct:+.2f}%")
                best_vars["blocks"].set(f"{best_result.statistical_evidence.positive_temporal_blocks}/{len(best_result.statistical_evidence.temporal_blocks)}")
                best_vars["overlap"].set(f"E {_fmt_ratio(best_overlap.max_event_overlap_ratio)} / H {_fmt_ratio(best_overlap.max_holding_overlap_ratio)}")
                best_vars["reason"].set("Причины: " + (", ".join(best_promotion.reasons) if best_promotion.reasons else "нет — все проверки пройдены"))
            else:
                best_vars["path"].set("Trading Paths не найдены")
                best_vars["status"].set("NO RESEARCH PATH")
                best_vars["reason"].set("Conditional Discovery не предоставил кандидатов.")

        def populate_market_context(benchmark: Any, snapshot: Any) -> None:
            state["market_context"] = snapshot
            context_vars["status"].set(snapshot.context_status)
            context_vars["benchmark"].set(f"{benchmark.benchmark_id} / {benchmark.benchmark_kind}")
            regime_result = getattr(snapshot.market_regime, "result", None)
            context_vars["regime"].set(str(getattr(regime_result, "regime", regime_result or "UNAVAILABLE")))
            relative = snapshot.relative_strength
            context_vars["relative"].set(
                f"{getattr(relative, 'classification', 'UNAVAILABLE')} ({_fmt_pct(getattr(relative, 'excess_return_pct', None))})"
            )
            volatility = snapshot.volatility
            relative_vol = getattr(volatility, "relative_volatility", None)
            context_vars["volatility"].set(
                f"{getattr(volatility, 'classification', 'UNAVAILABLE')} ({relative_vol:.2f}x)" if relative_vol is not None else "UNAVAILABLE"
            )
            context_vars["as_of"].set(str(snapshot.as_of))
            logger.warning(
                "[V011 MARKET CONTEXT] ticker=%s benchmark=%s status=%s regime=%s relative=%s excess=%s volatility=%s relative_volatility=%s as_of=%s",
                ticker,
                benchmark.benchmark_id,
                snapshot.context_status,
                getattr(regime_result, "regime", "UNAVAILABLE"),
                getattr(relative, "classification", "UNAVAILABLE"),
                getattr(relative, "excess_return_pct", None),
                getattr(volatility, "classification", "UNAVAILABLE"),
                relative_vol,
                snapshot.as_of,
            )

        def on_select(_event: Any) -> None:
            selected = tree.selection()
            if selected:
                show_path(int(selected[0]))

        tree.bind("<<TreeviewSelect>>", on_select)

        def set_running(value: bool) -> None:
            run_button.configure(state="disabled" if value else "normal")
            status_var.set("Выполнение v0.8.11 + v0.8.8…" if value else "Готово")

        def run() -> None:
            set_running(True)
            try:
                uid = str(detail["instrument_uid"])
                response = app.client.get_candles(uid, interval="CANDLE_INTERVAL_DAY", days=2400)
                candles = _parse_candles(response)
                if not candles:
                    raise RuntimeError("Исторические свечи не получены")

                metadata = _unwrap_instrument(app.client.get_instrument(uid))
                if not _field(metadata, "instrument_type", None):
                    metadata = dict(detail)
                    metadata["instrument_type"] = detail.get("instrument_kind", "SHARE")
                if not _field(metadata, "instrument_uid", None):
                    if isinstance(metadata, dict):
                        metadata["instrument_uid"] = uid

                market_service = MarketContextRuntimeServiceV011(
                    fetcher=app.client.get_candles,
                    indicatives_fetcher=app.client.get_indicatives,
                    find_instrument_fetcher=app.client.find_instrument,
                )
                benchmark, snapshot = market_service.build(
                    instrument_metadata=metadata,
                    asset_candles=candles,
                    as_of=max(candle.timestamp for candle in candles),
                )
                populate_market_context(benchmark, snapshot)

                service = AnalysisServiceV08()
                adapter = AnalysisTradingPathAdapterV088(service)
                research = adapter.analyze(instrument_uid=uid, ticker=ticker, candles=candles, profile=profile_var.get())
                try:
                    settings = ApplicationSettingsStore().load()
                    SQLiteStore(settings.storage_path)
                except Exception:
                    pass
                populate(research)
                status_var.set("v0.8.11 context + v0.8.8 анализ завершены")
                logger.warning("[V088 UI] ticker=%s candidates=%d validated=%d promoted=%d research_only=%d rejected=%d", ticker, len(research.ranked_candidates), len(research.validation_results), sum(getattr(x.status, 'value', x.status) == 'promoted' for x in research.promotion_results), sum(getattr(x.status, 'value', x.status) == 'research_only' for x in research.promotion_results), sum(getattr(x.status, 'value', x.status) == 'rejected' for x in research.promotion_results))
            except Exception as exc:
                status_var.set("Ошибка анализа")
                logger.exception("[V011 UI] ticker=%s market-context integration failed", ticker)
                tk.messagebox.showerror("Анализ v0.8.11", str(exc))
            finally:
                set_running(False)

        run_button.configure(command=lambda: run())
        run()

    legacy._open_analysis = open_analysis
    app_class._analysis_ui_v088_frontend_installed = True


__all__ = ["install"]
