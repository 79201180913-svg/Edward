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
PROFILE_VALUES = (
    ("long_term", "Долгосрочная"),
    ("medium_term", "Среднесрочная"),
    ("speculative", "Спекулятивная"),
)
PROFILE_BY_LABEL = {label: code for code, label in PROFILE_VALUES}
KIND_LABELS = {
    "SHARE": "Акции",
    "BOND": "Облигации",
    "ETF": "Фонды ETF",
    "CURRENCY": "Валюты",
    "FUTURES": "Фьючерсы",
    "OPTION": "Опционы",
}
KIND_BY_LABEL = {label: code for code, label in KIND_LABELS.items()}
DECISION_LABELS = {
    "BUY": "Купить",
    "WAIT": "Ждать",
    "HOLD": "Удерживать",
    "ADD": "Увеличить",
    "REDUCE": "Сократить",
    "SELL": "Продать",
    "PASS": "Пропустить",
}
FILTER_VALUES = ("ALL", "BUY", "WAIT", "HOLD", "ADD", "REDUCE", "SELL", "PASS")
FILTER_LABELS = ("Все", "Купить", "Ждать", "Удерживать", "Увеличить", "Сократить", "Продать", "Пропустить")
FILTER_CODE_BY_LABEL = dict(zip(FILTER_LABELS, FILTER_VALUES))
REGIME_LABELS = {
    "TREND": "Тренд",
    "MOMENTUM": "Импульс",
    "BREAKOUT": "Пробой",
    "MEAN_REVERSION": "Возврат к среднему",
    "UNCLEAR": "Неясный",
    "UNCLEAR_REGIME": "Неясный",
}
STRATEGY_LABELS = {
    "Trend Following": "Следование за трендом",
    "Momentum": "Импульсная стратегия",
    "Breakout": "Пробой",
    "Mean Reversion": "Возврат к среднему",
}
REASON_LABELS = {
    "STRATEGY_QUALITY_FAIL": "Стратегия не прошла контроль качества",
    "RISK_FAIL": "Не пройдены риск-ограничения",
    "MARKET_REGIME_UNFAVORABLE": "Рыночный режим неблагоприятен",
    "PORTFOLIO_CONSTRAINT": "Ограничение портфеля",
    "INSTRUMENT_BUY_UNAVAILABLE": "Покупка инструмента недоступна",
    "ENTRY_NOT_READY": "Условия входа ещё не готовы",
    "BUY_CONDITIONS_MET": "Условия покупки выполнены",
    "OPPORTUNITY_BELOW_BUY_THRESHOLD": "Привлекательность ниже порога покупки",
    "OPPORTUNITY_TOO_LOW": "Торговая возможность недостаточно привлекательна",
    "RISK_DETERIORATION": "Риск позиции ухудшился",
    "CRITICAL_RISK": "Критический риск",
    "EXIT_SIGNAL": "Получен сигнал на выход",
    "POSITION_ABOVE_TARGET": "Доля позиции выше целевой",
    "POSITION_BELOW_TARGET": "Доля позиции ниже целевой",
    "STRATEGY_QUALITY_DEGRADED": "Качество стратегии ухудшилось",
    "SIGNAL_DEGRADED": "Торговый сигнал ухудшился",
    "ANALYSIS_UNAVAILABLE": "Недостаточно данных для принятия решения",
    "NO_ACCEPTABLE_STRATEGY": "Нет приемлемой стратегии",
}


