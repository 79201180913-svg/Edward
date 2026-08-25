from __future__ import annotations

from typing import Any, Callable

from edward.config.application_settings import ApplicationSettingsStore
from edward.services.cached_analysis_service import CachedAnalysisService
from edward.services.opportunity_search_service import (
    MARKET_SCOPE,
    ProgressCallback,
    OpportunitySearchResult,
    OpportunitySearchService,
)
from edward.storage.sqlite_store import SQLiteStore

ResultCallback = Callable[[OpportunitySearchResult, int, int], None]


class LiveOpportunitySearchService(OpportunitySearchService):
    """Opportunity search that streams results and reuses Walk Forward cache."""

    def __init__(self, client: Any, *, force_recompute: bool = False):
        settings = ApplicationSettingsStore().load()
        store = SQLiteStore(settings.storage_path)
        super().__init__(client, analysis_service=CachedAnalysisService(store, force_recompute=force_recompute))

    @property
    def cache_info(self) -> dict[str, int]:
        analysis = self.analysis
        return analysis.cache_info() if isinstance(analysis, CachedAnalysisService) else {"hits": 0, "misses": 0, "total": 0}

    def scan(
        self,
        *,
        profile: str = "medium_term",
        instrument_kind: str = "SHARE",
        scope: str = MARKET_SCOPE,
        progress_callback: ProgressCallback | None = None,
        result_callback: ResultCallback | None = None,
        force_recompute: bool = False,
    ) -> list[OpportunitySearchResult]:
        if force_recompute and isinstance(self.analysis, CachedAnalysisService):
            self.analysis.force_recompute = True
        scope = str(scope or MARKET_SCOPE).upper()
        if scope not in {"MARKET", "PORTFOLIO"}:
            raise ValueError(f"Unsupported opportunity scope: {scope}")

        self._notify(progress_callback, "Загрузка списка инструментов", 2.0, 0, 0)
        account_id = self._active_account()
        positions = self.client.get_positions(account_id) if account_id else None
        portfolio = self.client.get_portfolio(account_id) if account_id else None
        instruments = self._build_universe(scope=scope, instrument_kind=instrument_kind, positions=positions)
        total = len(instruments)
        scope_title = "торговых инструментов" if scope == "MARKET" else "позиций портфеля"
        self._notify(progress_callback, f"Вселенная анализа: {total} {scope_title}", 8.0, 0, total)
        self._notify(progress_callback, "Portfolio Context загружается", 11.0, 0, total)
        self._notify(progress_callback, "Portfolio Context загружен", 14.0, 0, total)

        results: list[OpportunitySearchResult] = []
        valid_index = 0
        for instrument in instruments:
            uid = str(self._field(instrument, "uid", self._field(instrument, "instrument_uid", "")))
            if not uid:
                continue
            valid_index += 1
            progress_base = 15.0 + ((valid_index - 1) / max(1, total)) * 80.0
            progress_span = 80.0 / max(1, total)
            ticker = str(self._field(instrument, "ticker", ""))
            self._notify(progress_callback, f"Market Data: {ticker}", progress_base, valid_index, total)
            result = self._evaluate_instrument(
                instrument=instrument,
                profile=profile,
                positions=positions,
                portfolio=portfolio,
                progress_callback=progress_callback,
                progress_base=progress_base,
                progress_span=progress_span,
                current=valid_index,
                total=total,
            )
            results.append(result)
            if result_callback is not None:
                try:
                    result_callback(result, valid_index, total)
                except Exception:
                    pass
            self._notify(progress_callback, f"Обработано: {ticker}", progress_base + progress_span, valid_index, total)

        self._notify(progress_callback, "Ранжирование возможностей", 97.0, valid_index, total)
        results = sorted(
            results,
            key=lambda item: (
                item.decision not in {"BUY", "WAIT", "HOLD", "ADD", "REDUCE", "SELL"},
                item.decision not in {"BUY", "ADD", "REDUCE", "SELL", "HOLD"},
                -item.opportunity_score,
            ),
        )
        self._notify(progress_callback, "Сканирование завершено", 100.0, valid_index, total)
        return results

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)
