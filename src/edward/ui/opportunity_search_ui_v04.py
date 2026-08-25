from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.opportunity_search_service import OpportunitySearchService
from edward.ui.instrument_catalog import INSTRUMENT_KINDS


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
        ttk.Label(top, text="Возможности рынка", style="Title.TLabel").pack(side="left")

        profile_var = tk.StringVar(value="medium_term")
        kind_var = tk.StringVar(value="Shares")
        status_var = tk.StringVar(value="Готово")
        ttk.Label(top, text="Профиль:").pack(side="left", padx=(25, 5))
        ttk.Combobox(top, textvariable=profile_var, state="readonly", values=("long_term", "medium_term", "speculative"), width=14).pack(side="left")
        ttk.Label(top, text="Тип:").pack(side="left", padx=(15, 5))
        ttk.Combobox(top, textvariable=kind_var, state="readonly", values=[label for _, label in INSTRUMENT_KINDS], width=14).pack(side="left")
        ttk.Label(top, textvariable=status_var).pack(side="left", padx=18)
        scan_button = ttk.Button(top, text="Сканировать")
        scan_button.pack(side="right")

        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill="x", pady=(0, 8))
        decision_var = tk.StringVar(value="ALL")
        ttk.Label(filter_frame, text="Фильтр:").pack(side="left")
        filter_combo = ttk.Combobox(filter_frame, textvariable=decision_var, state="readonly", values=("ALL", "BUY", "WAIT", "PASS"), width=10)
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
            ("reason", "Причина", 230),
        ):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="center" if key not in {"ticker", "strategy", "reason"} else "w")
        tree.pack(fill="both", expand=True)

        summary_var = tk.StringVar(value="BUY: 0   WAIT: 0   PASS: 0   Недоступны: 0")
        ttk.Label(frame, textvariable=summary_var).pack(anchor="w", pady=(8, 0))

        state: dict[str, Any] = {"results": []}

        def render() -> None:
            selected = decision_var.get()
            for item in tree.get_children():
                tree.delete(item)
            results = state["results"]
            visible = []
            for item in results:
                decision = item.decision or "PASS"
                if selected == "BUY" and decision != "BUY":
                    continue
                if selected == "WAIT" and decision != "WAIT":
                    continue
                if selected == "PASS" and decision not in {"PASS", None}:
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
            buy = sum(1 for item in results if item.decision == "BUY")
            wait = sum(1 for item in results if item.decision == "WAIT")
            passed = sum(1 for item in results if item.decision == "PASS" or item.decision is None)
            unavailable = sum(1 for item in results if item.status == "ANALYSIS_UNAVAILABLE")
            summary_var.set(f"BUY: {buy}   WAIT: {wait}   PASS: {passed}   Недоступны: {unavailable}   Показано: {len(visible)}")

        def scan() -> None:
            scan_button.configure(state="disabled")
            status_var.set("Сканирование рынка…")
            kind = next(kind_code for kind_code, label in INSTRUMENT_KINDS if label == kind_var.get())
            profile = profile_var.get()

            def worker() -> None:
                try:
                    results = OpportunitySearchService(self.client).scan(profile=profile, instrument_kind=kind)
                    self.after(0, lambda: finish(results))
                except Exception as exc:
                    self.after(0, lambda: fail(exc))

            threading.Thread(target=worker, daemon=True).start()

        def finish(results: list[Any]) -> None:
            state["results"] = results
            status_var.set(f"Сканирование завершено: {len(results)} инструментов")
            scan_button.configure(state="normal")
            render()

        def fail(exc: Exception) -> None:
            status_var.set(f"Ошибка: {exc}")
            scan_button.configure(state="normal")

        scan_button.configure(command=scan)
        filter_combo.bind("<<ComboboxSelected>>", lambda _event: render())
        render()

    app_class._shell = shell
    app_class._page_opportunities = page_opportunities
    app_class._opportunity_search_ui_v04_installed = True
