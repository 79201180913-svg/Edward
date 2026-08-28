from __future__ import annotations
from datetime import datetime,timedelta,timezone
from typing import Any
import tinvest_adapter as adapter

def _ts(v):
    if v is None:return None
    if isinstance(v,str):return v
    v=v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return v.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

def _structure(v,depth=0):
    if depth>=2:return type(v).__name__
    if isinstance(v,dict):
        r={'type':'dict','keys':tuple(sorted(map(str,v)))}
        for k in ('fundamentals','statistics','asset_fundamentals','response','data','result','payload'):
            if k in v:
                x=v[k]; r[k]={'type':'list','count':len(x),'first':_structure(x[0],depth+1) if x else None} if isinstance(x,list) else _structure(x,depth+1)
        return r
    if isinstance(v,(list,tuple)):return {'type':type(v).__name__,'count':len(v),'first':_structure(v[0],depth+1) if v else None}
    return {'type':type(v).__name__}

def _resolve_asset_uid(self,instrument_id):
    uid=str(instrument_id or '')
    if not uid:raise ValueError('instrument_id is required')
    r=self._rest_request('InstrumentsService/GetInstrumentBy',{'idType':'INSTRUMENT_ID_TYPE_UID','id':uid})
    ins=r.get('instrument') if isinstance(r,dict) else None
    asset=ins.get('asset_uid') if isinstance(ins,dict) else None
    if not asset and isinstance(ins,dict):asset=ins.get('assetUid')
    adapter.logger.info('[FUNDAMENTALS ASSET UID] instrument_uid=%s resolved=%s available=%s',uid,asset,bool(asset))
    if not asset:raise ValueError(f'asset_uid is unavailable for instrument_uid={uid}')
    return str(asset)

def _get_asset_fundamentals(self,instrument_id):
    instrument_uid=str(instrument_id or '')
    asset_uid=_resolve_asset_uid(self,instrument_uid)
    adapter.logger.info('[FUNDAMENTALS API REQUEST] instrument_uid=%s asset_uid=%s',instrument_uid,asset_uid)
    result=self._rest_request('InstrumentsService/GetAssetFundamentals',{'assets':[asset_uid]})
    adapter.logger.info('[FUNDAMENTALS API RAW] response_type=%s structure=%s',type(result).__name__,_structure(result))
    if isinstance(result,dict):
        fs=result.get('fundamentals')
        if isinstance(fs,list):
            adapter.logger.info('[FUNDAMENTALS API COLLECTION] count=%s',len(fs))
            if fs and isinstance(fs[0],dict):
                keys=tuple(sorted(map(str,fs[0]))); populated=tuple(sorted(str(k) for k,v in fs[0].items() if v is not None))
                adapter.logger.info('[FUNDAMENTALS API FIRST] keys=%s populated_fields=%s',keys,populated)
    return result

def _get_asset_reports(self,instrument_id,from_dt=None,to_dt=None):
    p={'instrumentId':str(instrument_id)}
    if from_dt is not None:p['from']=_ts(from_dt)
    if to_dt is not None:p['to']=_ts(to_dt)
    return self._rest_request('InstrumentsService/GetAssetReports',p)
def _get_dividends(self,instrument_id,from_dt=None,to_dt=None):
    p={'instrumentId':str(instrument_id)}
    if from_dt is not None:p['from']=_ts(from_dt)
    if to_dt is not None:p['to']=_ts(to_dt)
    return self._rest_request('InstrumentsService/GetDividends',p)
def _get_risk_rates(self,instrument_ids):return self._rest_request('InstrumentsService/GetRiskRates',{'instrumentId':[str(v) for v in instrument_ids]})
def _get_insider_deals(self,instrument_id,limit=100):return self._rest_request('InstrumentsService/GetInsiderDeals',{'instrumentId':str(instrument_id),'limit':max(1,min(int(limit),100))})
def _get_order_book(self,instrument_id,depth=10):return self._rest_request('MarketDataService/GetOrderBook',{'instrumentId':str(instrument_id),'depth':max(1,min(int(depth),50))})
def _get_last_trades(self,instrument_id,from_dt=None,to_dt=None):
    end=to_dt or datetime.now(timezone.utc); start=from_dt or end-timedelta(hours=1)
    return self._rest_request('MarketDataService/GetLastTrades',{'instrumentId':str(instrument_id),'from':_ts(start),'to':_ts(end),'tradeSource':'TRADE_SOURCE_ALL'})
def _get_market_values(self,instrument_ids,values):return self._rest_request('MarketDataService/GetMarketValues',{'instrumentId':[str(v) for v in instrument_ids],'values':[str(v) for v in values]})
def _get_signals(self,instrument_uid=None,strategy_id=None,from_dt=None,to_dt=None,active='SIGNAL_STATE_ALL'):
    p={'active':active}
    if instrument_uid:p['instrumentUid']=str(instrument_uid)
    if strategy_id:p['strategyId']=str(strategy_id)
    if from_dt is not None:p['from']=_ts(from_dt)
    if to_dt is not None:p['to']=_ts(to_dt)
    return self._rest_request('SignalService/GetSignals',p)
