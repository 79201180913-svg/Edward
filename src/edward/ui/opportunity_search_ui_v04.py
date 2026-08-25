from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.opportunity_search_service import (
    INSTRUMENT_KIND_ALL,
    MARKET_SCOPE,
    PORTFOLIO_SCOPE,
    OpportunitySearchService,
)
from edward.ui.instrument_catalog import INSTRUMENT_KINDS


SCOPE_VALUES = (
    (MARKET_SCOPE, "Торгуемые инструменты"),
    (PORTFOLIO_SCOPE, "Мой портфель"),
)
SCOPE_BY_LABEL = {label: code for code, label in SCOPE_VALUES}
FILTER_VALUES = ("ALL", "BUY", "WAIT", "HOLD", "ADD", "REDUCE", "SELL", "PASS")


def install_opportunity_search_ui(app_class: type[Any]) -> None:
    if getattr(app_class, "_opportunity_search_ui_v04_installed", False):
        return

    original_shell = app_class._shell

    def shell(self: Any) -> None:
        original_shell(self)
        if not hasattr(self, "nav"):
            return
        if getattr(self, "_opportunity_nav_added_v04", False):
            return
        ttk.Button(
            self.nav,
            text="Возможности",
            style="Nav.TButton",
            command=lambda: self.show_page("opportunities"),
        ).pack(fill="x", pady=2)
        self._opportunity_nav_added_v04 = True

    def page_opportunities(self: Any) -> None:
        frame = ttk.Frame(self.content)
        frame.pack(fill="both", expand=True)

        top = ttk.Frame(frame)
        top.pack(fill="x", pady=(0, 10))
        title_var = tk.StringVar(value="Возможности рынка")
        ttk.Label(top, textvariable=title_var, style="Title.TLabel").pack(side="left")

        scope_var = tk.StringVar(value="Торгуемые инструменты")
        profile_var = tk.StringVar(value="medium_term")
        kind_var = tk.StringVar(value="Shares")
        status_var = tk.StringVar(value="Готово")
        progress_var = tk.DoubleVar(value=0.0)
        progress_text_var = tk.StringVar(value="Готово")

        ttk.Label(top, text="Область:").pack(side="left", padx=(25, 5))
        scope_combo = ttk.Combobox(
            top,
            textvariable=scope_var,
            state="readonly",
            values=[label for _, label in SCOPE_VALUES],
            width=20,
        )
        scope_combo.pack(side="left")

        ttk.Label(top, text="Профиль:").pack(side="left", padx=(15, 5))
        profile_combo = ttk.Combobox(
            top,
            textvariable=profile_var,
            state="readonly",
            values=("long_term", "medium_term", "speculative"),
            width=14,
        )
        profile_combo.pack(side="left")

        ttk.Label(top, text="Тип:").pack(side="left", padx=(15, 5))
        kind_combo = ttk.Combobox(
            top,
            textvariable=kind_var,
            state="readonly",
            values=["Все"] + [label for _, label in INSTRUMENT_KINDS],
            width=14,
        )
        kind_combo.pack(side="left")
        ttk.Label(top, textvariable=status_var).pack(side="left", padx=18)
        scan_button = ttk.Button(top, text="Сканировать")
        scan_button.pack(side="right")

        progress_frame = ttk.Frame(frame)
        progress_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(progress_frame, textvariable=progress_text_var).pack(anchor="w", pady=(0, 4))
        progress_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100.0,
            variable=progress_var,
        )
        progress_bar.pack(fill="x")

        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill="x", pady=(0, 8))
        decision_var = tk.StringVar(value="ALL")
        ttk.Label(filter_frame, text="Фильтр:").pack(side="left")
        filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=decision_var,
            state="readonly",
            values=FILTER_VALUES,
            width=10,
        )
        filter_combo.pack(side="left", padx=(6, 12))

        columns = ("ticker", "price", "regime", "strategy", "strategy_score", "opportunity_score", "decision", "reason")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=20)
        for key, label, width in (
            ("ticker", "Инструмент", 110),
            ("price", "Цена", 90),
            ("regime", "Regime", 100),
            ("strategy", "Стратегия", 150),
            ("strategy_score", "Strategy Score", 110),
            ("opportunity_score", "Opportunity Score", 125),
            ("decision", "Decision", 90),
            ("reason", "Причина", 260),
        ):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="center" if key not in {"ticker", "strategy", "reason"} else "w")
        tree.pack(fill="both", expand=True)

        summary_var = tk.StringVar(value="BUY: 0   WAIT: 0   HOLD: 0   ADD: 0   REDUCE: 0   SELL: 0   PASS: 0   Недоступны: 0")
        ttk.Label(frame, textvariable=summary_var).pack(anchor="w", pady=(8, 0))

        state: dict[str, Any] = {"results": []}

        def _scope_code() -> str:
            return SCOPE_BY_LABEL.get(scope_var.get(), MARKET_SCOPE)

        def _kind_code() -> str:
            if kind_var.get() == "Все":
                return INSTRUMENT_KIND_ALL
            return next(kind_code for kind_code, label in INSTRUMENT_KINDS if label == kind_var.get())

        def render() -> None:
            selected = decision_var.get()
            for item in tree.get_children():
                tree.delete(item)
            results = state["results"]
            visible = []
            for item in results:
                decision = item.decision or "PASS"
                if selected != "ALL" and decision != selected:
                    continue
                visible.append(item)
                tree.insert(
                    "",
                    "end",
                    values=(
                        item.ticker,
                        f"{item.price:.4f}" if item.price is not None else "—",
                        item.market_regime or "—",
                        item.strategy_name or "—",
                        f"{item.strategy_score:.1f}",
                        f"{item.opportunity_score:.1f}",
                        decision,
                        item.reason,
                    ),
                )
            counts = {value: 0 for value in FILTER_VALUES if value != "ALL"}
            for item in results:
                decision = item.decision or "PASS"
                counts[decision] = counts.get(decision, 0) + 1
            unavailable = sum(1 for item in results if item.status == "ANALYSIS_UNAVAILABLE")
            summary_var.set(
                "   ".join(
                    (
                        f"BUY: {counts.get('BUY', 0)}",
                        f"WAIT: {counts.get('WAIT', 0)}",
                        f"HOLD: {counts.get('HOLD', 0)}",
                        f"ADD: {counts.get('ADD', 0)}",
                        f"REDUCE: {counts.get('REDUCE', 0)}",
                        f"SELL: {counts.get('SELL', 0)}",
                        f"PASS: {counts.get('PASS', 0)}",
                        f"Недоступны: {unavailable}",
                        f"Показано: {len(visible)}",
                    )
                )
            )

        def update_scope_ui(*_args: Any) -> None:
            is_portfolio = _scope_code() == PORTFOLIO_SCOPE
            title_var.set("Анализ портфеля" if is_portfolio else "Возможности рынка")
            decision_var.set("ALL")
            state["results"] = []
            progress_var.set(0.0)
            progress_text_var.set("Готово")
            status_var.set("Готово")
            render()

        def update_progress(stage: str, percent: float, current: int, total: int) -> None:
            progress_var.set(percent)
            suffix = f" ({current}/{total})" if total else ""
            progress_text_var.set(f"{stage} — {percent:.0f}%{suffix}")
            status_var.set(f"Выполняется: {stage}")

        def progress_from_worker(stage: str, percent: float, current: int, total: int) -> None:
            self.after(0, lambda: update_progress(stage, percent, current, total))

        def scan() -> None:
            scan_button.configure(state="disabled")
            scope_combo.configure(state="disabled")
            profile_combo.configure(state="disabled")
            kind_combo.configure(state="disabled")
            filter_combo.configure(state="disabled")
            progress_var.set(0.0)
            progress_text_var.set("Подготовка сканирования — 0%")
            status_var.set("Запуск сканирования")
            scope = _scope_code()
            kind = _kind_code()
            profile = profile_var.get()

            def worker() -> None:
                try:
                    results = OpportunitySearchService(self.client).scan(
                        profile=profile,
                        instrument_kind=kind,
                        scope=scope,
                        progress_callback=progress_from_worker,
                    )
                    self.after(0, lambda: finish(results))
                except Exception as exc:
                    self.after(0, lambda: fail(exc))

            threading.Thread(target=worker, daemon=True).start()

        def finish(results: list[Any]) -> None:
            state["results"] = results
            progress_var.set(100.0)
            label = "позиций" if _scope_code() == PORTFOLIO_SCOPE else "инструментов"
            progress_text_var.set(f"Анализ завершён — 100% ({len(results)} {label})")
            status_var.set(f"Анализ завершён: {len(results)} {label}")
            scan_button.configure(state="normal")
            scope_combo.configure(state="readonly")
            profile_combo.configure(state="readonly")
            kind_combo.configure(state="readonly")
            filter_combo.configure(state="readonly")
            render()

        def fail(exc: Exception) -> None:
            progress_text_var.set(f"Анализ завершён с ошибкой на {progress_var.get():.0f}%")
            status_var.set(f"Ошибка: {exc}")
            scan_button.configure(state="normal")
            scope_combo.configure(state="readonly")
            profile_combo.configure(state="readonly")
            kind_combo.configure(state="readonly")
            filter_combo.configure(state="readonly")

        scope_combo.bind("<<ComboboxSelected>>", update_scope_ui)
        scan_button.configure(command=scan)
        filter_combo.bind("<<ComboboxSelected>>", lambda _event: render())
        render()

    app_class._shell = shell
    app_class._page_opportunities = page_opportunities
    app_class._opportunity_search_ui_v04_installed = True
