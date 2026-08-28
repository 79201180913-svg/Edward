from __future__ import annotations
from collections.abc import Mapping
from dataclasses import replace
from logging import getLogger
from typing import Any
from edward.services.contract_analysis_data_service_v081 import ContractAnalysisDataServiceV081
from edward.services.contract_evidence_mapper_v081 import map_fundamentals, map_insider, map_order_book, map_risk_rates, map_news
logger = getLogger(__name__)
class RobustContractAnalysisDataServiceV081(ContractAnalysisDataServiceV081):
    """v0.8.1 collector with recursive contract-response discovery."""
    _DIRECT_FIELD_GROUPS = {"fundamentals": {"roe","roic","net_margin_mrq","revenue_ttm","free_cash_flow_ttm","pe_ratio_ttm","eps_change_five_years","net_debt_to_ebitda","one_year_annual_revenue_growth_rate","current_ratio_mrq"}, "risk_rates": {"long_risk_rate","short_risk_rate","dlong","dshort","dlong_client","dshort_client"}, "reports": {"report_date","period_year","period_num","period_type"}, "insiders": {"quantity","direction","investor_position","percentage"}, "news": {"id","title","source","priority","ts"}, "signals": {"signal_id","strategy_id","direction","initial_price"}, "dividends": {"yield_value","dividend_yield","regularity","declared_date"}, "microstructure": {"bids","asks"}}
    @classmethod
    def _walk(cls, value: Any, *, max_depth: int = 12):
        seen=set(); stack=[(value,0)]
        while stack:
            current,depth=stack.pop()
            if current is None or depth>max_depth: continue
            if isinstance(current,(Mapping,list,tuple)):
                if id(current) in seen: continue
                seen.add(id(current))
            yield current
            if depth==max_depth: continue
            if isinstance(current,Mapping):
                for child in reversed(list(current.values())): stack.append((child,depth+1))
            elif isinstance(current,(list,tuple)):
                for child in reversed(current): stack.append((child,depth+1))
    @staticmethod
    def _normalize(name: str) -> str: return name.replace("_","").lower()
    @classmethod
    def _looks_like_direct_object(cls,mapping,group): return bool({cls._normalize(str(k)) for k in mapping}&{cls._normalize(k) for k in cls._DIRECT_FIELD_GROUPS[group]})
    @classmethod
    def _matching_value(cls,mapping,key_names):
        normalized={cls._normalize(str(k)):k for k in mapping}
        for name in key_names:
            if name in mapping: return mapping[name]
            compact=cls._normalize(name)
            if compact in normalized: return mapping[normalized[compact]]
        return None
    @classmethod
    def _groups_for_keys(cls,keys):
        aliases={"fundamentals":"fundamentals","statistics":"fundamentals","riskrates":"risk_rates","instrumentriskrates":"risk_rates","events":"reports","reports":"reports","insiderdeals":"insiders","insiders":"insiders","items":"news","news":"news","signals":"signals","dividends":"dividends","bids":"microstructure","asks":"microstructure"}
        groups=[]; normalized={cls._normalize(k) for k in keys}
        for name,group in aliases.items():
            if name in normalized and group not in groups: groups.append(group)
        return tuple(groups)
    @classmethod
    def _first(cls,payload,*keys):
        groups=cls._groups_for_keys(keys)
        for current in cls._walk(payload):
            if isinstance(current,Mapping) and any(cls._looks_like_direct_object(current,g) for g in groups): return current
        for current in cls._walk(payload):
            if not isinstance(current,Mapping): continue
            value=cls._matching_value(current,keys)
            if value is None: continue
            if isinstance(value,list):
                for item in value:
                    if isinstance(item,Mapping) and any(cls._looks_like_direct_object(item,g) for g in groups): return item
                if value: return value[0]
            elif isinstance(value,Mapping):
                for nested in cls._walk(value,max_depth=8):
                    if isinstance(nested,Mapping) and any(cls._looks_like_direct_object(nested,g) for g in groups): return nested
                if not groups: return value
            else: return value
        return None
    @classmethod
    def _extract_list(cls,value,max_depth=8):
        if isinstance(value,list): return value
        if not isinstance(value,Mapping): return []
        stack=[(value,0)]; seen=set()
        while stack:
            current,depth=stack.pop()
            if depth>max_depth or current is None: continue
            if isinstance(current,(Mapping,list,tuple)):
                if id(current) in seen: continue
                seen.add(id(current))
            if isinstance(current,list): return current
            if isinstance(current,Mapping):
                for child in reversed(list(current.values())): stack.append((child,depth+1))
        return []
    @classmethod
    def _many(cls,payload,*keys):
        if isinstance(payload,list): return payload
        groups=cls._groups_for_keys(keys); targets={cls._normalize(k) for k in keys}
        for current in cls._walk(payload):
            if not isinstance(current,Mapping): continue
            for raw_key,value in current.items():
                if cls._normalize(str(raw_key)) not in targets: continue
                extracted=cls._extract_list(value)
                if extracted: return extracted
                if isinstance(value,Mapping) and groups and any(cls._looks_like_direct_object(value,g) for g in groups): return [value]
        if groups:
            for current in cls._walk(payload):
                if isinstance(current,(list,tuple)) and current:
                    mappings=[x for x in current if isinstance(x,Mapping)]
                    if mappings and any(cls._looks_like_direct_object(x,g) for x in mappings for g in groups): return list(current)
            if isinstance(payload,Mapping) and any(cls._looks_like_direct_object(payload,g) for g in groups): return [payload]
        return []
    @classmethod
    def _log_risk_item_diagnostics(cls,instrument_uid,raw_risk,risk_items):
        logger.info("[V081 RISK ITEM DIAG] instrument_uid=%s root_type=%s item_count=%d",instrument_uid,type(raw_risk).__name__,len(risk_items))
    def collect(self,instrument_uid: str):
        result=super().collect(instrument_uid); failed=set(result.failed_sources); unavailable=set(result.unavailable_sources); fetched=set(result.fetched_sources)
        if "fundamentals" in fetched and ("fundamentals_mapping" in failed or "fundamentals" in unavailable):
            mapped=map_fundamentals(self._first(self.client.get_asset_fundamentals(instrument_uid),"fundamentals","statistics","asset_fundamentals"))
            if mapped is not None: failed.discard("fundamentals_mapping"); unavailable.discard("fundamentals"); result=replace(result,fundamentals=mapped)
        if "insiders" in fetched and ("insiders_mapping" in failed or "insiders" in unavailable):
            items=self._many(self.client.get_insider_deals(instrument_uid,100),"insider_deals","insiders")
            if items: failed.discard("insiders_mapping"); unavailable.discard("insiders"); result=replace(result,insider_transactions=tuple(map_insider(x) for x in items))
        if "reports" in fetched and ("reports_mapping" in failed or "reports" in unavailable):
            items=self._many(self.client.get_asset_reports(instrument_uid,None,None),"events","reports")
            if items: failed.discard("reports_mapping"); unavailable.discard("reports"); result=replace(result,reports=tuple(self._map_report(x) for x in items))
        if "news" in fetched and ("news_mapping" in failed or "news" in unavailable or not result.news):
            raw=self.client.get_news(1000)
            items=self._many(raw,"items","news")
            if not items and isinstance(raw,Mapping) and self._looks_like_direct_object(raw,"news"):
                items=[raw]
            if items:
                failed.discard("news_mapping"); unavailable.discard("news"); result=replace(result,news=tuple(map_news(x) for x in items))
        if "risk_rates" in fetched and ("risk_rates_mapping" in failed or "risk_rates_mapping" in unavailable or "risk_rates" in unavailable):
            raw=self.client.get_risk_rates([instrument_uid]); items=self._many(raw,"risk_rates","instrument_risk_rates","items"); self._log_risk_item_diagnostics(instrument_uid,raw,items)
            mapped=map_risk_rates({"risk_rates":items}) if items else map_risk_rates(raw)
            if mapped is not None: failed.discard("risk_rates_mapping"); unavailable.discard("risk_rates_mapping"); unavailable.discard("risk_rates"); result=replace(result,risk_data=mapped)
        if "order_book" in fetched and result.order_book is None:
            raw=self.client.get_order_book(instrument_uid,10); bids=self._many(raw,"bids"); asks=self._many(raw,"asks"); mapped=map_order_book({"bids":bids,"asks":asks}) if bids or asks else None
            if mapped is not None: result=replace(result,order_book=mapped)
        return replace(result,failed_sources=tuple(sorted(failed)),unavailable_sources=tuple(sorted(unavailable)))
__all__=["RobustContractAnalysisDataServiceV081"]