def _get_signal_strategies(self):return self._rest_request('SignalService/GetStrategies',{})
def _get_news(self,limit=1000,cursor=None):
    p={'limit':max(1,min(int(limit),1000))}
    if cursor is not None:p['cursor']=int(cursor)
    return self._rest_request('InstrumentsService/News',p)
def _get_trading_schedules(self,exchange=None,from_dt=None,to_dt=None):
    p={}
    if exchange:p['exchange']=str(exchange)
    if from_dt is not None:p['from']=_ts(from_dt)
    if to_dt is not None:p['to']=_ts(to_dt)
    return self._rest_request('InstrumentsService/TradingSchedules',p)
def _get_margin_attributes(self,account_id):return self._rest_request('UsersService/GetMarginAttributes',{'accountId':str(account_id)})
def _get_account_values(self,account_ids,values):return self._rest_request('UsersService/GetAccountValues',{'accounts':[str(v) for v in account_ids],'values':[str(v) for v in values]})
def _get_option(self,instrument_id,id_type='INSTRUMENT_ID_TYPE_UID',class_code=None):
    p={'idType':id_type,'id':str(instrument_id)}
    if class_code:p['classCode']=str(class_code)
    return self._rest_request('InstrumentsService/OptionBy',p)
def _get_future(self,instrument_id,id_type='INSTRUMENT_ID_TYPE_UID',class_code=None):
    p={'idType':id_type,'id':str(instrument_id)}
    if class_code:p['classCode']=str(class_code)
    return self._rest_request('InstrumentsService/FutureBy',p)
def _single(p,*keys):
    for k in keys:
        v=p.get(k)
        if isinstance(v,list) and v:return str(v[0])
        if v is not None and not isinstance(v,list):return str(v)
    raise KeyError(keys[0])
def _ids(p):
    v=p.get('instrument_id',p.get('instrument_ids',p.get('assets')))
    if isinstance(v,list):return [str(x) for x in v]
    return [str(v)] if v is not None else []

_ROUTES={'/analysis/fundamentals':lambda p:adapter.STATE.get_asset_fundamentals(_single(p,'assets','instrument_id')),'/analysis/reports':lambda p:adapter.STATE.get_asset_reports(p['instrument_id'],p.get('from'),p.get('to')),'/analysis/dividends':lambda p:adapter.STATE.get_dividends(p['instrument_id'],p.get('from'),p.get('to')),'/analysis/risk-rates':lambda p:adapter.STATE.get_risk_rates(_ids(p)),'/analysis/insider-deals':lambda p:adapter.STATE.get_insider_deals(p['instrument_id'],p.get('limit',100)),'/analysis/order-book':lambda p:adapter.STATE.get_order_book(p['instrument_id'],p.get('depth',10)),'/analysis/last-trades':lambda p:adapter.STATE.get_last_trades(p['instrument_id'],p.get('from'),p.get('to')),'/analysis/market-values':lambda p:adapter.STATE.get_market_values(_ids(p),p.get('values',[])),'/analysis/signals':lambda p:adapter.STATE.get_signals(p.get('instrument_uid'),p.get('strategy_id'),p.get('from'),p.get('to'),p.get('active','SIGNAL_STATE_ALL')),'/analysis/signal-strategies':lambda p:adapter.STATE.get_signal_strategies(),'/analysis/news':lambda p:adapter.STATE.get_news(p.get('limit',1000),p.get('cursor')),'/analysis/trading-schedules':lambda p:adapter.STATE.get_trading_schedules(p.get('exchange'),p.get('from'),p.get('to')),'/analysis/margin-attributes':lambda p:adapter.STATE.get_margin_attributes(p['account_id']),'/analysis/account-values':lambda p:adapter.STATE.get_account_values(p.get('account_ids',[]),p.get('values',[])),'/analysis/option':lambda p:adapter.STATE.get_option(p['instrument_id'],p.get('id_type','INSTRUMENT_ID_TYPE_UID'),p.get('class_code')),'/analysis/future':lambda p:adapter.STATE.get_future(p['instrument_id'],p.get('id_type','INSTRUMENT_ID_TYPE_UID'),p.get('class_code'))}

def install():
    if getattr(adapter,'_multifactor_v081_installed',False):return
    methods={'get_asset_fundamentals':_get_asset_fundamentals,'get_asset_reports':_get_asset_reports,'get_dividends':_get_dividends,'get_risk_rates':_get_risk_rates,'get_insider_deals':_get_insider_deals,'get_order_book':_get_order_book,'get_last_trades':_get_last_trades,'get_market_values':_get_market_values,'get_signals':_get_signals,'get_signal_strategies':_get_signal_strategies,'get_news':_get_news,'get_trading_schedules':_get_trading_schedules,'get_margin_attributes':_get_margin_attributes,'get_account_values':_get_account_values,'get_option':_get_option,'get_future':_get_future}
    for name,method in methods.items():setattr(adapter.AdapterState,name,method)
    original=adapter.Handler.do_POST
    def do_post(self):
        if self.path not in _ROUTES:return original(self)
        try:self._send(200,_ROUTES[self.path](self._read_json()))
        except Exception as exc:adapter.logger.exception('[MULTIFACTOR V0.8.1] %s',exc);self._send(500,{'error':str(exc),'type':type(exc).__name__})
    adapter.Handler.do_POST=do_post;adapter._multifactor_v081_installed=True

__all__=['install']