def _label(mapping: dict[str, str], value: str | None, default: str = "—") -> str:
    if value in (None, ""):
        return default
    text = str(value)
    return mapping.get(text, text)


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
        profile_var = tk.StringVar(value="Среднесрочная")
        kind_var = tk.StringVar(value="Акции")
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

        ttk.Label(top, text="Профиль торговли:").pack(side="left", padx=(15, 5))
        profile_combo = ttk.Combobox(
            top,
            textvariable=profile_var,
            state="readonly",
            values=[label for _, label in PROFILE_VALUES],
            width=16,
        )
        profile_combo.pack(side="left")

        ttk.Label(top, text="Тип инструмента:").pack(side="left", padx=(15, 5))
        kind_combo = ttk.Combobox(
            top,
            textvariable=kind_var,
            state="readonly",
            values=["Все"] + list(KIND_LABELS.values()),
            width=16,
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
        decision_var = tk.StringVar(value="Все")
        ttk.Label(filter_frame, text="Фильтр решения:").pack(side="left")
        filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=decision_var,
            state="readonly",
            values=FILTER_LABELS,
            width=15,
        )
        filter_combo.pack(side="left", padx=(6, 12))

        columns = ("ticker", "price", "regime", "strategy", "strategy_score", "opportunity_score", "decision", "reason")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=20)
        for key, label, width in (
            ("ticker", "Инструмент", 110),
            ("price", "Цена", 90),
            ("regime", "Рыночный режим", 120),
            ("strategy", "Стратегия", 190),
            ("strategy_score", "Балл стратегии", 115),
            ("opportunity_score", "Балл возможности", 125),
            ("decision", "Решение", 105),
            ("reason", "Причина", 300),
        ):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="center" if key not in {"ticker", "strategy", "reason"} else "w")
        tree.pack(fill="both", expand=True)

        summary_var = tk.StringVar(value="Покупка: 0   Ждать: 0   Удерживать: 0   Увеличить: 0   Сократить: 0   Продать: 0   Пропустить: 0   Недоступны: 0")
        ttk.Label(frame, textvariable=summary_var).pack(anchor="w", pady=(8, 0))

        state: dict[str, Any] = {"results": []}

        def _scope_code() -> str:
            return SCOPE_BY_LABEL.get(scope_var.get(), MARKET_SCOPE)

        def _profile_code() -> str:
            return PROFILE_BY_LABEL.get(profile_var.get(), "medium_term")

        def _kind_code() -> str:
            if kind_var.get() == "Все":
                return INSTRUMENT_KIND_ALL
            return KIND_BY_LABEL.get(kind_var.get(), "SHARE")

        def _decision_code() -> str:
            return FILTER_CODE_BY_LABEL.get(decision_var.get(), "ALL")

        def render() -> None:
            selected = _decision_code()
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
                        _label(REGIME_LABELS, item.market_regime),
                        _label(STRATEGY_LABELS, item.strategy_name),
                        f"{item.strategy_score:.1f}",
                        f"{item.opportunity_score:.1f}",
                        _label(DECISION_LABELS, decision),
                        _label(REASON_LABELS, item.reason),
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
                        f"Покупка: {counts.get('BUY', 0)}",
                        f"Ждать: {counts.get('WAIT', 0)}",
                        f"Удерживать: {counts.get('HOLD', 0)}",
                        f"Увеличить: {counts.get('ADD', 0)}",
                        f"Сократить: {counts.get('REDUCE', 0)}",
                        f"Продать: {counts.get('SELL', 0)}",
                        f"Пропустить: {counts.get('PASS', 0)}",
                        f"Недоступны: {unavailable}",
                        f"Показано: {len(visible)}",
                    )
                )
            )

        def update_scope_ui(*_args: Any) -> None:
            is_portfolio = _scope_code() == PORTFOLIO_SCOPE
            title_var.set("Анализ портфеля" if is_portfolio else "Возможности рынка")
            decision_var.set("Все")
            state["results"] = []
            progress_var.set(0.0)
            progress_text_var.set("Готово")
            status_var.set("Готово")
            render()

        def _localize_stage(stage: str) -> str:
            replacements = (
                ("Market Data: candles ", "Рыночные данные: свечи "),
                ("Market Data: ", "Рыночные данные: "),
                ("Анализ стратегий: ", "Анализ стратегий: "),
                ("Risk / Opportunity: ", "Риск и возможность: "),
                ("Decision Engine: ", "Формирование решения: "),
                ("Portfolio Context загружается", "Загрузка контекста портфеля"),
                ("Portfolio Context загружен", "Контекст портфеля загружен"),
                ("Ранжирование возможностей", "Ранжирование возможностей"),
                ("Обработано: ", "Обработано: "),
                ("Сканирование завершено", "Сканирование завершено"),
                ("Вселенная анализа:", "Инструментов для анализа:"),
            )
            localized = stage
            for source, target in replacements:
                if localized.startswith(source) or localized == source:
                    localized = target + localized[len(source):]
                    break
            return localized

        def update_progress(stage: str, percent: float, current: int, total: int) -> None:
            stage = _localize_stage(stage)
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
            profile = _profile_code()

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
                    self.after(0, lambda error=exc: fail(error))

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
