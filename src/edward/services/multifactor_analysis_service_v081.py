from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence

MULTIFACTOR_VERSION = "0.8.1"


@dataclass(frozen=True, slots=True)
class Evidence:
    name: str
    direction: str
    strength: float
    reliability: float
    freshness: float = 100.0
    available: bool = True
    reason: str | None = None

    @property
    def quality(self) -> float:
        if not self.available:
            return 0.0
        return max(0.0, min(100.0, self.strength)) * max(0.0, min(100.0, self.reliability)) / 100.0 * max(0.0, min(100.0, self.freshness)) / 100.0


@dataclass(frozen=True, slots=True)
class FundamentalFactor:
    quality_score: float
    growth_score: float
    valuation_score: float
    balance_sheet_score: float
    cash_flow_score: float
    shareholder_return_score: float
    momentum_score: float
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class MicrostructureFactor:
    spread_pct: float | None
    depth_score: float
    order_imbalance_pct: float | None
    trade_imbalance_pct: float | None
    liquidity_score: float
    entry_quality_score: float
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class VolumePressureFactor:
    buy_pressure_pct: float | None
    sell_pressure_pct: float | None
    net_pressure_pct: float | None
    accumulation_score: float
    distribution_score: float
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class SignalFactor:
    current_direction: str | None
    historical_hit_rate_pct: float | None
    historical_avg_return_pct: float | None
    reliability_pct: float
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class EventRiskFactor:
    days_to_event: int | None
    event_risk_score: float
    historical_gap_pct: float | None
    historical_post_event_volatility_pct: float | None
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class DividendFactor:
    yield_pct: float | None
    payout_pct: float | None
    growth_score: float
    stability_score: float
    total_return_contribution_pct: float | None
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class InsiderFactor:
    net_direction: str
    activity_score: float
    historical_follow_through_pct: float | None
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class SessionFactor:
    session: str
    quality_score: float
    is_execution_allowed: bool
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class InstrumentRiskFactor:
    long_margin_rate_pct: float | None
    short_margin_rate_pct: float | None
    short_enabled: bool
    capital_efficiency_score: float
    risk_score: float
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class PortfolioFactor:
    current_weight_pct: float
    concentration_score: float
    marginal_risk_pct: float
    diversification_benefit_pct: float
    expected_return_impact_pct: float
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class MultiFactorResult:
    fundamentals: FundamentalFactor
    microstructure: MicrostructureFactor
    volume_pressure: VolumePressureFactor
    signals: SignalFactor
    event_risk: EventRiskFactor
    dividends: DividendFactor
    insider: InsiderFactor
    session: SessionFactor
    instrument_risk: InstrumentRiskFactor
    portfolio: PortfolioFactor
    aggregate_evidence_score: float
    aggregate_reliability_score: float
    conflict_penalty: float
    version: str = MULTIFACTOR_VERSION


