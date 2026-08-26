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
from edward.services.autonomous_runtime_service import AutonomousRuntimeConfig, AutonomousRuntimeService
from edward.services.autonomous_trading_runtime_facade import AutonomousTradingRuntimeFacade
from edward.services.balance_service import BalanceService
from edward.services.budget_planning_service import BudgetPlanningPolicy
from edward.services.currency_service import CurrencyService
from edward.services.opportunity_search_service import OpportunitySearchService
from edward.ui.autonomous_control_ui_v07 import AutonomousControlPanel
from edward.ui.autonomous_portfolio_ui_v07 import open_autonomous_portfolio_window

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


def _display_opportunity_quantity(opportunity: Any) -> int:
    """Return order quantity for the autonomous opportunities grid."""
    decision = str(getattr(opportunity, "decision", "") or "").upper()
    if decision not in {"BUY", "ADD", "REDUCE", "SELL"}:
        return 0
    try:
        return int(getattr(opportunity, "recommended_quantity", 0) or 0)
    except (TypeError, ValueError):
        return 0


def install_autonomous_ui(app_class: type) -> None:
    """Add the v0.7 autonomous cycle and explicit execution lifecycle to the GUI."""
    if getattr(app_class, "_autonomous_ui_v07_installed", False):
        return
    app_class._autonomous_ui_v07_installed = True
    log_path = _install_file_logging()
    original_shell = app_class._shell
    original_close = app_class._close

    def _shell(self: Any) -> None:
        original_shell(self)
        ttk.Separator(self.nav).pack(fill="x", pady=14)
        ttk.Button(self.nav, text="Автономная торговля", style="Nav.TButton", command=lambda: self.show_page("autonomous")).pack(fill="x", pady=2)

    def _page_autonomous(self: Any) -> None:
        ttk.Label(self.content, text="Автономная торговля", style="Title.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Label(self.content, text="Планирование капитала и анализ возможностей.", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))
        aid = self._require_account()
        if not aid:
            return

        control = AutonomousControlPanel(self.content)
        control.pack(fill="x", pady=(0, 12))

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
        portfolio_button = ttk.Button(controls, text="Портфель")
        portfolio_button.pack(side="left", padx=(0, 8))
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

        ttk.Label(self.content, text="Возможности рынка и портфеля", style="CardTitle.TLabel").pack(anchor="w", pady=(4, 6))
        tree = self._tree(self.content, ("Область", "Тикер", "Решение", "Score", "Риск", "Цена", "Кол-во", "Стоимость", "Статус"), (90, 100, 100, 80, 75, 110, 80, 115, 250))
        ttk.Label(self.content, text="План перераспределения", style="CardTitle.TLabel").pack(anchor="w", pady=(10, 6))
        allocation_tree = self._tree(self.content, ("Действие", "Тикер", "Что заменяем", "Score", "Риск", "Целевая стоимость", "Причина"), (100, 100, 110, 80, 80, 130, 520))
        ttk.Label(self.content, text="Порядок исполнения", style="CardTitle.TLabel").pack(anchor="w", pady=(10, 6))
        execution_tree = self._tree(self.content, ("№", "Действие", "Тикер", "UID", "Целевая стоимость", "Зависит от", "Статус", "Причина"), (45, 90, 100, 220, 130, 90, 120, 420))
        activity = tk.Text(self.content, height=7, wrap="word", state="disabled")
        activity.pack(fill="x", pady=(10, 0))
        latest_portfolio_opportunities: list[Any] = []
        runtime_holder: dict[str, Any] = {"service": None, "facade": None, "last_status": None}

        def log_ui(message: str) -> None:
            def apply() -> None:
                activity.configure(state="normal")
                activity.insert("end", message + "\n")
                activity.see("end")
                activity.configure(state="disabled")
            self.after(0, apply)

        def display_money(value: Any, source_currency: str) -> str:
            target_currency = str(self.display_currency.get() or source_currency or "RUB").upper()
            source_currency = str(source_currency or "RUB").upper()
            try:
                converted = value if source_currency == target_currency else CurrencyService(self.client).convert(value, source_currency, target_currency)
                return self._money(converted, target_currency)
            except Exception:
                logger.exception("autonomous_currency_conversion_failed source=%s target=%s", source_currency, target_currency)
                return self._money(value, source_currency)

        def render_budget(planning: Any) -> None:
            budget = planning.budget
            source_currency = getattr(budget, "currency", None) or "RUB"
            def apply() -> None:
                card_values["capital"].configure(text=display_money(budget.account_capital, source_currency))
                card_values["reserve"].configure(text=display_money(budget.reserve, source_currency))
                card_values["budget"].configure(text=display_money(budget.planning_budget, source_currency))
                card_values["target"].configure(text=display_money(budget.target_position_value, source_currency))
                card_values["cash"].configure(text=display_money(budget.investable_cash, source_currency))
            self.after(0, apply)

        def insert_opportunity(opportunity: Any, scope: str) -> None:
            decision = opportunity.decision or "—"
            quantity = _display_opportunity_quantity(opportunity)
            tree.insert("", "end", values=(scope, opportunity.ticker, decision, f"{opportunity.opportunity_score:.2f}", f"{opportunity.risk_score:.2f}", "—" if opportunity.price is None else f"{opportunity.price:.4f}", quantity, f"{opportunity.recommended_value:.2f}", opportunity.status))

        def render_allocation(actions: Any) -> None:
            for item in allocation_tree.get_children():
                allocation_tree.delete(item)
            for action in actions:
                allocation_tree.insert("", "end", values=(action.action, action.ticker, action.source_ticker or "—", f"{action.score:.2f}", f"{action.risk_score:.2f}", f"{action.target_value:.2f}", action.reason))

        def render_execution_plan(plan: Any) -> None:
            for item in execution_tree.get_children():
                execution_tree.delete(item)
            if plan is None:
                return
            for step in plan.steps:
                execution_tree.insert("", "end", values=(step.sequence, step.action, step.ticker, step.instrument_uid, f"{step.target_value:.2f}", "—" if step.depends_on is None else step.depends_on, "План", step.reason))

        def render_incremental(opportunity: Any, scope: str, current: int, total: int) -> None:
            def apply() -> None:
                insert_opportunity(opportunity, scope)
                status_var.set(f"{scope}: обработано {current}/{total} — {opportunity.ticker}")
            self.after(0, apply)

        def render_result(result: Any) -> None:
            def apply() -> None:
                latest_portfolio_opportunities.clear()
                latest_portfolio_opportunities.extend(result.portfolio_opportunities)
                for item in tree.get_children():
                    tree.delete(item)
                for opportunity in result.market_opportunities:
                    insert_opportunity(opportunity, "Рынок")
                for opportunity in result.portfolio_opportunities:
                    insert_opportunity(opportunity, "Портфель")
                render_budget(result.planning)
                render_allocation(result.allocation_actions)
                render_execution_plan(result.execution_plan)
                status_var.set(f"Завершено: рынок {len(result.market_opportunities)}, портфель {len(result.portfolio_opportunities)}, действий {len(result.allocation_actions)}, шагов {len(result.execution_plan.steps) if result.execution_plan else 0}")
                log_ui(f"Цикл анализа завершён: market={len(result.market_opportunities)} portfolio={len(result.portfolio_opportunities)} allocation={len(result.allocation_actions)} execution_steps={len(result.execution_plan.steps) if result.execution_plan else 0}")
            self.after(0, apply)

        def open_portfolio() -> None:
            open_autonomous_portfolio_window(self, self.client, aid, display_currency=str(self.display_currency.get() or "RUB"), opportunities=tuple(latest_portfolio_opportunities))
        portfolio_button.configure(command=open_portfolio)

        def on_progress(stage: str, percent: float, current: int, total: int) -> None:
            logger.info("autonomous_progress stage=%s percent=%.1f current=%d total=%d", stage, percent, current, total)
            status = f"{stage} — {percent:.1f}%"
            self.after(0, lambda: status_var.set(status))
            log_ui(status)

        def run_analysis_cycle() -> None:
            try:
                slots = int(slots_var.get())
                reserve_pct = Decimal(str(reserve_var.get()).replace(",", "."))
                policy = BudgetPlanningPolicy(slots=slots, reserve_pct=reserve_pct)
                logger.info("autonomous_analysis_started account_id=%s profile=%s slots=%d reserve_pct=%s", aid, profile_var.get(), slots, reserve_pct)
                log_ui(f"Однократный анализ: профиль={profile_var.get()}, слоты={slots}, резерв={reserve_pct}%")
                service = AutonomousCycleService(AutonomousPlanningService(BalanceService(self.client)), OpportunitySearchService(self.client))
                active_scope = {"value": "Рынок"}

                def result_callback(opportunity: Any, current: int, total: int) -> None:
                    render_incremental(opportunity, active_scope["value"], current, total)

                def scope_callback(scope: str) -> None:
                    active_scope["value"] = "Рынок" if scope == "MARKET" else "Портфель"
                    log_ui(f"Начат анализ: {active_scope['value']}")

                def planning_callback(planning: Any) -> None:
                    render_budget(planning)
                    log_ui("План капитала рассчитан по текущему счёту")

                result = service.run(account_id=aid, policy=policy, profile=profile_var.get(), instrument_kind="SHARE", progress_callback=on_progress, result_callback=result_callback, scope_callback=scope_callback, planning_callback=planning_callback)
                logger.info("autonomous_analysis_completed account_id=%s profile=%s market=%d portfolio=%d allocation=%d execution_steps=%d", aid, profile_var.get(), len(result.market_opportunities), len(result.portfolio_opportunities), len(result.allocation_actions), len(result.execution_plan.steps) if result.execution_plan else 0)
                render_result(result)
            except Exception as exc:
                logger.exception("autonomous_analysis_failed account_id=%s", aid)
                self.after(0, lambda: status_var.set(f"Ошибка: {type(exc).__name__}: {exc}"))
                log_ui(f"ОШИБКА: {type(exc).__name__}: {exc}")
                self.after(0, lambda: messagebox.showerror("Анализ рынка", str(exc)))
            finally:
                self.after(0, lambda: start_button.configure(state="normal"))

        def run_autonomous_once() -> None:
            slots = int(slots_var.get())
            reserve_pct = Decimal(str(reserve_var.get()).replace(",", "."))
            policy = BudgetPlanningPolicy(slots=slots, reserve_pct=reserve_pct)
            facade = runtime_holder.get("facade")
            if facade is None:
                facade = AutonomousTradingRuntimeFacade(
                    self.client,
                    account_id=aid,
                    policy=policy,
                    profile=profile_var.get(),
                    instrument_kind="SHARE",
                )
                runtime_holder["facade"] = facade
            log_ui("Автономный цикл: анализ → план → исполнение → проверка → защита → replan")
            result = facade.run_cycle(max_iterations=50)
            control_result = result.control
            log_ui(f"Автономный цикл завершён: executed={control_result.executed} reason={control_result.reason}")
            self.after(0, lambda: status_var.set(f"Автономный цикл: {control_result.reason}"))
            if control_result.replanning is not None:
                cycle = control_result.replanning
                log_ui(f"Replan: итераций={cycle.iterations}, выполнено шагов={len(cycle.executed_steps)}")
            if not control_result.executed and control_result.reason not in {"COMPLETED", "STOPPED"}:
                raise RuntimeError(control_result.reason)

        def _sync_runtime_status() -> None:
            service = runtime_holder.get("service")
            if service is not None:
                snapshot = service.state.snapshot()
                status = snapshot.status
                message = snapshot.message
                if message:
                    control.status_var.set(f"● {status}: {message}")
                    status_var.set(message)
                else:
                    control.status_var.set(f"● {status}")
                if runtime_holder.get("last_status") != (status, message):
                    runtime_holder["last_status"] = (status, message)
                    logger.info("autonomous_runtime_status status=%s message=%s", status, message)
            if self.winfo_exists():
                self.after(500, _sync_runtime_status)

        def start_analysis() -> None:
            if not aid:
                return
            if control.mode().value == "autonomous" and control.state.snapshot().enabled:
                return
            try:
                int(slots_var.get())
                Decimal(str(reserve_var.get()).replace(",", "."))
            except Exception:
                messagebox.showwarning("Edward", "Проверьте количество слотов и резерв.")
                return
            for item in tree.get_children(): tree.delete(item)
            for item in allocation_tree.get_children(): allocation_tree.delete(item)
            for item in execution_tree.get_children(): execution_tree.delete(item)
            latest_portfolio_opportunities.clear()
            start_button.configure(state="disabled")
            status_var.set("Подготовка анализа...")
            threading.Thread(target=run_analysis_cycle, daemon=True, name="edward-autonomous-analysis").start()

        def start_autonomous() -> None:
            if control.mode().value != "autonomous":
                messagebox.showwarning("Автономная торговля", "Сначала выберите режим «Автономная торговля».")
                return
            try:
                slots = int(slots_var.get())
                reserve_pct = Decimal(str(reserve_var.get()).replace(",", "."))
                policy = BudgetPlanningPolicy(slots=slots, reserve_pct=reserve_pct)
                interval_seconds = control.interval_minutes() * 60
            except Exception:
                messagebox.showwarning("Edward", "Проверьте количество слотов и резерв.")
                return
            if runtime_holder.get("service") is not None:
                runtime_holder["service"].stop()
            facade = AutonomousTradingRuntimeFacade(
                self.client,
                account_id=aid,
                policy=policy,
                profile=profile_var.get(),
                instrument_kind="SHARE",
            )
            runtime = AutonomousRuntimeService(
                run_cycle=run_autonomous_once,
                state_service=control.state,
                config=AutonomousRuntimeConfig(interval_seconds=interval_seconds),
            )
            runtime_holder["facade"] = facade
            runtime_holder["service"] = runtime
            start_button.configure(state="disabled")
            status_var.set("Запуск автономной торговли...")
            log_ui(f"Автономная торговля ВКЛ: интервал={control.interval_minutes()} мин")
            runtime.start()

        def pause_autonomous() -> None:
            runtime = runtime_holder.get("service")
            if runtime is not None:
                runtime.pause()
            status_var.set("Автономная торговля на паузе")
            log_ui("Автономная торговля: ПАУЗА")

        def stop_autonomous() -> None:
            runtime = runtime_holder.get("service")
            if runtime is not None:
                runtime.stop()
            runtime_holder["service"] = None
            runtime_holder["facade"] = None
            start_button.configure(state="normal")
            status_var.set("Автономная торговля остановлена")
            log_ui("Автономная торговля: СТОП")

        def on_control_state(state: Any) -> None:
            if str(getattr(state, "mode", "")) == "analysis" and runtime_holder.get("service") is not None:
                runtime_holder["service"].stop()
                runtime_holder["service"] = None
                runtime_holder["facade"] = None

        control.on_start = start_autonomous
        control.on_pause = pause_autonomous
        control.on_stop = stop_autonomous
        control.on_state = on_control_state
        start_button.configure(command=start_analysis)
        refresh_button.configure(command=lambda: self.show_page("autonomous"))
        log_ui(f"Лог автономного режима: {log_path}")
        self.after(500, _sync_runtime_status)

    def _close(self: Any) -> None:
        original_close(self)

    app_class._shell = _shell
    app_class._page_autonomous = _page_autonomous
    app_class._close = _close
