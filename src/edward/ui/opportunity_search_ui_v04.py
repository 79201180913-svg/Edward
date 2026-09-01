from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.opportunity_search_service import INSTRUMENT_KIND_ALL, MARKET_SCOPE, PORTFOLIO_SCOPE
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService

SCOPE_VALUES = ((MARKET_SCOPE, "Торгуемые инструменты"), (PORTFOLIO_SCOPE, "Мой портфель"))
SCOPE_BY_LABEL = {label: code for code, label in SCOPE_VALUES}
PROFILE_VALUES = (("long_term", "Долгосрочная"), ("medium_term", "Среднесрочная"), ("speculative", "Спекулятивная"))
PROFILE_BY_LABEL = {label: code for code, label in PROFILE_VALUES}
KIND_LABELS = {"SHARE": "Акции", "BOND": "Облигации", "ETF": "Фонды ETF", "CURRENCY": "Валюты", "FUTURES": "Фьючерсы", "OPTION": "Опционы"}
KIND_BY_LABEL = {label: code for code, label in KIND_LABELS.items()}
DECISION_LABELS = {"BUY": "Купить", "WAIT": "Ждать", "PASS": "Пропустить"}
FILTER_VALUES = ("ALL", "BUY", "WAIT", "PASS")
FILTER_LABELS = ("Все", "Купить", "Ждать", "Пропустить")
FILTER_CODE_BY_LABEL = dict(zip(FILTER_LABELS, FILTER_VALUES))
STATUS_LABELS = {"PROMOTED": "Продвинут", "PROMOTABLE": "Кандидат", "VALIDATED": "Валидирован", "RESEARCH_ONLY": "Исследование", "REJECTED": "Отклонён", "ANALYSIS_UNAVAILABLE": "Нет анализа"}


def _value(value: Any, default: str = "—") -> Any:
    if value is None: return default
    return getattr(value, "value", value)


def _fmt(value: Any, suffix: str = "", digits: int = 1) -> str:
    if value is None: return "—"
    try: return f"{float(value):.{digits}f}{suffix}"
    except Exception: return str(value)


def _bool(value: Any) -> str:
    if value is None: return "—"
    return "PASS" if bool(value) else "FAIL"


