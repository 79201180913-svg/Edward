from __future__ import annotations

import subprocess
import tkinter as tk
from decimal import Decimal
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.config.settings import Environment, Settings
from edward.main import _start_adapter, _wait_for_adapter
from edward.security.token_store import TokenStore
from edward.services.account_context import AccountContext
from edward.services.account_service import AccountService
from edward.services.balance_service import BalanceService
from edward.services.currency_service import CurrencyService
from edward.services.instrument_catalog_service import InstrumentCatalogService
from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.services.trading_data_provider import AdapterTradingDataProvider
from edward.history.trading_history import TradeRecord, TradingHistoryRepository
from edward.ui.instrument_catalog import INSTRUMENT_KINDS
from edward.ui.token_dialog import request_and_save_token
from edward.validation.trading_validator import TradingValidator


class EdwardApp(tk.Tk):
    def __init__(self, client, adapter_process, environment):
        super().__init__(); self.client=client; self.adapter_process=adapter_process; self.environment=environment; self.context=AccountContext(); self.accounts=[]; self.account_by_label={}; self.current_page='overview'; self.selected_instrument=None; self.tracked_orders={}; self.display_currency=tk.StringVar(value='RUB'); self.history=TradingHistoryRepository(); self.title('Edward — Торговая платформа'); self.geometry('1400x850'); self.minsize(1180,720); self.protocol('WM_DELETE_WINDOW',self._close); self._style(); self._shell(); self._refresh_accounts(); self.show_page('overview'); self.after(5000,self._tick)

    @staticmethod
    def _field(v,n,d=''): return v.get(n,d) if isinstance(v,dict) else getattr(v,n,d)
    @classmethod
    def _items(cls,r,*names):
        if isinstance(r,list): return r
        for n in names:
            v=cls._field(r,n,None)
            if v is not None: return list(v)
        return []
    @staticmethod
    def _decimal(v):
        if v is None: return Decimal('0')
        if isinstance(v,dict) and ('units' in v or 'nano' in v): return Decimal(str(v.get('units',0)))+Decimal(str(v.get('nano',0)))/Decimal('1000000000')
        try: return Decimal(str(v))
        except Exception: return Decimal('0')
    @classmethod
    def _money(cls,v,c=''): return f'{cls._decimal(v):,.2f}'.replace(',',' ')+(f' {c}' if c else '')

    def _style(self):
        s=ttk.Style(self)
        try:s.theme_use('vista')
        except tk.TclError:pass
        s.configure('Title.TLabel',font=('Segoe UI',20,'bold')); s.configure('Subtitle.TLabel',font=('Segoe UI',10)); s.configure('Card.TFrame',relief='solid',borderwidth=1); s.configure('CardTitle.TLabel',font=('Segoe UI',10)); s.configure('CardValue.TLabel',font=('Segoe UI',18,'bold')); s.configure('Nav.TButton',padding=(14,10),anchor='w'); s.configure('Treeview',rowheight=28)

    def _shell(self):
        h=ttk.Frame(self,padding=(20,14)); h.pack(fill='x'); ttk.Label(h,text='Edward',style='Title.TLabel').pack(side='left'); ttk.Label(h,text='Торговая платформа v0.1',style='Subtitle.TLabel').pack(side='left',padx=(12,0),pady=(9,0)); ttk.Label(h,text=self.environment.value.upper()).pack(side='right',padx=(10,0)); ttk.Button(h,text='⟳ Обновить',command=self.refresh_current).pack(side='right')
        b=ttk.Frame(self,padding=(20,0,20,12)); b.pack(fill='x'); ttk.Label(b,text='Активный счёт:').pack(side='left'); self.account_var=tk.StringVar(); self.account_combo=ttk.Combobox(b,textvariable=self.account_var,state='readonly',width=52); self.account_combo.pack(side='left',padx=10); self.account_combo.bind('<<ComboboxSelected>>',self._account_changed); ttk.Label(b,text='Валюта:').pack(side='left',padx=(18,4)); ttk.Radiobutton(b,text='RUB',variable=self.display_currency,value='RUB',command=self.refresh_current).pack(side='left'); ttk.Radiobutton(b,text='USD',variable=self.display_currency,value='USD',command=self.refresh_current).pack(side='left'); self.status_var=tk.StringVar(value='Готово'); ttk.Label(b,textvariable=self.status_var).pack(side='right')
        body=ttk.Frame(self); body.pack(fill='both',expand=True); self.nav=ttk.Frame(body,padding=(20,10,10,20),width=210); self.nav.pack(side='left',fill='y'); self.content=ttk.Frame(body,padding=(10,10,20,20)); self.content.pack(side='left',fill='both',expand=True)
        for key,label in [('overview','Обзор'),('accounts','Счета'),('portfolio','Портфель'),('instruments','Инструменты'),('orders','Заявки'),('order','Новая заявка'),('history','История')]: ttk.Button(self.nav,text=label,style='Nav.TButton',command=lambda k=key:self.show_page(k)).pack(fill='x',pady=2)
        ttk.Separator(self.nav).pack(fill='x',pady=14)
        if self.environment is Environment.SANDBOX: ttk.Button(self.nav,text='Создать sandbox-счёт',command=self._create_account).pack(fill='x',pady=2); ttk.Button(self.nav,text='Закрыть активный счёт',command=self._close_account).pack(fill='x',pady=2)

    def _clear(self):
        for c in self.content.winfo_children(): c.destroy()
    def show_page(self,page): self.current_page=page; self._clear();
    def _show_page(self,page):
        try:getattr(self,f'_page_{page}')()
        except Exception as exc:self._show_error(exc,page)
    def refresh_current(self): self._refresh_accounts(); self._clear(); self._show_page(self.current_page)
    def show_page(self,page): self.current_page=page; self._clear(); self._show_page(page)

    def _tick(self):
        try:
            self._refresh_accounts(); self._poll_orders()
            if self.current_page in {'overview','portfolio','orders'}: self._clear(); self._show_page(self.current_page)
        except Exception: pass
        if self.winfo_exists(): self.after(5000,self._tick)

    def _refresh_accounts(self):
        self.accounts=[a for a in self._items(self.client.get_accounts(),'accounts') if AccountService.is_open(a)]; self.account_by_label={}; labels=[]
        for a in self.accounts:
            aid=str(self._field(a,'id','')); label=f"{self._field(a,'name','') or 'Счёт'} | {aid} | {self._field(a,'status','')}"; labels.append(label); self.account_by_label[label]=a
        self.account_combo['values']=labels; active=next((a for a in self.accounts if str(self._field(a,'id',''))==self.context.active_account_id),None)
        if active is None and self.accounts: active=self.accounts[0]; self.context.set_active(active)
        self.account_var.set(next((k for k,v in self.account_by_label.items() if str(self._field(v,'id',''))==self.context.active_account_id),'')); self.status_var.set(f'Открытых счетов: {len(self.accounts)}')
    def _account_changed(self,_=None):
        a=self.account_by_label.get(self.account_var.get())
        if a:self.context.set_active(a); self.show_page(self.current_page)
    def _require_account(self):
        try:return self.context.require_account_id()
        except RuntimeError: messagebox.showwarning('Edward','Сначала выберите открытый торговый счёт.'); return None
    def _card(self,p,t,v,c):
        f=ttk.Frame(p,style='Card.TFrame',padding=16); f.grid(row=0,column=c,sticky='nsew',padx=6); ttk.Label(f,text=t,style='CardTitle.TLabel').pack(anchor='w'); ttk.Label(f,text=v,style='CardValue.TLabel').pack(anchor='w',pady=(8,0))

    def _page_overview(self):
        ttk.Label(self.content,text='Обзор счёта',style='Title.TLabel').pack(anchor='w',pady=(0,16)); aid=self._require_account()
        if not aid:return
        pos=self.client.get_positions(aid); portfolio=self.client.get_portfolio(aid); summary=BalanceService.build_summary(pos,portfolio); currency=summary.currency or 'RUB'; values=[summary.available,summary.blocked,summary.securities,summary.portfolio_value]
        if currency != self.display_currency.get():
            try: values=[CurrencyService(self.client).convert(v,currency,self.display_currency.get()) for v in values]; currency=self.display_currency.get()
            except Exception:self.status_var.set('Курс USD/RUB недоступен; показана исходная валюта.')
        cards=ttk.Frame(self.content); cards.pack(fill='x')
        for i in range(4):cards.columnconfigure(i,weight=1)
        for i,(t,v) in enumerate(zip(('Доступно','Заблокировано','Ценные бумаги','Стоимость портфеля'),values)):self._card(cards,t,self._money(v,currency),i)
        active=self.context.active_account; d=ttk.Frame(self.content); d.pack(fill='x',pady=(28,0))
        for r,(k,v) in enumerate((('ID счёта',aid),('Название',active.name if active else ''),('Статус',active.status if active else ''))):ttk.Label(d,text=k,width=18).grid(row=r,column=0,sticky='w',pady=4); ttk.Label(d,text=v).grid(row=r,column=1,sticky='w',pady=4)

    def _page_accounts(self):
        ttk.Label(self.content,text='Торговые счета',style='Title.TLabel').pack(anchor='w',pady=(0,16)); tree=self._tree(self.content,('ID','Название','Статус','Активен'),(380,220,150,90));
        for a in self.accounts: tree.insert('', 'end', values=(self._field(a,'id',''),self._field(a,'name',''),self._field(a,'status',''),'Да' if str(self._field(a,'id',''))==self.context.active_account_id else ''))
        ttk.Label(self.content,text='Активный счёт выбирается в верхней панели.').pack(anchor='w',pady=10)

    def _page_portfolio(self):
        ttk.Label(self.content,text='Портфель',style='Title.TLabel').pack(anchor='w',pady=(0,16)); aid=self._require_account()
        if not aid:return
        tree=self._tree(self.content,('Тикер','UID','Количество','Заблокировано','Цена','Доходность'),(110,350,110,140,120,130))
        for p in self._items(self.client.get_positions(aid),'securities'): tree.insert('', 'end', values=(self._field(p,'ticker',''),self._field(p,'instrument_uid',self._field(p,'figi','')),self._field(p,'balance',''),self._field(p,'blocked_lots',self._field(p,'blocked','')),self._field(p,'current_price',''),self._field(p,'expected_yield',self._field(p,'expected_yield_fifo',''))))

    def _page_instruments(self):
        ttk.Label(self.content,text='Каталог инструментов',style='Title.TLabel').pack(anchor='w',pady=(0,12)); c=ttk.Frame(self.content); c.pack(fill='x',pady=(0,10)); self.kind_var=tk.StringVar(value=INSTRUMENT_KINDS[0][1]); ttk.Combobox(c,textvariable=self.kind_var,state='readonly',values=[x[1] for x in INSTRUMENT_KINDS],width=18).pack(side='left'); self.filter_var=tk.StringVar(); ttk.Entry(c,textvariable=self.filter_var,width=35).pack(side='left',padx=8); ttk.Button(c,text='Загрузить',command=self._load_instruments).pack(side='left'); ttk.Button(c,text='Обновить цены',command=self._load_instruments).pack(side='left',padx=8)
        self.instrument_tree=self._tree(self.content,('Тикер','Название','Валюта','Цена','Шаг','Покупка','Продажа','Торги','UID'),(100,250,80,120,100,90,90,100,360)); self.instrument_tree.bind('<Double-1>',self._instrument_selected); self._load_instruments()
    def _load_instruments(self):
        kind=next(k for k,v in INSTRUMENT_KINDS if v==self.kind_var.get()); svc=InstrumentCatalogService(self.client); q=self.filter_var.get().strip(); items=svc.search(q,kind,True) if q else svc.list(kind,True)
        for x in self.instrument_tree.get_children():self.instrument_tree.delete(x)
        for i in items:self.instrument_tree.insert('', 'end', values=(self._field(i,'ticker',''),self._field(i,'name',''),self._field(i,'currency',''),self._field(i,'last_price',''),self._field(i,'min_price_increment',''),'Да' if self._field(i,'buy_available',False) else 'Нет','Да' if self._field(i,'sell_available',False) else 'Нет','Да' if self._field(i,'api_trade_available',False) else 'Нет',self._field(i,'uid',self._field(i,'instrument_uid',''))))
        self.status_var.set(f'Инструментов: {len(items)}')
    def _instrument_selected(self,_=None):
        sel=self.instrument_tree.selection()
        if not sel:return
        v=self.instrument_tree.item(sel[0]).get('values',[])
        if len(v)<9:return
        self.selected_instrument={'ticker':v[0],'name':v[1],'currency':v[2],'last_price':v[3],'min_price_increment':v[4],'buy_available':v[5]=='Да','sell_available':v[6]=='Да','api_trade_available':v[7]=='Да','uid':str(v[8]),'instrument_uid':str(v[8]),'instrument_kind':next(k for k,l in INSTRUMENT_KINDS if l==self.kind_var.get())}; self.show_page('order')

    def _page_orders(self):
        ttk.Label(self.content,text='Активные заявки',style='Title.TLabel').pack(anchor='w',pady=(0,12)); aid=self._require_account()
        if not aid:return
        orders=self._items(self.client.get_orders(aid),'orders'); tree=self._tree(self.content,('ID','Тикер','Операция','Запрошено','Исполнено','Статус','Цена'),(330,110,100,100,100,160,120))
        for o in orders:tree.insert('', 'end', values=(self._field(o,'order_id',''),self._field(o,'ticker',''),self._field(o,'direction',''),self._field(o,'lots_requested',self._field(o,'quantity','')),self._field(o,'lots_executed',''),self._field(o,'execution_report_status',self._field(o,'status','')),self._field(o,'initial_security_price',self._field(o,'price',''))))
        f=ttk.Frame(self.content); f.pack(fill='x',pady=10); ttk.Button(f,text='Отменить',command=lambda:self._cancel(tree)).pack(side='left'); ttk.Button(f,text='Изменить',command=lambda:self._replace(tree)).pack(side='left',padx=8)
    def _cancel(self,tree):
        s=tree.selection()
        if not s:return
        oid=str(tree.item(s[0])['values'][0]); aid=self._require_account()
        if aid and messagebox.askyesno('Подтверждение',f'Отменить заявку {oid}?'): OrderService(self.client).cancel_order(aid,oid); self.refresh_current()
    def _replace(self,tree):
        s=tree.selection(); aid=self._require_account()
        if not s or not aid:return
        vals=tree.item(s[0])['values']; oid=str(vals[0]); qty=simpledialog.askinteger('Изменение заявки','Новое количество лотов:',initialvalue=int(vals[3]),parent=self,minvalue=1)
        if qty is None:return
        price=simpledialog.askstring('Изменение заявки','Новая цена (Enter — оставить текущую):',initialvalue=str(vals[6]),parent=self)
        try:
            req=OrderRequest(account_id=aid,instrument_uid=str(vals[1]),side=OrderSide(str(vals[2]).upper()),order_type=OrderType.LIMIT,quantity=qty,price=Decimal(price) if price else None)
            OrderService(self.client).replace_order(aid,oid,req); self.refresh_current()
        except Exception as exc:self._show_error(exc,'изменение заявки')

    def _page_order(self):
        ttk.Label(self.content,text='Новая торговая заявка',style='Title.TLabel').pack(anchor='w',pady=(0,16)); aid=self._require_account()
        if not aid:return
        ins=self.selected_instrument or {}; f=ttk.Frame(self.content); f.pack(fill='x'); vars={}
        fields=[('ticker','Инструмент',ins.get('ticker','')),('side','Операция','Покупка'),('order_type','Тип заявки','Лимитная'),('quantity','Количество лотов','1'),('price','Цена',str(ins.get('last_price','')))]
        for r,(k,l,d) in enumerate(fields):
            ttk.Label(f,text=l,width=22).grid(row=r,column=0,sticky='w',pady=5); vars[k]=tk.StringVar(value=d)
            if k=='side':w=ttk.Combobox(f,textvariable=vars[k],state='readonly',values=['Покупка','Продажа'],width=37)
            elif k=='order_type':w=ttk.Combobox(f,textvariable=vars[k],state='readonly',values=['Рыночная','Лимитная'],width=37)
            elif k=='ticker':w=ttk.Entry(f,textvariable=vars[k],state='readonly',width=40)
            else:w=ttk.Entry(f,textvariable=vars[k],width=40)
            w.grid(row=r,column=1,sticky='w')
        ttk.Label(self.content,text=f"Текущая цена: {ins.get('last_price','недоступна')} | Шаг цены: {ins.get('min_price_increment','неизвестен')}").pack(anchor='w',pady=12); ttk.Button(self.content,text='Проверить и подтвердить',command=lambda:self._submit(vars)).pack(anchor='w')
    def _submit(self,v):
        aid=self._require_account(); ins=self.selected_instrument
        if not aid or not ins:return
        try:
            qty=int(v['quantity'].get()); side=OrderSide.BUY if v['side'].get()=='Покупка' else OrderSide.SELL; typ=OrderType.MARKET if v['order_type'].get()=='Рыночная' else OrderType.LIMIT; price=Decimal(v['price'].get()) if typ==OrderType.LIMIT else None; req=OrderRequest(account_id=aid,instrument_uid=str(ins['instrument_uid']),side=side,order_type=typ,quantity=qty,price=price,instrument_kind=str(ins.get('instrument_kind','SHARE'))); ctx=TradingValidator(AdapterTradingDataProvider(self.client)).validate(req)
            total=ctx.estimated_total or Decimal('0'); commission=ctx.estimated_commission or Decimal('0')
        except Exception as exc:self._show_error(exc,'проверка заявки'); return
        if not messagebox.askyesno('Подтверждение заявки',f"{ins.get('ticker','')}\n{side.value}\nКоличество: {qty}\nЦена: {price or ctx.market_price}\nКомиссия: {self._money(commission)}\nИтого: {self._money(total+commission)}\n\nОтправить?"):return
        try:
            result=OrderService(self.client).create_order(req); oid=str(self._field(result,'order_id','')); self.tracked_orders[oid]={'account_id':aid,'instrument_uid':req.instrument_uid,'ticker':ins.get('ticker',''),'name':ins.get('name',''),'operation':side.value,'quantity':qty,'order_type':typ.value,'currency':ins.get('currency','')}; self.show_page('orders')
        except Exception as exc:self._show_error(exc,'создание заявки')

    def _poll_orders(self):
        for oid,meta in list(self.tracked_orders.items()):
            try:
                state=self.client.get_order_state(meta['account_id'],oid); status=str(self._field(state,'execution_report_status',self._field(state,'status',''))).upper()
                if 'FILL' in status and 'PART' not in status:
                    self.history.save_completed(TradeRecord(account_id=meta['account_id'],order_id=oid,instrument_uid=meta['instrument_uid'],operation=meta['operation'],quantity=int(self._field(state,'lots_executed',meta['quantity']) or 0),order_type=meta['order_type'],execution_price=self._decimal(self._field(state,'executed_order_price',None)),amount=self._decimal(self._field(state,'total_order_amount',None)),commission=self._decimal(self._field(state,'executed_commission',None)),currency=str(self._field(state,'currency',meta['currency'])),status='FILLED',figi=str(self._field(state,'figi','')),ticker=meta['ticker'],name=meta['name'])); self.tracked_orders.pop(oid,None)
            except Exception: pass

    def _page_history(self):
        ttk.Label(self.content,text='История исполненных операций',style='Title.TLabel').pack(anchor='w',pady=(0,12)); tree=self._tree(self.content,('Дата','Время','Счёт','Заявка','Тикер','Операция','Количество','Цена','Сумма','Комиссия','Валюта','Статус'),(90,80,300,300,100,100,100,110,120,110,80,100))
        for row in self.history.read_all():tree.insert('', 'end', values=tuple(row.get(k,'') for k in ('date','time','account_id','order_id','ticker','operation','quantity','execution_price','amount','commission','currency','status')))

    def _create_account(self):
        name=simpledialog.askstring('Sandbox','Название счёта (необязательно):',parent=self)
        try:
            r=self.client.create_sandbox_account(name); self._refresh_accounts(); aid=str(self._field(r,'account_id',self._field(r,'id',''))); a=next((x for x in self.accounts if str(self._field(x,'id',''))==aid),None); self.context.set_active(a) if a else self.context.set_active_id(aid); self.show_page('overview')
        except Exception as exc:self._show_error(exc,'создание счёта')
    def _close_account(self):
        aid=self._require_account()
        if aid and messagebox.askyesno('Подтверждение',f'Закрыть sandbox-счёт {aid}?'):
            try:self.client.close_sandbox_account(aid); self.context.clear(); self._refresh_accounts(); self.show_page('overview')
            except Exception as exc:self._show_error(exc,'закрытие счёта')

    def _tree(self,parent,columns,widths):
        frame=ttk.Frame(parent); frame.pack(fill='both',expand=True); tree=ttk.Treeview(frame,columns=columns,show='headings')
        for c,w in zip(columns,widths):tree.heading(c,text=c); tree.column(c,width=w,anchor='w')
        y=ttk.Scrollbar(frame,orient='vertical',command=tree.yview); x=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview); tree.configure(yscrollcommand=y.set,xscrollcommand=x.set); tree.grid(row=0,column=0,sticky='nsew'); y.grid(row=0,column=1,sticky='ns'); x.grid(row=1,column=0,sticky='ew'); frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1); return tree
    def _show_error(self,exc,context=''):
        detail=f'Edward Trading Platform v0.1\nКонтекст: {context}\nОшибка: {type(exc).__name__}: {exc}'
        d=tk.Toplevel(self); d.title('Ошибка Edward'); d.geometry('900x520'); t=tk.Text(d,wrap='word'); t.pack(fill='both',expand=True,padx=10,pady=10); t.insert('1.0',detail); t.configure(state='disabled'); b=ttk.Frame(d); b.pack(fill='x',padx=10,pady=10); ttk.Button(b,text='Скопировать',command=lambda:(self.clipboard_clear(),self.clipboard_append(detail),self.update())).pack(side='left'); ttk.Button(b,text='Закрыть',command=d.destroy).pack(side='right')
    def _close(self):
        try:self.adapter_process.terminate()
        finally:self.destroy()


def main():
    store=TokenStore(); token=store.get() or request_and_save_token(store)
    if not token:return
    env=Environment.SANDBOX; process=_start_adapter(token,env); client=TInvestAdapterClient(); _wait_for_adapter(client,process); EdwardApp(client,process,env).mainloop()

if __name__=='__main__': main()
