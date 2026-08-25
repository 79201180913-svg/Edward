from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from edward.config.application_settings import ApplicationSettingsStore
from edward.services.opportunity_search_service import INSTRUMENT_KIND_ALL, MARKET_SCOPE, PORTFOLIO_SCOPE
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService
from edward.services.strategy_optimization_cache import StrategyOptimizationCache

SCOPE_VALUES = ((MARKET_SCOPE, "Торгуемые инструменты"), (PORTFOLIO_SCOPE, "Мой портфель"))
SCOPE_BY_LABEL = {label: code for code, label in SCOPE_VALUES}
PROFILE_VALUES = (("long_term", "Долгосрочная"), ("medium_term", "Среднесрочная"), ("speculative", "Спекулятивная"))
PROFILE_BY_LABEL = {label: code for code, label in PROFILE_VALUES}
KIND_LABELS = {"SHARE": "Акции", "BOND": "Облигации", "ETF": "Фонды ETF", "CURRENCY": "Валюты", "FUTURES": "Фьючерсы", "OPTION": "Опционы"}
KIND_BY_LABEL = {label: code for code, label in KIND_LABELS.items()}
DECISION_LABELS = {"BUY": "Купить", "WAIT": "Ждать", "HOLD": "Удерживать", "ADD": "Увеличить", "REDUCE": "Сократить", "SELL": "Продать", "PASS": "Пропустить"}
FILTER_VALUES = ("ALL", "BUY", "WAIT", "HOLD", "ADD", "REDUCE", "SELL", "PASS")
FILTER_LABELS = ("Все", "Купить", "Ждать", "Удерживать", "Увеличить", "Сократить", "Продать", "Пропустить")
FILTER_CODE_BY_LABEL = dict(zip(FILTER_LABELS, FILTER_VALUES))
REGIME_LABELS = {"TREND": "Тренд", "Trend": "Тренд", "MOMENTUM": "Импульс", "Momentum": "Импульс", "BREAKOUT": "Пробой", "Breakout": "Пробой", "MEAN_REVERSION": "Возврат к среднему", "Mean Reversion": "Возврат к среднему", "UNCLEAR": "Неясный", "UNCLEAR_REGIME": "Неясный"}
STRATEGY_LABELS = {"Trend Following": "Следование за трендом", "Momentum": "Импульсная стратегия", "Breakout": "Пробой", "Mean Reversion": "Возврат к среднему"}
REASON_LABELS = {"STRATEGY_QUALITY_FAIL": "Стратегия не прошла контроль качества", "RISK_FAIL": "Не пройдены риск-ограничения", "MARKET_REGIME_UNFAVORABLE": "Рыночный режим неблагоприятен", "PORTFOLIO_CONSTRAINT": "Ограничение портфеля", "INSTRUMENT_BUY_UNAVAILABLE": "Покупка инструмента недоступна", "ENTRY_NOT_READY": "Условия входа ещё не готовы", "BUY_CONDITIONS_MET": "Условия покупки выполнены", "OPPORTUNITY_BELOW_BUY_THRESHOLD": "Привлекательность ниже порога покупки", "OPPORTUNITY_TOO_LOW": "Торговая возможность недостаточно привлекательна", "RISK_DETERIORATION": "Риск позиции ухудшился", "CRITICAL_RISK": "Критический риск", "EXIT_SIGNAL": "Получен сигнал на выход", "POSITION_ABOVE_TARGET": "Доля позиции выше целевой", "POSITION_BELOW_TARGET": "Доля позиции ниже целевой", "STRATEGY_QUALITY_DEGRADED": "Качество стратегии ухудшилось", "SIGNAL_DEGRADED": "Торговый сигнал ухудшился", "ANALYSIS_UNAVAILABLE": "Недостаточно данных для принятия решения", "NO_ACCEPTABLE_STRATEGY": "Нет приемлемой стратегии"}


def _label(mapping: dict[str, str], value: str | None, default: str = "—") -> str:
    if value in (None, ""):
        return default
    return mapping.get(str(value), str(value))