def install_opportunity_search_ui(app_class: type[Any]) -> None:
    if getattr(app_class, "_opportunity_search_ui_v04_installed", False): return
    original_shell = app_class._shell

    def shell(self: Any) -> None:
        original_shell(self)
        if hasattr(self, "nav") and not getattr(self, "_opportunity_nav_added_v04", False):
            ttk.Button(self.nav, text="Возможности", style="Nav.TButton", command=lambda: self.show_page("opportunities")).pack(fill="x", pady=2)
            self._opportunity_nav_added_v04 = True

    def page_opportunities(self: Any) -> None:
        frame = ttk.Frame(self.content); frame.pack(fill="both", expand=True)
        title_var = tk.StringVar(value="Возможности рынка")
        status_var = tk.StringVar(value="Готово")
        progress_var = tk.DoubleVar(value=0.0)
        progress_text_var = tk.StringVar(value="Готово")
        scope_var = tk.StringVar(value="Торгуемые инструменты")
        profile_var = tk.StringVar(value="Среднесрочная")
        kind_var = tk.StringVar(value="Акции")
        decision_var = tk.StringVar(value="Все")
        detail_var = tk.StringVar(value="Выберите инструмент, чтобы увидеть итоговый Trading Path и решение.")
        summary_var = tk.StringVar(value="Покупка: 0   Ждать: 0   Пропустить: 0   Путей: 0")

        top = ttk.Frame(frame); top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, textvariable=title_var, style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="Область:").pack(side="left", padx=(25, 5))
        scope_combo = ttk.Combobox(top, textvariable=scope_var, state="readonly", values=[x[1] for x in SCOPE_VALUES], width=20); scope_combo.pack(side="left")
        ttk.Label(top, text="Профиль:").pack(side="left", padx=(15, 5))
        profile_combo = ttk.Combobox(top, textvariable=profile_var, state="readonly", values=[x[1] for x in PROFILE_VALUES], width=16); profile_combo.pack(side="left")
        ttk.Label(top, text="Инструмент:").pack(side="left", padx=(15, 5))
        kind_combo = ttk.Combobox(top, textvariable=kind_var, state="readonly", values=["Все"] + list(KIND_LABELS.values()), width=16); kind_combo.pack(side="left")
        ttk.Label(top, textvariable=status_var, width=11).pack(side="left", padx=8)
        scan_button = ttk.Button(top, text="Сканировать", width=13); scan_button.pack(side="right")

        progress_frame = ttk.Frame(frame); progress_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(progress_frame, textvariable=progress_text_var).pack(anchor="w", pady=(0, 4))
        ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate", maximum=100.0, variable=progress_var).pack(fill="x")

        filter_frame = ttk.Frame(frame); filter_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(filter_frame, text="Фильтр решения:").pack(side="left")
        filter_combo = ttk.Combobox(filter_frame, textvariable=decision_var, state="readonly", values=FILTER_LABELS, width=15); filter_combo.pack(side="left", padx=6)

        columns = ("ticker", "decision", "path", "status", "score", "confidence", "ev", "risk", "regime", "validation", "market", "paths")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=17); tree.pack(fill="both", expand=True)
        headers = (
            ("ticker", "Инструмент", 105), ("decision", "Решение", 95), ("path", "Лучший Trading Path", 220),
            ("status", "Статус", 110), ("score", "Opportunity", 100), ("confidence", "Confidence", 95),
            ("ev", "Expected Value", 105), ("risk", "Risk", 80), ("regime", "Regime", 100),
            ("validation", "Validation", 220), ("market", "Market Context", 125), ("paths", "Paths", 90),
        )
        for key, label, width in headers:
            tree.heading(key, text=label); tree.column(key, width=width, anchor="w" if key in {"ticker", "path", "validation", "market"} else "center")

        detail_frame = ttk.LabelFrame(frame, text="Итоговый анализ инструмента")
        detail_frame.pack(fill="x", pady=(8, 0))
        ttk.Label(detail_frame, textvariable=detail_var, justify="left", anchor="w").pack(fill="x", padx=8, pady=8)
        ttk.Label(frame, textvariable=summary_var).pack(anchor="w", pady=(8, 0))
        state: dict[str, Any] = {"results": []}

        def scope_code() -> str: return SCOPE_BY_LABEL.get(scope_var.get(), MARKET_SCOPE)
        def profile_code() -> str: return PROFILE_BY_LABEL.get(profile_var.get(), "medium_term")
        def kind_code() -> str: return INSTRUMENT_KIND_ALL if kind_var.get() == "Все" else KIND_BY_LABEL.get(kind_var.get(), "SHARE")
        def decision_code() -> str: return FILTER_CODE_BY_LABEL.get(decision_var.get(), "ALL")

        def path_for(item: Any) -> Any: return getattr(getattr(item, "canonical_opportunity", None), "best_path", None)

        def row_values(item: Any) -> tuple[str, ...]:
            path = path_for(item)
            if path is None:
                return (item.ticker, "—", "—", "Нет анализа", "—", "—", "—", "—", "—", "—", "—", "—")
            validation = path.validation; market = path.market_context; opp = path.opportunity; canonical = item.canonical_opportunity
            validation_text = f"WF {_fmt(validation.wf_persistence_pct, '%')} · OOS {_fmt(validation.positive_oos_windows_pct, '%')} · Stat {_bool(validation.statistical_valid)} · MT {_bool(validation.multiple_testing_valid)}"
            market_text = f"rank {_value(market.context_rank)} · Δ {_value(market.rank_delta)}"
            path_text = f"{path.hypothesis} / {path.regime} / {path.volatility_bucket} / {path.direction} / H={path.horizon}"
            return (
                item.ticker, _value(item.decision, "—").upper(), path_text,
                str(_value(path.status, "—")).upper(), _fmt(opp.score), _fmt(opp.confidence, '%'),
                _fmt(opp.expected_value_pct, '%', 2), _fmt(opp.risk_score), str(path.regime),
                validation_text, market_text,
                f"{canonical.total_paths} / P{canonical.promoted_paths} / R{canonical.research_only_paths} / X{canonical.rejected_paths}",
            )

        def show_detail(item: Any | None) -> None:
            if item is None: detail_var.set("Выберите инструмент, чтобы увидеть итоговый Trading Path и решение."); return
            path = path_for(item); canonical = getattr(item, "canonical_opportunity", None)
            if path is None or canonical is None: detail_var.set(f"{item.ticker}\nРешение: {item.decision or '—'}\nПричина: {item.reason or '—'}"); return
            v = path.validation; m = path.market_context; o = path.opportunity
            decision = str(_value(canonical.decision, "—")).upper()
            detail_var.set("\n".join((
                f"{item.ticker}  →  ФИНАЛЬНОЕ РЕШЕНИЕ: {decision}",
                f"Trading Path: {path.hypothesis} | {path.regime} | {path.volatility_bucket} | {path.direction} | H={path.horizon}",
                f"Status: {_value(path.status)} | State: {_value(canonical.current_state)} | Rank: {path.rank or '—'}",
                f"Opportunity: {_fmt(o.score)} | Confidence: {_fmt(o.confidence, '%')} | Expected Value: {_fmt(o.expected_value_pct, '%', 2)} | Risk: {_fmt(o.risk_score)} | Risk Gate: {_bool(o.risk_gate)}",
                f"Validation: WF {_fmt(v.wf_persistence_pct, '%')} | Robustness {_fmt(v.robustness_score)} | OOS {_fmt(v.positive_oos_windows_pct, '%')} | Statistical {_bool(v.statistical_valid)} | Overlap {_bool(v.overlap_valid)} | Multiple Testing {_bool(v.multiple_testing_valid)}",
                f"Market Context: benchmark {_value(m.benchmark_id)} | baseline rank {_value(m.baseline_rank)} | context rank {_value(m.context_rank)} | Δ rank {_value(m.rank_delta)} | RS {_fmt(m.relative_strength_component)} | Vol {_fmt(m.volatility_component)}",
                f"Paths: total {canonical.total_paths} | promoted {canonical.promoted_paths} | research-only {canonical.research_only_paths} | rejected {canonical.rejected_paths}",
                f"Причина: {item.reason or '—'}",
            )))

        def render() -> None:
            for row in tree.get_children(): tree.delete(row)
            selected = decision_code()
            for item in state["results"]:
                if selected != "ALL" and (item.decision or "PASS") != selected: continue
                tree.insert("", "end", values=row_values(item))
            buy = sum(1 for x in state["results"] if x.decision == "BUY"); wait = sum(1 for x in state["results"] if x.decision == "WAIT"); passed = sum(1 for x in state["results"] if x.decision == "PASS"); paths = sum(getattr(getattr(x, "canonical_opportunity", None), "total_paths", 0) for x in state["results"])
            summary_var.set(f"Покупка: {buy}   Ждать: {wait}   Пропустить: {passed}   Путей: {paths}")

        def update_progress(stage: str, percent: float, current: int, total: int) -> None:
            progress_var.set(percent); suffix = f" ({current}/{total})" if total else ""; progress_text_var.set(f"{stage} — {percent:.0f}%{suffix}"); status_var.set("Выполняется")

        def scan() -> None:
            scan_button.configure(state="disabled"); state["results"] = []; render(); progress_var.set(0); progress_text_var.set("Подготовка сканирования — 0%"); status_var.set("Запуск")
            scope, kind, profile = scope_code(), kind_code(), profile_code()
            def worker() -> None:
                try:
                    service = LiveOpportunitySearchService(self.client)
                    results = service.scan(profile=profile, instrument_kind=kind, scope=scope, progress_callback=lambda s, p, c, t: self.after(0, lambda: update_progress(s, p, c, t)), result_callback=lambda item, c, t: None)
                    self.after(0, lambda: finish(results))
                except Exception as exc:
                    self.after(0, lambda: fail(exc))
            threading.Thread(target=worker, daemon=True).start()

        def finish(results: list[Any]) -> None:
            state["results"] = results; progress_var.set(100); progress_text_var.set(f"Анализ завершён — 100% ({len(results)} инструментов)"); status_var.set("Готово"); scan_button.configure(state="normal"); render()

        def fail(exc: Exception) -> None:
            progress_text_var.set(f"Ошибка анализа: {exc}"); status_var.set("Ошибка"); scan_button.configure(state="normal")

        def on_tree_select(_event: Any = None) -> None:
            selection = tree.selection()
            if not selection: return show_detail(None)
            index = tree.index(selection[0]); selected = [x for x in state["results"] if decision_code() == "ALL" or (x.decision or "PASS") == decision_code()]
            if 0 <= index < len(selected): show_detail(selected[index])

        def update_scope(*_args: Any) -> None:
            title_var.set("Анализ портфеля" if scope_code() == PORTFOLIO_SCOPE else "Возможности рынка"); state["results"] = []; show_detail(None); render()

        scope_combo.bind("<<ComboboxSelected>>", update_scope)
        filter_combo.bind("<<ComboboxSelected>>", lambda _e: render())
        tree.bind("<<TreeviewSelect>>", on_tree_select)
        scan_button.configure(command=scan)
        render()

    app_class._shell = shell
    app_class._page_opportunities = page_opportunities
    app_class._opportunity_search_ui_v04_installed = True


__all__ = ["install_opportunity_search_ui"]
