from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from edward.services.analysis_service import AnalysisService, Candle, StrategyResult
from edward.services.decision_engine import (
    DecisionEngine,
    DecisionRequest,
    InstrumentContextData,
    MarketContextData,
    OpportunityContext,
    PortfolioContextData,
    PositionContextData,
    RiskContextData,
    Scenario,
    StrategyContextData,
)
from edward.services.instrument_catalog_service import InstrumentCatalogService
from edward.services.instrument_decision_context_service import InstrumentDecisionContextService
from edward.services.market_decision_context_service import MarketDecisionContextService
from edward.services.opportunity_engine import OpportunityEngine
from edward.services.portfolio_decision_context_service import PortfolioDecisionContextService


@dataclass(frozen=True, slots=True)
class OpportunitySearchResult:
    instrument_uid: str
    ticker: str
    name: str
    price: float | None
    market_regime: str | None
    strategy_name: str | None
    strategy_score: float
    opportunity_score: float
    decision: str | None
    status: str
    reason: str
    explanation: str
    quantity: float


class OpportunitySearchService:
    """Run the v0.4 OPPORTUNITY_SEARCH pipeline across the live catalog."""

    def __init__(self, client: Any, analysis_service: AnalysisService | None = None):
        self.client = client
        self.analysis = analysis_service or AnalysisService()
        self.catalog = InstrumentCatalogService(client)
        self.instrument_context = InstrumentDecisionContextService()
        self.market_context = MarketDecisionContextService()
        self.portfolio_context = PortfolioDecisionContextService()

    def scan(self, *, profile: str = "medium_term", instrument_kind: str = "SHARE") -> list[OpportunitySearchResult]:
        instruments = self.catalog.list(instrument_kind, trade_available_only=True)
        account_id = self._active_account()
        positions = self.client.get_positions(account_id) if account_id else None
        portfolio = self.client.get_portfolio(account_id) if account_id else None

        results: list[OpportunitySearchResult] = []
        for instrument in instruments:
            uid = str(_field(instrument, "uid", _field(instrument, "instrument_uid", "")))
            if not uid:
                continue
            results.append(
                self._evaluate_instrument(
                    instrument=instrument,
                    profile=profile,
                    positions=positions,
                    portfolio=portfolio,
                )
            )

        return sorted(
            results,
            key=lambda item: (
                item.decision not in {"BUY", "WAIT"},
                item.decision != "BUY",
                -item.opportunity_score,
            ),
        )

    def _evaluate_instrument(
        self,
        *,
        instrument: Any,
        profile: str,
        positions: Any,
        portfolio: Any,
    ) -> OpportunitySearchResult:
        uid = str(_field(instrument, "uid", _field(instrument, "instrument_uid", "")))
        ticker = str(_field(instrument, "ticker", ""))
        name = str(_field(instrument, "name", ""))
        raw_price = _field(instrument, "last_price", None)
        price = _float_or_none(raw_price)
        position_context = self.portfolio_context.build(
            positions=positions,
            portfolio=portfolio,
            instrument_uid=uid,
        ) if positions is not None else _empty_portfolio()

        try:
            trading_status = _field(instrument, "trading_status", None)
            instrument_data = self.instrument_context.build(instrument, trading_status)
            candles = self._get_candles(uid)
            if len(candles) < 150:
                return self._unavailable(
                    instrument, price, position_context.position.quantity, "Недостаточно исторических данных для анализа."
                )

            analysis = self.analysis.analyze(
                instrument_uid=uid,
                ticker=ticker,
                candles=candles,
                profile=profile,
            )
            selected = self._best_strategy(analysis.strategies)
            market = self.market_context.build(
                last_price=raw_price,
                candles=candles,
                market_regime=analysis.market_regime,
            )

            if selected is None:
                opportunity_context = OpportunityContext(
                    opportunity_score=0.0,
                    entry_ok=False,
                    risk_ok=True,
                    strategy_ok=False,
                    market_regime_compatible=False,
                    critical_risk=False,
                )
                strategy_context = StrategyContextData(
                    strategy_name=None,
                    strategy_score=0.0,
                    quality_gate=False,
                    available=True,
                )
                explanation = "Приемлемая стратегия не сформирована."
            else:
                opportunity = OpportunityEngine.evaluate(analysis, candles, selected if selected.quality_gate else None)
                opportunity_context = opportunity.context
                strategy_context = StrategyContextData(
                    strategy_name=selected.strategy,
                    strategy_score=selected.score,
                    walk_forward_score=selected.test_score,
                    stability_score=selected.stability,
                    confidence=analysis.confidence,
                    quality_gate=selected.quality_gate,
                    entry_signal=bool(selected.quality_gate and opportunity_context.entry_ok),
                    quality_degraded=not selected.quality_gate,
                    available=True,
                )
                explanation = opportunity.explanation

            risk_context = RiskContextData(
                risk_gate=opportunity_context.risk_ok,
                critical_risk=opportunity_context.critical_risk,
                max_drawdown_pct=selected.max_drawdown_pct if selected else None,
                available=True,
            )
            portfolio_data = position_context.portfolio
            position_data = position_context.position
            portfolio_data = PortfolioContextData(
                portfolio_value=portfolio_data.portfolio_value,
                available_cash=portfolio_data.available_cash,
                blocked_cash=portfolio_data.blocked_cash,
                current_weight_pct=portfolio_data.current_weight_pct,
                target_weight_pct=portfolio_data.target_weight_pct,
                max_position_weight_pct=portfolio_data.max_position_weight_pct,
                allows_buy=portfolio_data.allows_buy and not position_data.is_open,
                allows_add=portfolio_data.allows_add and position_data.is_open,
                available=portfolio_data.available if account_id_or_none(positions, portfolio) else True,
            )

            request = DecisionRequest(
                scenario=Scenario.OPPORTUNITY_SEARCH,
                instrument=instrument_data,
                market=market,
                strategy=strategy_context,
                risk=risk_context,
                position=position_data,
                portfolio=portfolio_data,
                opportunity=opportunity_context,
                portfolio_allows_buy=portfolio_data.allows_buy,
                portfolio_allows_add=portfolio_data.allows_add,
                market_data_available=market.available,
                strategy_analysis_available=True,
                risk_analysis_available=True,
                portfolio_context_available=(not position_data.is_open) or portfolio_data.available,
                instrument_available=instrument_data.available,
                profile=profile,
            )
            decision = DecisionEngine.evaluate(request)
            reason = decision.reason_codes[0] if decision.reason_codes else ""
            return OpportunitySearchResult(
                instrument_uid=uid,
                ticker=ticker,
                name=name,
                price=market.current_price if market.current_price is not None else price,
                market_regime=analysis.market_regime,
                strategy_name=decision.strategy_name,
                strategy_score=decision.strategy_score,
                opportunity_score=decision.opportunity_score,
                decision=decision.decision.value if decision.decision else None,
                status=decision.status.value,
                reason=reason,
                explanation=decision.explanation,
                quantity=position_data.quantity,
            )
        except Exception as exc:
            return self._unavailable(instrument, price, position_context.position.quantity, f"Ошибка анализа: {exc}")

    @staticmethod
    def _best_strategy(strategies: list[StrategyResult]) -> StrategyResult | None:
        if not strategies:
            return None
        passing = [item for item in strategies if item.quality_gate]
        return max(passing or strategies, key=lambda item: item.score)

    def _get_candles(self, instrument_uid: str) -> list[Candle]:
        payload = self.client.get_candles(
            instrument_uid,
            interval="CANDLE_INTERVAL_DAY",
            days=2400,
        )
        items = payload.get("candles", []) if isinstance(payload, dict) else []
        result: list[Candle] = []
        for item in items:
            timestamp = _field(item, "time", _field(item, "timestamp", None))
            if timestamp is None:
                continue
            result.append(
                Candle(
                    timestamp=_parse_timestamp(timestamp),
                    open=_number(_field(item, "open", 0)),
                    high=_number(_field(item, "high", 0)),
                    low=_number(_field(item, "low", 0)),
                    close=_number(_field(item, "close", 0)),
                    volume=_number(_field(item, "volume", 0)),
                )
            )
        return result

    def _active_account(self) -> str | None:
        try:
            accounts = self.client.get_accounts()
            items = accounts if isinstance(accounts, list) else _field(accounts, "accounts", []) or []
            active = next((item for item in items if str(_field(item, "status", "")).upper().endswith("OPEN")), None)
            return str(_field(active, "id", "")) if active else None
        except Exception:
            return None

    @staticmethod
    def _unavailable(instrument: Any, price: float | None, quantity: float, reason: str) -> OpportunitySearchResult:
        return OpportunitySearchResult(
            instrument_uid=str(_field(instrument, "uid", _field(instrument, "instrument_uid", ""))),
            ticker=str(_field(instrument, "ticker", "")),
            name=str(_field(instrument, "name", "")),
            price=price,
            market_regime=None,
            strategy_name=None,
            strategy_score=0.0,
            opportunity_score=0.0,
            decision=None,
            status="ANALYSIS_UNAVAILABLE",
            reason="ANALYSIS_UNAVAILABLE",
            explanation=reason,
            quantity=quantity,
        )


def _empty_portfolio():
    from edward.services.portfolio_decision_context_service import PortfolioDecisionContext

    return PortfolioDecisionContext(
        portfolio=PortfolioContextData(available=False),
        position=PositionContextData(),
    )


def account_id_or_none(positions: Any, portfolio: Any) -> bool:
    return positions is not None and portfolio is not None


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _number(value: Any) -> float:
    if isinstance(value, dict):
        return float(value.get("units", 0)) + float(value.get("nano", 0)) / 1_000_000_000
    try:
        return float(value)
    except Exception:
        return 0.0


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value in (None, "") else _number(value)
    except Exception:
        return None


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)
