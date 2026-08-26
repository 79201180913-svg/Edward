from __future__ import annotations

import logging
import threading
from decimal import Decimal
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from edward.services.autonomous_cycle_service import AutonomousCycleService
from edward.services.autonomous_planning_service import AutonomousPlanningService
from edward.services.balance_service import BalanceService
from edward.services.budget_planning_service import BudgetPlanningPolicy
from edward.services.opportunity_search_service import OpportunitySearchService

logger = logging.getLogger("edward.autonomous.ui")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _install_file_logging() -> Path:
    path = _project_root() / "runtime" / "edward_autonomous.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    absolute = str(path.resolve())
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == absolute:
            return path
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = True
    return path


def install_autonomous_ui(app_class: type) -> None:
    """Add the v0.7 autonomous read-only cycle to the existing GUI.

    This is a UI adapter only. Market analysis remains inside the existing
    OpportunitySearchService; the UI does not fetch candles or implement
    analysis logic itself.
    """
    if getattr(app_class, "_autonomous_ui_v07_installed", False):
        return
    app_class._autonomous_ui_v07_installed = True
    log_path = _install_file_logging()

    original_shell = app_class._shell
    original_close = app_class._close

    def _shell(self: Any) -> None:
        original_shell(self)
        ttk.Separator(self.nav).pack(fill="x", pady=14)
        ttk.Button(
            self.nav,
            text="Автономная торговля",
            style="Nav.TButton",
            command=lambda: self.show_page("autonomous"),
        ).pack(fill="x", pady=2)

    def _page_autonomous(self: Any) -> None:
        ttk.Label(self.content, text="Автономная торговля", style="Title.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(
            self.content,
            text="Планирование капитала и анализ возможностей. Текущий режим: только анализ, без отправки заявок.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 14))

        aid = self._require_account()
        if not aid:
            return

        controls = ttk.Frame(self.content)
        controls.pack(fill="x", pady=(0, 12))
        ttk.Label(controls, text="Профиль:").pack(side="left")
        profile_var = tk.StringVar(value="medium_term")
        ttk.Combobox(controls, textvariable=profile_var, state="readonly", values=("speculative", "medium_term", "long_term"), width=16).pack(side="left", padx=(6, 16))
        ttk.Label(controls, text="Слоты:").pack(side="left")
        slots_var = tk.IntVar(value=5)
        ttk.Spinbox(controls, from_=1, to=50, textvariable=slots_var, width=6).pack(side="left", padx=(6, 16))
        ttk.Label(controls, text="Резерв %:").pack(side="left")
        reserve_var = tk.StringVar(value="10")
        ttk.Entry(controls, textvariable=reserve_var, width=8).pack(side="left", padx=(6, 16))
        start_button = ttk.Button(controls, text="Анализировать рынок")
        start_button.pack(side="left", padx=(4, 8))
        refresh_button = ttk.Button(controls, text="Обновить")
        refresh_button.pack(side="left")

        status_var = tk.StringVar(value="Готово")
        ttk.Label(self.content, textvariable=status_var).pack(anchor="w", pady=(0, 8))

        cards = ttk.Frame(self.content)
        cards.pack(fill="x", pady=(0, 14))
        for column in range(5):
            cards.columnconfigure(column, weight=1)
        card_values: dict[str, ttk.Label] = {}
        for column, (key, title) in enumerate((("capital", "Капитал"), ("reserve", "Резерв"), ("budget", "Инвестиционный бюджет"), ("target", "Целевая позиция"), ("cash", "Доступные деньги"))):
            frame = ttk.Frame(cards, style="Card.TFrame", padding=12)
            frame.grid(row=0, column=column, sticky="nsew", padx=4)
            ttk.Label(frame, text=title, style="CardTitle.TLabel").pack(anchor="w")
            value = ttk.Label(frame, text="—", style="CardValue.TLabel")
            value.pack(anchor="w", pady=(7, 0))
            card_values[key] = value

        ttk.Label(self.content, text="Возможности рынка", style="CardTitle.TLabel").pack(anchor="w", pady=(4, 6))
        tree = self._tree(self.content, ("Тикер", "Решение", "Score", "Риск", "Цена", "Кол-во", "Стоимость", "Статус"), (100, 100, 90, 80, 120, 90, 130, 260))
        activity = tk.Text(self.content, height=7, wrap="word", state="disabled")
        activity.pack(fill="x", pady=(12, 0))

        def log_ui(message: str) -> None:
            def apply() -> None:
                try:
                    activity.configure(state="normal")
                    activity.insert("end", message + "\n")
                    activity.see("end")
                    activity.configure(state="disabled")
                except tk.TclError:
                    pass
            self.after(0, apply)

        def render_result(result: Any) -> None:
            def apply() -> None:
                try:
                    for item in tree.get_children():
                        tree.delete(item)
                    for opportunity in result.market_opportunities:
                        tree.insert("", "end", values=(
                            opportunity.ticker,
                            opportunity.decision or "—",
                            f"{opportunity.opportunity_score:.2f}",
                            f"{opportunity.risk_score:.2f}",
                            "—" if opportunity.price is None else f"{opportunity.price:.4f}",
                            opportunity.recommended_quantity or opportunity.quantity,
                            f"{opportunity.recommended_value:.2f}",
                            opportunity.status,
                        ))
                    budget = result.planning.budget
                    currency = "RUB"
                    card_values["capital"].configure(text=self._money(budget.account_capital, currency))
                    card_values["reserve"].configure(text=self._money(budget.reserve, currency))
                    card_values["budget"].configure(text=self._money(budget.planning_budget, currency))
                    card_values["target"].configure(text=self._money(budget.target_position_value, currency))
                    card_values["cash"].configure(text=self._money(budget.cash, currency))
                    status_var.set(f"Завершено: рынок {len(result.market_opportunities)}, портфель {len(result.portfolio_opportunities)}")
                except tk.TclError:
                    return
            self.after(0, apply)

        def on_progress(stage: str, percent: float, current: int, total: int) -> None:
            logger.info("autonomous_progress stage=%s percent=%.1f current=%d total=%d", stage, percent, current, total)
            log_ui(f"{stage} — {percent:.1f}%")
            self.after(0, lambda: status_var.set(f"{stage} — {percent:.1f}%"))

        def run_cycle(account_id: str, profile: str, slots: int, reserve_pct: Decimal) -> None:
            try:
                policy = BudgetPlanningPolicy(slots=slots, reserve_pct=reserve_pct)
                logger.info("autonomous_cycle_started account_id=%s profile=%s slots=%d reserve_pct=%s", account_id, profile, slots, reserve_pct)
                log_ui("Запуск автономного цикла")
                service = AutonomousCycleService(
                    AutonomousPlanningService(BalanceService(self.client)),
                    OpportunitySearchService(self.client),
                )
                result = service.run(
                    account_id=account_id,
                    policy=policy,
                    profile=profile,
                    instrument_kind="SHARE",
                    progress_callback=on_progress,
                )
                logger.info("autonomous_cycle_completed account_id=%s market=%d portfolio=%d", account_id, len(result.market_opportunities), len(result.portfolio_opportunities))
                log_ui(f"Цикл завершён: market={len(result.market_opportunities)} portfolio={len(result.portfolio_opportunities)}")
                render_result(result)
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                logger.exception("autonomous_cycle_failed account_id=%s", account_id)
                log_ui(f"ОШИБКА: {error_text}")
                self.after(0, lambda text=error_text: status_var.set(f"Ошибка: {text}"))
                self.after(0, lambda text=error_text: messagebox.showerror("Автономная торговля", text))
            finally:
                self.after(0, lambda: start_button.configure(state="normal"))

        def start() -> None:
            try:
                account_id = str(aid)
                profile = str(profile_var.get())
                slots = int(slots_var.get())
                reserve_pct = Decimal(str(reserve_var.get()).replace(",", "."))
                if slots < 1 or not Decimal("0") <= reserve_pct <= Decimal("100"):
                    raise ValueError
            except Exception:
                messagebox.showwarning("Edward", "Проверьте количество слотов и резерв.")
                return
            start_button.configure(state="disabled")
            status_var.set("Подготовка автономного цикла...")
            threading.Thread(
                target=run_cycle,
                args=(account_id, profile, slots, reserve_pct),
                daemon=True,
                name="edward-autonomous-cycle",
            ).start()

        start_button.configure(command=start)
        refresh_button.configure(command=lambda: self.show_page("autonomous"))
        log_ui(f"Лог автономного режима: {log_path}")

    def _close(self: Any) -> None:
        original_close(self)

    app_class._shell = _shell
    app_class._page_autonomous = _page_autonomous
    app_class._close = _close
