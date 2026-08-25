from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from edward.services.decision_engine import RiskContextData
from edward.services.instrument_decision_context_service import InstrumentDecisionContextService
from edward.services.market_decision_context_service import MarketDecisionContextService
from edward.services.opportunity_engine import OpportunityEngine
from edward.services.portfolio_decision_context_service import PortfolioDecisionContextService


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _refresh_context(app: Any) -> None:
    detail = getattr(app, "instrument_detail", None)
    variables = getattr(app, "decision_context_vars", None)
    if not detail or not variables:
        return

    uid = str(detail.get("instrument_uid") or detail.get("uid") or "")
    variables["uid"].set(uid or "—")
    if not uid:
        variables["available"].set("Нет UID")
        return

    try:
        status = app.client.get_trading_status(uid)
        instrument_context = InstrumentDecisionContextService().build(detail, status)
        variables["status"].set(instrument_context.trading_status or "—")
        variables["buy"].set("ДА" if instrument_context.buy_available else "НЕТ")
        variables["sell"].set("ДА" if instrument_context.sell_available else "НЕТ")
        variables["available"].set("ДА" if instrument_context.available else "НЕТ")

        prices = app.client.get_last_prices([uid])
        items = prices if isinstance(prices, list) else _field(prices, "last_prices", []) or []
        price_item = next(
            (item for item in items if str(_field(item, "instrument_uid", _field(item, "uid", ""))) == uid),
            None,
        )
        market_context = MarketDecisionContextService().build(
            last_price=_field(price_item, "price") if price_item is not None else None
        )
        variables["price"].set(
            f"{market_context.current_price:.4f}" if market_context.current_price is not None else "—"
        )

        account_id = getattr(app.context, "active_account_id", None)
        if account_id:
            positions = app.client.get_positions(account_id)
            portfolio = app.client.get_portfolio(account_id)
            context = PortfolioDecisionContextService().build(
                positions=positions,
                portfolio=portfolio,
                instrument_uid=uid,
            )
            p = context.portfolio
            pos = context.position
            variables["portfolio"].set(
                f"{p.portfolio_value:,.2f}" if p.portfolio_value is not None else "—"
            )
            variables["cash"].set(
                f"{p.available_cash:,.2f}" if p.available_cash is not None else "—"
            )
            variables["weight"].set(f"{pos.portfolio_weight_pct:.2f}%")
            variables["position"].set("есть" if pos.is_open else "нет")
        else:
            for key in ("portfolio", "cash", "weight", "position"):
                variables[key].set("—")
    except Exception as exc:
        variables["status"].set(f"Ошибка: {exc}")
        for key in ("price", "buy", "sell", "available", "portfolio", "cash", "weight", "position"):
            variables[key].set("—")