def _value(data: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(data, Mapping) and name in data:
            return data[name]
        if hasattr(data, name):
            return getattr(data, name)
    return default


def _num(data: Any, *names: str, default: float | None = None) -> float | None:
    value = _value(data, *names, default=default)
    try:
        result = float(value)
        return result if isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _score_positive(value: float | None, *, neutral: float = 50.0, scale: float = 1.0) -> float:
    if value is None:
        return neutral
    return _clamp(neutral + value * scale)


def _ratio_score(numerator: float | None, denominator: float | None, *, neutral: float = 50.0, scale: float = 50.0) -> float:
    if numerator is None or denominator is None or denominator == 0:
        return neutral
    return _clamp(neutral + (numerator / denominator - 1.0) * scale)


class MultiFactorAnalysisServiceV081:
    """Contract-friendly factor layer for v0.8.1.

    Fundamental scoring is delegated to the structured v0.8.2 service when
    fundamentals are supplied, avoiding duplicate semantic scoring in V081.
    """

    @classmethod
    def fundamentals(cls, snapshot: Any) -> FundamentalFactor:
        if snapshot is None:
            return FundamentalFactor(0, 0, 0, 0, 0, 0, 0, Evidence("fundamentals", "UNAVAILABLE", 0, 0, available=False, reason="NO_FUNDAMENTAL_DATA"))

        try:
            from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisServiceV082

            if isinstance(snapshot, Mapping) and snapshot:
                profile = str(snapshot.get("strategy_profile") or snapshot.get("profile") or "medium_term")
                result = FundamentalAnalysisServiceV082.analyze(snapshot, profile=profile)
                score = result.overall_score
                direction = "POSITIVE" if score >= 60 else "NEGATIVE" if score < 40 else "NEUTRAL"
                reliability = result.confidence
                return FundamentalFactor(
                    result.business_quality.score,
                    result.growth.score,
                    result.valuation.score,
                    result.financial_health.score,
                    result.cash_generation.score,
                    result.shareholder_return.score,
                    result.fundamental_momentum.score,
                    Evidence("fundamentals", direction, score, reliability, available=result.status != "UNAVAILABLE", reason=None if result.status != "UNAVAILABLE" else "NO_FUNDAMENTAL_DATA"),
                )
        except Exception:
            # Compatibility fallback for direct V081 callers.
            pass

        roe = _num(snapshot, "roe", "return_on_equity")
        roic = _num(snapshot, "roic", "return_on_invested_capital")
        margin = _num(snapshot, "net_margin", "net_profit_margin")
        revenue_growth = _num(snapshot, "revenue_growth", "revenue_growth_1y")
        revenue_growth_3y = _num(snapshot, "revenue_growth_3y")
        revenue_growth_5y = _num(snapshot, "revenue_growth_5y")
        eps_growth = _num(snapshot, "eps_growth", "eps_growth_1y")
        ebitda_growth = _num(snapshot, "ebitda_growth", "ebitda_growth_1y")
        debt_ebitda = _num(snapshot, "net_debt_to_ebitda", "debt_to_ebitda")
        current_ratio = _num(snapshot, "current_ratio")
        fcf = _num(snapshot, "free_cash_flow", "fcf")
        pe = _num(snapshot, "pe", "p_e")
        ps = _num(snapshot, "ps", "p_s")
        pb = _num(snapshot, "pb", "p_b")
        pfcf = _num(snapshot, "p_fcf")
        dividend_yield = _num(snapshot, "dividend_yield")
        payout = _num(snapshot, "dividend_payout", "payout_ratio")
        profitability = mean([_score_positive(roe, scale=1.8), _score_positive(roic, scale=2.0), _score_positive(margin, scale=2.0)])
        growth_inputs = [revenue_growth, eps_growth, ebitda_growth]
        growth_scores = [_score_positive(value, scale=1.5) for value in growth_inputs]
        for value in (revenue_growth_3y, revenue_growth_5y):
            if value is not None:
                growth_scores.append(_score_positive(value, scale=1.5))
        growth = mean(growth_scores)
        balance = mean([_clamp(75.0 - max(0.0, debt_ebitda or 0.0) * 12.0), _score_positive((current_ratio or 1.0) - 1.0, scale=25.0)])
        cash_flow = _score_positive(fcf, neutral=50.0, scale=0.000001)
        valuations = [x for x in (pe, ps, pb, pfcf) if x is not None and x > 0]
        valuation = _clamp(80.0 - mean(valuations) * 1.5) if valuations else 50.0
        shareholder = mean([_score_positive(dividend_yield, scale=5.0), _clamp(90.0 - max(0.0, (payout or 0.0) - 60.0))])
        momentum = mean([_score_positive(revenue_growth, scale=1.2), _score_positive(eps_growth, scale=1.2)])
        quality = _clamp(mean([profitability, growth, balance, cash_flow, valuation]))
        direction = "POSITIVE" if quality >= 60 else "NEGATIVE" if quality < 40 else "NEUTRAL"
        reliability = 75.0 if sum(x is not None for x in (roe, roic, margin, revenue_growth, revenue_growth_3y, revenue_growth_5y, eps_growth, ebitda_growth, debt_ebitda, current_ratio, fcf, pe)) >= 7 else 50.0
        evidence = Evidence("fundamentals", direction, quality, reliability)
        return FundamentalFactor(quality, growth, valuation, balance, cash_flow, shareholder, momentum, evidence)

    @classmethod
    def microstructure(cls, order_book: Any = None, trades: Sequence[Any] | None = None, current_price: float | None = None) -> MicrostructureFactor:
        if order_book is None and not trades:
            return MicrostructureFactor(None, 0, None, None, 0, 0, Evidence("microstructure", "UNAVAILABLE", 0, 0, available=False, reason="NO_MICROSTRUCTURE_DATA"))
        bids = list(_value(order_book, "bids", default=[]) or []) if order_book is not None else []
        asks = list(_value(order_book, "asks", default=[]) or []) if order_book is not None else []
        best_bid = _num(bids[0], "price") if bids else None
        best_ask = _num(asks[0], "price") if asks else None
        if best_bid is None or best_ask is None:
            bids = []
            asks = []
        mid = ((best_bid or 0.0) + (best_ask or 0.0)) / 2.0
        spread_pct = ((best_ask - best_bid) / mid * 100.0) if best_bid is not None and best_ask is not None and mid > 0 else None
        bid_depth = sum(_num(x, "quantity", default=0.0) or 0.0 for x in bids[:10])
        ask_depth = sum(_num(x, "quantity", default=0.0) or 0.0 for x in asks[:10])
        total_depth = bid_depth + ask_depth
        order_imbalance = ((bid_depth - ask_depth) / total_depth * 100.0) if total_depth else None
        trade_buy = trade_sell = 0.0
        for trade in trades or ():
            qty = _num(trade, "quantity", "volume", default=0.0) or 0.0
            direction = str(_value(trade, "direction", default="")).upper()
            if "BUY" in direction: trade_buy += qty
            elif "SELL" in direction: trade_sell += qty
        total_trade = trade_buy + trade_sell
        trade_imbalance = ((trade_buy - trade_sell) / total_trade * 100.0) if total_trade else None
        spread_score = _clamp(100.0 - (spread_pct or 2.0) * 30.0)
        depth_score = _clamp(50.0 + min(50.0, total_depth / max(1.0, (current_price or mid or 1.0)) * 5.0)) if total_depth else 30.0
        liquidity = _clamp(spread_score * 0.55 + depth_score * 0.45)
        entry = _clamp(liquidity + (order_imbalance or 0.0) * 0.15 + (trade_imbalance or 0.0) * 0.1)
        direction = "POSITIVE" if entry >= 60 else "NEGATIVE" if entry < 40 else "NEUTRAL"
        reliability = 80.0 if order_book is not None and trades else 60.0
        return MicrostructureFactor(spread_pct, depth_score, order_imbalance, trade_imbalance, liquidity, entry, Evidence("microstructure", direction, entry, reliability))

    @classmethod
    def volume_pressure(cls, candles: Sequence[Any]) -> VolumePressureFactor:
        buy = sell = 0.0
        for candle in candles:
            vb = _num(candle, "volume_buy")
            vs = _num(candle, "volume_sell")
            if vb is not None: buy += max(0.0, vb)
            if vs is not None: sell += max(0.0, vs)
        denominator = buy + sell
        if denominator <= 0:
            return VolumePressureFactor(None, None, None, 0, 0, Evidence("volume_pressure", "UNAVAILABLE", 0, 0, available=False, reason="NO_BUY_SELL_VOLUME"))
        buy_pct = buy / denominator * 100.0
        sell_pct = sell / denominator * 100.0
        net = buy_pct - sell_pct
        accumulation = _clamp(50.0 + net)
        distribution = _clamp(50.0 - net)
        direction = "POSITIVE" if accumulation >= 60 else "NEGATIVE" if accumulation < 40 else "NEUTRAL"
        return VolumePressureFactor(buy_pct, sell_pct, net, accumulation, distribution, Evidence("volume_pressure", direction, accumulation, 75.0))

    @classmethod
    def signals(cls, current_signal: Any = None, historical_signals: Sequence[Any] | None = None) -> SignalFactor:
        if current_signal is None and not historical_signals:
            return SignalFactor(None, None, None, 0.0, Evidence("signals", "UNAVAILABLE", 0, 0, available=False, reason="NO_SIGNAL_DATA"))
        outcomes = []
        for item in historical_signals or ():
            probability = _num(item, "probability")
            target = _num(item, "target_price")
            close = _num(item, "close_price")
            initial = _num(item, "initial_price")
            if close is not None and initial not in (None, 0):
                ret = (close / initial - 1.0) * 100.0
                direction = str(_value(item, "direction", default="")).upper()
                hit = ret > 0 if "BUY" in direction else ret < 0 if "SELL" in direction else ret != 0
                outcomes.append((hit, ret, probability))
            elif target is not None and initial not in (None, 0) and probability is not None:
                outcomes.append((target > initial, (target / initial - 1.0) * 100.0, probability))
        hit_rate = mean([1.0 if x[0] else 0.0 for x in outcomes]) * 100.0 if outcomes else None
        avg_return = mean([x[1] for x in outcomes]) if outcomes else None
        reliability = _clamp((hit_rate or 50.0) * 0.7 + min(len(outcomes), 50) * 0.6) if outcomes else 40.0
        direction = str(_value(current_signal, "direction", default="NEUTRAL")).upper() if current_signal is not None else "NEUTRAL"
        normalized = "POSITIVE" if "BUY" in direction else "NEGATIVE" if "SELL" in direction else "NEUTRAL"
        strength = _clamp(abs((hit_rate or 50.0) - 50.0) * 2.0)
        return SignalFactor(direction if current_signal is not None else None, hit_rate, avg_return, reliability, Evidence("signals", normalized, strength, reliability))

    @classmethod
    def event_risk(cls, event: Any = None, historical_gaps_pct: Sequence[float] | None = None, historical_vol_pct: Sequence[float] | None = None, now: datetime | None = None) -> EventRiskFactor:
        if event is None:
            return EventRiskFactor(None, 0.0, None, None, Evidence("event_risk", "UNAVAILABLE", 0, 0, available=False, reason="NO_EVENT_DATA"))
        when = _value(event, "report_date", "event_date", "created_at")
        current = now or datetime.now(timezone.utc)
        days = None
        if isinstance(when, datetime):
            days = (when.date() - current.date()).days
        elif isinstance(when, str):
            try:
                parsed = datetime.fromisoformat(when.replace("Z", "+00:00"))
                days = (parsed.date() - current.date()).days
            except ValueError:
                pass
        avg_gap = mean(historical_gaps_pct) if historical_gaps_pct else None
        avg_vol = mean(historical_vol_pct) if historical_vol_pct else None
        if days is None: score = 20.0 if avg_gap or avg_vol else 0.0
        elif days <= 2: score = 90.0
        elif days <= 7: score = 70.0
        elif days <= 21: score = 45.0
        else: score = 15.0
        direction = "NEGATIVE" if score >= 70 else "NEUTRAL"
        return EventRiskFactor(days, score, avg_gap, avg_vol, Evidence("event_risk", direction, score, 80.0))

    @classmethod
    def dividends(cls, snapshot: Any = None) -> DividendFactor:
        if snapshot is None:
            return DividendFactor(None, None, 0, 0, None, Evidence("dividends", "UNAVAILABLE", 0, 0, available=False, reason="NO_DIVIDEND_DATA"))
        yield_pct = _num(snapshot, "dividend_yield")
        payout = _num(snapshot, "dividend_payout", "payout_ratio")
        growth = _num(snapshot, "dividend_growth")
        regularity = _num(snapshot, "dividend_regularity")
        growth_score = _score_positive(growth, scale=2.0)
        stability = _score_positive(regularity, scale=1.0)
        contribution = yield_pct
        strength = _clamp(50.0 + (yield_pct or 0.0) * 5.0 - max(0.0, (payout or 0.0) - 60.0) * 0.4)
        direction = "POSITIVE" if strength >= 60 else "NEGATIVE" if strength < 40 else "NEUTRAL"
        return DividendFactor(yield_pct, payout, growth_score, stability, contribution, Evidence("dividends", direction, strength, 75.0))

    @classmethod
    def insiders(cls, transactions: Sequence[Any] | None = None) -> InsiderFactor:
        if not transactions:
            return InsiderFactor("UNAVAILABLE", 0, None, Evidence("insiders", "UNAVAILABLE", 0, 0, available=False, reason="NO_INSIDER_DATA"))
        signed = []
        follow = []
        for tx in transactions:
            action = str(_value(tx, "type", "operation", default="")).upper()
            qty = _num(tx, "quantity", "amount", default=0.0) or 0.0
            signed.append(qty if "BUY" in action else -qty if "SELL" in action else 0.0)
            outcome = _num(tx, "follow_through_pct")
            if outcome is not None: follow.append(outcome)
        net = sum(signed)
        direction = "BUY" if net > 0 else "SELL" if net < 0 else "NEUTRAL"
        strength = _clamp(50.0 + min(50.0, abs(net) * 10.0))
        normalized = "POSITIVE" if net > 0 else "NEGATIVE" if net < 0 else "NEUTRAL"
        return InsiderFactor(direction, strength, mean(follow) if follow else None, Evidence("insiders", normalized, strength, 60.0 if follow else 45.0))

    @classmethod
    def session(cls, session: str | None, *, execution_allowed: bool = True) -> SessionFactor:
        value = (session or "UNKNOWN").upper()
        quality = {"REGULAR": 100.0, "OPENING_AUCTION": 80.0, "CLOSING_AUCTION": 80.0, "EVENING": 70.0, "PREMARKET": 45.0, "CLEARING": 0.0, "UNKNOWN": 50.0}.get(value, 50.0)
        allowed = execution_allowed and value != "CLEARING"
        direction = "POSITIVE" if quality >= 70 else "NEGATIVE" if quality < 40 else "NEUTRAL"
        return SessionFactor(value, quality, allowed, Evidence("session", direction, quality, 90.0))

    @classmethod
    def instrument_risk(cls, risk_data: Any = None) -> InstrumentRiskFactor:
        if risk_data is None:
            return InstrumentRiskFactor(None, None, False, 0, 0, Evidence("instrument_risk", "UNAVAILABLE", 0, 0, available=False, reason="NO_RISK_RATE_DATA"))
        dlong = _num(risk_data, "dlong_client", "dlong")
        dshort = _num(risk_data, "dshort_client", "dshort")
        short_value = _value(risk_data, "short_enabled_flag", "short_enabled", default=None)
        short_enabled = bool(short_value) if short_value is not None else False
        if dlong is None and dshort is None:
            return InstrumentRiskFactor(None, None, short_enabled, 0, 0, Evidence("instrument_risk", "UNAVAILABLE", 0, 0, available=False, reason="INCOMPLETE_RISK_RATE_DATA"))
        effective_margin = dlong if not short_enabled or dshort is None else max(dlong or 0.0, dshort)
        capital = _clamp(100.0 - effective_margin)
        risk = _clamp(50.0 + effective_margin * (40.0 / 30.0))
        direction = "NEGATIVE" if risk >= 65 else "NEUTRAL"
        return InstrumentRiskFactor(dlong, dshort, short_enabled, capital, risk, Evidence("instrument_risk", direction, risk, 90.0))

    @classmethod
    def portfolio(cls, *, current_weight_pct: float = 0.0, marginal_risk_pct: float = 0.0, diversification_benefit_pct: float = 0.0, expected_return_impact_pct: float = 0.0, max_position_weight_pct: float | None = None) -> PortfolioFactor:
        concentration = _clamp(100.0 - current_weight_pct / max_position_weight_pct * 100.0) if max_position_weight_pct and max_position_weight_pct > 0 else _clamp(100.0 - current_weight_pct * 2.0)
        score = _clamp(concentration + diversification_benefit_pct * 2.0 - max(0.0, marginal_risk_pct) * 4.0)
        direction = "POSITIVE" if score >= 60 else "NEGATIVE" if score < 40 else "NEUTRAL"
        return PortfolioFactor(current_weight_pct, concentration, marginal_risk_pct, diversification_benefit_pct, expected_return_impact_pct, Evidence("portfolio", direction, score, 85.0))

    @classmethod
    def aggregate(cls, factors: Sequence[Evidence]) -> tuple[float, float, float]:
        available = [factor for factor in factors if factor.available]
        if not available: return 0.0, 0.0, 0.0
        weighted = [factor.quality for factor in available]
        reliability = mean(factor.reliability for factor in available)
        positives = sum(1 for f in available if f.direction == "POSITIVE")
        negatives = sum(1 for f in available if f.direction == "NEGATIVE")
        conflict = min(30.0, abs(positives - negatives) == 0 and positives * 5.0 or min(30.0, min(positives, negatives) * 3.0))
        return mean(weighted), reliability, conflict

    @classmethod
    def analyze(cls, *, fundamentals: Any = None, order_book: Any = None, trades: Sequence[Any] | None = None, candles: Sequence[Any] = (), current_signal: Any = None, historical_signals: Sequence[Any] | None = None, event: Any = None, historical_gaps_pct: Sequence[float] | None = None, historical_event_vol_pct: Sequence[float] | None = None, dividend_data: Any = None, insider_transactions: Sequence[Any] | None = None, session_name: str | None = None, session_execution_allowed: bool = True, risk_data: Any = None, current_weight_pct: float = 0.0, marginal_risk_pct: float = 0.0, diversification_benefit_pct: float = 0.0, expected_return_impact_pct: float = 0.0, max_position_weight_pct: float | None = None, current_price: float | None = None) -> MultiFactorResult:
        fundamental = cls.fundamentals(fundamentals)
        micro = cls.microstructure(order_book, trades, current_price)
        volume = cls.volume_pressure(candles)
        signal = cls.signals(current_signal, historical_signals)
        event_factor = cls.event_risk(event, historical_gaps_pct, historical_event_vol_pct)
        dividend = cls.dividends(dividend_data)
        insider = cls.insiders(insider_transactions)
        session_factor = cls.session(session_name, execution_allowed=session_execution_allowed)
        risk = cls.instrument_risk(risk_data)
        portfolio = cls.portfolio(current_weight_pct=current_weight_pct, marginal_risk_pct=marginal_risk_pct, diversification_benefit_pct=diversification_benefit_pct, expected_return_impact_pct=expected_return_impact_pct, max_position_weight_pct=max_position_weight_pct)
        evidence = [fundamental.evidence, micro.evidence, volume.evidence, signal.evidence, event_factor.evidence, dividend.evidence, insider.evidence, session_factor.evidence, risk.evidence, portfolio.evidence]
        score, reliability, conflict = cls.aggregate(evidence)
        return MultiFactorResult(fundamental, micro, volume, signal, event_factor, dividend, insider, session_factor, risk, portfolio, score, reliability, conflict)


__all__ = ["MULTIFACTOR_VERSION", "Evidence", "FundamentalFactor", "MicrostructureFactor", "VolumePressureFactor", "SignalFactor", "EventRiskFactor", "DividendFactor", "InsiderFactor", "SessionFactor", "InstrumentRiskFactor", "PortfolioFactor", "MultiFactorResult", "MultiFactorAnalysisServiceV081"]