def _safe_configure(widget: Any, **kwargs: Any) -> bool:
    try:
        if widget.winfo_exists():
            widget.configure(**kwargs)
            return True
    except tk.TclError:
        return False
    return False


def install_opportunity_search_ui(app_class: type[Any]) -> None:
    if getattr(app_class, "_opportunity_search_ui_v04_installed", False):
        return
    original_shell = app_class._shell

    def shell(self: Any) -> None:
        original_shell(self)
        if hasattr(self, "nav") and not getattr(self, "_opportunity_nav_added_v04", False):
            ttk.Button(self.nav, text="Возможности", style="Nav.TButton", command=lambda: self.show_page("opportunities")).pack(fill="x", pady=2)
            self._opportunity_nav_added_v04 = True

    def page_opportunities(self: Any) -> None:
        frame = ttk.Frame(self.content)
        frame.pack(fill="both", expand=True)
        title_var = tk.StringVar(value="Возможности рынка")
        status_var = tk.StringVar(value="Готово")
        cache_status_var = tk.StringVar(value="Кэш WF: 0")
        progress_var = tk.DoubleVar(value=0.0)
        progress_text_var = tk.StringVar(value="Готово")
        scope_var = tk.StringVar(value="Торгуемые инструменты")
        profile_var = tk.StringVar(value="Среднесрочная")
        kind_var = tk.StringVar(value="Акции")
        decision_var = tk.StringVar(value="Все")

        settings = ApplicationSettingsStore().load()
        cache = StrategyOptimizationCache(settings.storage_path)

        top = ttk.Frame(frame); top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, textvariable=title_var, style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="Область:").pack(side="left", padx=(25, 5))
        scope_combo = ttk.Combobox(top, textvariable=scope_var, state="readonly", values=[x[1] for x in SCOPE_VALUES], width=20); scope_combo.pack(side="left")
        ttk.Label(top, text="Профиль торговли:").pack(side="left", padx=(15, 5))
        profile_combo = ttk.Combobox(top, textvariable=profile_var, state="readonly", values=[x[1] for x in PROFILE_VALUES], width=16); profile_combo.pack(side="left")
        ttk.Label(top, text="Тип инструмента:").pack(side="left", padx=(15, 5))
        kind_combo = ttk.Combobox(top, textvariable=kind_var, state="readonly", values=["Все"] + list(KIND_LABELS.values()), width=16); kind_combo.pack(side="left")
        ttk.Label(top, textvariable=status_var, width=11).pack(side="left", padx=8)
        ttk.Label(top, textvariable=cache_status_var, width=14).pack(side="left", padx=4)
        clear_cache_button = ttk.Button(top, text="Очистить кэш", width=13); clear_cache_button.pack(side="right", padx=(4, 0))
        recompute_button = ttk.Button(top, text="Пересчитать WF", width=15); recompute_button.pack(side="right", padx=(4, 0))
        scan_button = ttk.Button(top, text="Сканировать", width=13); scan_button.pack(side="right")

        progress_frame = ttk.Frame(frame); progress_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(progress_frame, textvariable=progress_text_var).pack(anchor="w", pady=(0, 4))
        ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate", maximum=100.0, variable=progress_var).pack(fill="x")

        filter_frame = ttk.Frame(frame); filter_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(filter_frame, text="Фильтр решения:").pack(side="left")
        filter_combo = ttk.Combobox(filter_frame, textvariable=decision_var, state="readonly", values=FILTER_LABELS, width=15); filter_combo.pack(side="left", padx=(6, 12))

        columns = ("ticker", "price", "regime", "strategy", "strategy_score", "opportunity_score", "decision", "reason")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=20)
        for key, label, width in (("ticker", "Инструмент", 110), ("price", "Цена", 90), ("regime", "Рыночный режим", 120), ("strategy", "Стратегия", 190), ("strategy_score", "Балл стратегии", 115), ("opportunity_score", "Балл возможности", 125), ("decision", "Решение", 105), ("reason", "Причина", 300)):
            tree.heading(key, text=label); tree.column(key, width=width, anchor="center" if key not in {"ticker", "strategy", "reason"} else "w")
        tree.pack(fill="both", expand=True)
        summary_var = tk.StringVar(value="Покупка: 0   Ждать: 0   Удерживать: 0   Увеличить: 0   Сократить: 0   Продать: 0   Пропустить: 0   Недоступны: 0   Показано: 0")
        ttk.Label(frame, textvariable=summary_var).pack(anchor="w", pady=(8, 0))
        state: dict[str, Any] = {"results": []}

        def refresh_cache_status() -> None:
            try: cache_status_var.set(f"Кэш WF: {cache.count()}")
            except Exception: cache_status_var.set("Кэш WF: ошибка")

        def page_alive() -> bool:
            try: return bool(frame.winfo_exists())
            except tk.TclError: return False

        def scope_code() -> str: return SCOPE_BY_LABEL.get(scope_var.get(), MARKET_SCOPE)
        def profile_code() -> str: return PROFILE_BY_LABEL.get(profile_var.get(), "medium_term")
        def kind_code() -> str: return INSTRUMENT_KIND_ALL if kind_var.get() == "Все" else KIND_BY_LABEL.get(kind_var.get(), "SHARE")
        def decision_code() -> str: return FILTER_CODE_BY_LABEL.get(decision_var.get(), "ALL")

        def set_controls(enabled: bool) -> None:
            combo_state = "readonly" if enabled else "disabled"
            _safe_configure(scan_button, state="normal" if enabled else "disabled")
            _safe_configure(recompute_button, state="normal" if enabled else "disabled")
            _safe_configure(clear_cache_button, state="normal" if enabled else "disabled")
            for widget in (scope_combo, profile_combo, kind_combo, filter_combo): _safe_configure(widget, state=combo_state)

        def row_values(item: Any) -> tuple[str, ...]:
            decision = item.decision or "PASS"
            return (item.ticker, f"{item.price:.4f}" if item.price is not None else "—", _label(REGIME_LABELS, item.market_regime), _label(STRATEGY_LABELS, item.strategy_name), f"{item.strategy_score:.1f}", f"{item.opportunity_score:.1f}", _label(DECISION_LABELS, decision), _label(REASON_LABELS, item.reason))

        def update_summary() -> None:
            if not page_alive(): return
            counts = {value: 0 for value in FILTER_VALUES if value != "ALL"}
            for item in state["results"]: counts[item.decision or "PASS"] = counts.get(item.decision or "PASS", 0) + 1
            unavailable = sum(1 for item in state["results"] if item.status == "ANALYSIS_UNAVAILABLE")
            selected = decision_code(); visible = sum(1 for item in state["results"] if selected == "ALL" or (item.decision or "PASS") == selected)
            summary_var.set("   ".join((f"Покупка: {counts.get('BUY', 0)}", f"Ждать: {counts.get('WAIT', 0)}", f"Удерживать: {counts.get('HOLD', 0)}", f"Увеличить: {counts.get('ADD', 0)}", f"Сократить: {counts.get('REDUCE', 0)}", f"Продать: {counts.get('SELL', 0)}", f"Пропустить: {counts.get('PASS', 0)}", f"Недоступны: {unavailable}", f"Показано: {visible}")))

        def render() -> None:
            if not page_alive(): return
            for row in tree.get_children(): tree.delete(row)
            selected = decision_code()
            for item in state["results"]:
                if selected != "ALL" and (item.decision or "PASS") != selected: continue
                tree.insert("", "end", values=row_values(item))
            update_summary()

        def append_result(item: Any) -> None:
            if not page_alive(): return
            state["results"].append(item)
            selected = decision_code()
            if selected == "ALL" or (item.decision or "PASS") == selected: tree.insert("", "end", values=row_values(item))
            update_summary()

        def update_scope_ui(*_args: Any) -> None:
            if not page_alive(): return
            title_var.set("Анализ портфеля" if scope_code() == PORTFOLIO_SCOPE else "Возможности рынка")
            decision_var.set("Все"); state["results"] = []; progress_var.set(0.0); progress_text_var.set("Готово"); status_var.set("Готово"); render()

        def localize_stage(stage: str) -> str:
            for source, target in (("Market Data: candles ", "Рыночные данные: свечи "), ("Market Data: ", "Рыночные данные: "), ("Risk / Opportunity: ", "Риск и возможность: "), ("Decision Engine: ", "Формирование решения: "), ("Portfolio Context загружается", "Загрузка контекста портфеля"), ("Portfolio Context загружен", "Контекст портфеля загружен"), ("Вселенная анализа:", "Инструментов для анализа:")):
                if stage.startswith(source): return target + stage[len(source):]
            return stage

        def update_progress(stage: str, percent: float, current: int, total: int) -> None:
            if not page_alive(): return
            progress_var.set(percent); suffix = f" ({current}/{total})" if total else ""; progress_text_var.set(f"{localize_stage(stage)} — {percent:.0f}%{suffix}"); status_var.set("Выполняется")

        def progress_from_worker(stage: str, percent: float, current: int, total: int) -> None:
            try: self.after(0, lambda: update_progress(stage, percent, current, total))
            except tk.TclError: pass

        def result_from_worker(item: Any, current: int, total: int) -> None:
            try: self.after(0, lambda result=item: append_result(result))
            except tk.TclError: pass

        def scan(force_recompute: bool = False) -> None:
            if not page_alive(): return
            set_controls(False); state["results"] = []
            for row in tree.get_children(): tree.delete(row)
            update_summary(); progress_var.set(0.0); progress_text_var.set("Подготовка сканирования — 0%"); status_var.set("Запуск")
            if force_recompute: status_var.set("Принудительный пересчёт Walk Forward")
            scope, kind, profile = scope_code(), kind_code(), profile_code()

            def worker() -> None:
                try:
                    service = LiveOpportunitySearchService(self.client, force_recompute=force_recompute)
                    results = service.scan(profile=profile, instrument_kind=kind, scope=scope, progress_callback=progress_from_worker, result_callback=result_from_worker, force_recompute=force_recompute)
                    try: self.after(0, lambda final_results=results: finish(final_results))
                    except tk.TclError: pass
                except Exception as exc:
                    try: self.after(0, lambda error=exc: fail(error))
                    except tk.TclError: pass
            threading.Thread(target=worker, daemon=True).start()

        def finish(results: list[Any]) -> None:
            if not page_alive(): return
            state["results"] = results; progress_var.set(100.0); label = "позиций" if scope_code() == PORTFOLIO_SCOPE else "инструментов"; progress_text_var.set(f"Анализ завершён — 100% ({len(results)} {label})"); status_var.set("Готово"); set_controls(True); render(); refresh_cache_status()

        def fail(_exc: Exception) -> None:
            if not page_alive(): return
            progress_text_var.set(f"Анализ завершён с ошибкой на {progress_var.get():.0f}%"); status_var.set("Ошибка"); set_controls(True); refresh_cache_status()

        def clear_cache() -> None:
            if not page_alive(): return
            if not messagebox.askyesno("Очистка кэша", "Удалить все сохранённые результаты Walk Forward для версии 0.4?\n\nСледующий анализ выполнит полный пересчёт."):
                return
            deleted = cache.clear_all(); refresh_cache_status(); status_var.set(f"Кэш очищен: удалено {deleted} результатов")

        scope_combo.bind("<<ComboboxSelected>>", update_scope_ui)
        scan_button.configure(command=lambda: scan(False))
        recompute_button.configure(command=lambda: scan(True))
        clear_cache_button.configure(command=clear_cache)
        filter_combo.bind("<<ComboboxSelected>>", lambda _event: render())
        render(); refresh_cache_status()

    app_class._shell = shell
    app_class._page_opportunities = page_opportunities
    app_class._opportunity_search_ui_v04_installed = True