def _install_analysis_context_pipeline() -> None:
    """Patch the v0.4 analysis pipeline to use the same structured context as UI."""
    import edward.ui.analysis_ui_v04 as module

    if getattr(module, "_decision_context_pipeline_v04_installed", False):
        return

    original_builder = module._build_decision_request
    original_opportunity = OpportunityEngine.evaluate

    def evaluate_with_fallback(
        cls: type[Any], analysis: Any, candles: list[Any], strategy_result: Any | None
    ):
        selected = strategy_result
        if selected is None and getattr(analysis, "strategies", None):
            selected = max(analysis.strategies, key=lambda item: item.score)
        return original_opportunity(analysis, candles, selected)

    OpportunityEngine.evaluate = classmethod(evaluate_with_fallback)

    def build_request(
        app: Any,
        detail: dict[str, Any],
        result: Any,
        opportunity: Any,
        strategy_result: Any | None,
        position: Any,
        profile: str,
    ):
        selected = strategy_result
        if selected is None and getattr(result, "strategies", None):
            selected = max(result.strategies, key=lambda item: item.score)

        request = original_builder(app, detail, result, opportunity, selected, position, profile)

        account_id = getattr(app.context, "active_account_id", None)
        portfolio_context = request.portfolio
        portfolio_position = request.position
        portfolio_available = False
        if account_id:
            try:
                positions = app.client.get_positions(account_id)
                portfolio = app.client.get_portfolio(account_id)
                context = PortfolioDecisionContextService().build(
                    positions=positions,
                    portfolio=portfolio,
                    instrument_uid=str(detail.get("instrument_uid") or detail.get("uid") or ""),
                )
                portfolio_context = context.portfolio
                portfolio_position = context.position
                portfolio_available = context.portfolio.available
            except Exception:
                portfolio_available = False

        strategy_context = request.strategy
        if selected is not None:
            strategy_context = type(strategy_context)(
                strategy_id=getattr(strategy_context, "strategy_id", None),
                strategy_name=selected.strategy,
                strategy_score=selected.score,
                walk_forward_score=selected.test_score,
                stability_score=selected.stability,
                confidence=getattr(result, "confidence", None),
                quality_gate=selected.quality_gate,
                entry_signal=bool(selected.quality_gate and opportunity.context.entry_ok),
                exit_signal=False,
                quality_degraded=not selected.quality_gate,
                signal_degraded=False,
                available=True,
            )

        risk_context = RiskContextData(
            risk_gate=opportunity.context.risk_ok,
            critical_risk=opportunity.context.critical_risk,
            risk_score=None,
            max_drawdown_pct=selected.max_drawdown_pct if selected is not None else None,
            risk_reward=None,
            available=True,
        )

        return type(request)(
            scenario=request.scenario,
            instrument=request.instrument,
            market=request.market,
            strategy=strategy_context,
            risk=risk_context,
            position=portfolio_position,
            portfolio=portfolio_context,
            opportunity=request.opportunity,
            portfolio_allows_buy=portfolio_context.allows_buy,
            portfolio_allows_add=portfolio_context.allows_add,
            exit_signal=request.exit_signal,
            strategy_quality_degraded=request.strategy_quality_degraded,
            signal_degraded=request.signal_degraded,
            market_regime_degraded=request.market_regime_degraded,
            market_data_available=request.market_data_available,
            strategy_analysis_available=True,
            risk_analysis_available=True,
            portfolio_context_available=(portfolio_available or not portfolio_position.is_open),
            instrument_available=request.instrument.available,
            profile=profile,
        )

    module._build_decision_request = build_request
    module._decision_context_pipeline_v04_installed = True


def install_decision_context_ui(app_class: type[Any]) -> None:
    _install_analysis_context_pipeline()
    if getattr(app_class, "_decision_context_ui_v04_installed", False):
        return

    original_page = app_class._page_instrument

    def page_instrument(self: Any) -> None:
        original_page(self)
        detail = getattr(self, "instrument_detail", None)
        if not detail or getattr(self, "decision_context_frame", None) is not None:
            return

        frame = ttk.LabelFrame(self.content, text="Decision Engine 0.4 — текущий контекст", padding=10)
        frame.pack(fill="x", pady=(10, 0))
        self.decision_context_frame = frame

        variables = {
            "uid": tk.StringVar(value="—"),
            "price": tk.StringVar(value="—"),
            "status": tk.StringVar(value="—"),
            "buy": tk.StringVar(value="—"),
            "sell": tk.StringVar(value="—"),
            "available": tk.StringVar(value="—"),
            "portfolio": tk.StringVar(value="—"),
            "cash": tk.StringVar(value="—"),
            "weight": tk.StringVar(value="—"),
            "position": tk.StringVar(value="—"),
        }
        self.decision_context_vars = variables

        rows = (
            ("UID", "uid"),
            ("Текущая цена", "price"),
            ("Trading Status", "status"),
            ("BUY доступен", "buy"),
            ("SELL доступен", "sell"),
            ("Инструмент доступен", "available"),
            ("Portfolio Value", "portfolio"),
            ("Available Cash", "cash"),
            ("Current Weight", "weight"),
            ("Position", "position"),
        )
        for index, (label, key) in enumerate(rows):
            row = index // 5
            column = (index % 5) * 2
            frame.columnconfigure(column, weight=0)
            frame.columnconfigure(column + 1, weight=1)
            ttk.Label(frame, text=f"{label}:").grid(row=row, column=column, sticky="w", padx=(0, 5), pady=2)
            ttk.Label(frame, textvariable=variables[key]).grid(row=row, column=column + 1, sticky="w", padx=(0, 16), pady=2)

        ttk.Button(
            frame,
            text="Обновить контекст",
            command=lambda: _refresh_context(self),
        ).grid(row=2, column=8, columnspan=2, sticky="e", padx=(10, 0), pady=(4, 0))
        _refresh_context(self)

    app_class._page_instrument = page_instrument
    app_class._decision_context_ui_v04_installed = True
