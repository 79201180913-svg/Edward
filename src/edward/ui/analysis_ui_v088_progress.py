from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088
from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011

logger = logging.getLogger(__name__)


def install(app_class: type[Any], client_class: type[Any]) -> None:
    import edward.ui.analysis_ui_v088_frontend as frontend

    if getattr(app_class, "_analysis_ui_v088_progress_installed", False):
        return

    original_open_analysis = getattr(frontend, "install", None)
    if original_open_analysis is None:
        raise RuntimeError("v0.8.8 analysis frontend installer is unavailable")

    # Install the normal frontend first; we only decorate its existing entrypoint.
    original_open_analysis(app_class, client_class)

    import edward.ui.analysis_ui_v04 as legacy
    normal_open_analysis: Callable[[Any], None] = legacy._open_analysis

    def open_analysis_with_progress(app: Any) -> None:
        detail = getattr(app, "instrument_detail", None)
        ticker = str((detail or {}).get("ticker", ""))
        if not detail:
            normal_open_analysis(app)
            return

        progress = tk.Toplevel(app)
        progress.title(f"Анализ {ticker} — выполнение")
        progress.geometry("560x245")
        progress.minsize(520, 225)
        progress.resizable(False, False)
        progress.transient(app)

        outer = ttk.Frame(progress, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=f"Анализ {ticker}",
            font=("TkDefaultFont", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="v0.8.8 Trading Paths + v0.8.11 Market Context",
        ).pack(anchor="w", pady=(2, 14))

        phase_var = tk.StringVar(value="Подготовка анализа…")
        detail_var = tk.StringVar(value="Запуск общего pipeline")
        ttk.Label(outer, textvariable=phase_var, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(outer, textvariable=detail_var, wraplength=500).pack(anchor="w", pady=(5, 12))

        progressbar = ttk.Progressbar(outer, mode="determinate", maximum=4, value=0)
        progressbar.pack(fill="x", pady=(0, 12))
        percent_var = tk.StringVar(value="0 / 4 этапа")
        ttk.Label(outer, textvariable=percent_var).pack(anchor="e")

        closed = False
        stage = 0

        def refresh() -> None:
            if closed:
                return
            try:
                progress.update_idletasks()
                progress.update()
            except tk.TclError:
                pass

        def set_phase(number: int, title: str, detail_text: str = "") -> None:
            nonlocal stage
            stage = max(stage, number)
            phase_var.set(title)
            detail_var.set(detail_text)
            progressbar.configure(value=stage)
            percent_var.set(f"{stage} / 4 этапа")
            refresh()

        original_get_candles = getattr(app.client, "get_candles", None)
        original_get_instrument = getattr(app.client, "get_instrument", None)
        original_context_build = MarketContextRuntimeServiceV011.build
        original_adapter_analyze = AnalysisTradingPathAdapterV088.analyze
        candle_calls = 0

        def get_candles_with_progress(*args: Any, **kwargs: Any) -> Any:
            nonlocal candle_calls
            candle_calls += 1
            if candle_calls == 1:
                set_phase(1, "Этап 1 из 4 — загружаем историю", f"Получаем дневные свечи {ticker}…")
            else:
                set_phase(2, "Этап 2 из 4 — загружаем рынок", "Получаем исторические данные benchmark IMOEX…")
            result = original_get_candles(*args, **kwargs)
            refresh()
            return result

        def get_instrument_with_progress(*args: Any, **kwargs: Any) -> Any:
            set_phase(1, "Этап 1 из 4 — проверяем инструмент", f"Получаем параметры {ticker}…")
            result = original_get_instrument(*args, **kwargs)
            refresh()
            return result

        def context_build_with_progress(*args: Any, **kwargs: Any) -> Any:
            set_phase(2, "Этап 2 из 4 — строим Market Context", "IMOEX → regime → relative strength → volatility…")
            result = original_context_build(*args, **kwargs)
            status = getattr(result[1], "context_status", "UNKNOWN") if isinstance(result, tuple) and len(result) > 1 else "UNKNOWN"
            set_phase(2, "Этап 2 из 4 — Market Context готов", f"Статус контекста: {status}")
            return result

        def adapter_analyze_with_progress(self: Any, *args: Any, **kwargs: Any) -> Any:
            set_phase(3, "Этап 3 из 4 — строим Trading Paths", "Candidate Discovery → validation → overlap → multiple testing → Quality Gate…")
            result = original_adapter_analyze(self, *args, **kwargs)
            candidates = len(getattr(result, "ranked_candidates", ()))
            statuses = [getattr(item.status, "value", item.status) for item in getattr(result, "promotion_results", ())]
            set_phase(
                4,
                "Этап 4 из 4 — формируем итог",
                f"Trading Paths: {candidates} | Promoted: {statuses.count('promoted')} | Research Only: {statuses.count('research_only')} | Rejected: {statuses.count('rejected')}",
            )
            return result

        try:
            if original_get_candles is not None:
                app.client.get_candles = get_candles_with_progress
            if original_get_instrument is not None:
                app.client.get_instrument = get_instrument_with_progress
            MarketContextRuntimeServiceV011.build = context_build_with_progress
            AnalysisTradingPathAdapterV088.analyze = adapter_analyze_with_progress

            set_phase(1, "Этап 1 из 4 — запускаем анализ", f"Подготавливаем данные {ticker}…")
            normal_open_analysis(app)
            set_phase(4, "Анализ завершён", "Все результаты рассчитаны и показаны в окне анализа.")
            progress.after(900, progress.destroy)
            progress.wait_window()
            closed = True
        except Exception:
            closed = True
            try:
                progress.destroy()
            except tk.TclError:
                pass
            raise
        finally:
            if original_get_candles is not None:
                try:
                    app.client.get_candles = original_get_candles
                except Exception:
                    pass
            if original_get_instrument is not None:
                try:
                    app.client.get_instrument = original_get_instrument
                except Exception:
                    pass
            MarketContextRuntimeServiceV011.build = original_context_build
            AnalysisTradingPathAdapterV088.analyze = original_adapter_analyze

    legacy._open_analysis = open_analysis_with_progress
    app_class._analysis_ui_v088_progress_installed = True


__all__ = ["install"]
