from __future__ import annotations

from decimal import Decimal
from tkinter import messagebox
from typing import Any

from edward.history.trading_history import TradeRecord
from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.services.trading_data_provider import AdapterTradingDataProvider
from edward.validation.trading_validator import TradingValidator


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict) and ("units" in value or "nano" in value):
        return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def install_final_order_history_fix(EdwardApp: Any) -> None:
    def _submit(self: Any, v: Any) -> None:
        aid = self._require_account()
        ins = self.selected_instrument
        if not aid or not ins:
            return

        try:
            qty = int(v['quantity'].get())
            side = OrderSide.BUY if v['side'].get() == 'Покупка' else OrderSide.SELL
            typ = OrderType.MARKET if v['order_type'].get() == 'Рыночная' else OrderType.LIMIT
            price = Decimal(v['price'].get()) if typ == OrderType.LIMIT else None
            req = OrderRequest(
                account_id=aid,
                instrument_uid=str(ins['instrument_uid']),
                side=side,
                order_type=typ,
                quantity=qty,
                price=price,
                instrument_kind=str(ins.get('instrument_kind', 'SHARE')),
            )
            ctx = TradingValidator(AdapterTradingDataProvider(self.client)).validate(req)
            total = ctx.estimated_total or Decimal('0')
            commission = ctx.estimated_commission or Decimal('0')
            market_price = ctx.market_price
        except Exception as exc:
            print(f"[ORDER VALIDATION FAILED] account_id={aid}: {type(exc).__name__}: {exc}", flush=True)
            self._show_error(exc, 'проверка заявки')
            return

        shown_price = price if price is not None else market_price
        confirm_text = (
            f"{ins.get('ticker', '')}\n"
            f"{side.value}\n"
            f"Количество: {qty} лот(ов)\n"
            f"Цена 1 бумаги: {shown_price}\n"
            f"Итого: {self._money(total + commission)}\n"
            f"Комиссия: {self._money(commission)}\n\n"
            f"Отправить?"
        )
        if not messagebox.askyesno('Подтверждение заявки', confirm_text):
            print(f"[ORDER CANCELLED BY USER] account_id={aid} ticker={ins.get('ticker', '')}", flush=True)
            return

        try:
            print(
                f"[ORDER SEND] account_id={aid} ticker={ins.get('ticker', '')} uid={req.instrument_uid} "
                f"side={side.value} type={typ.value} quantity_lots={qty} price={price}",
                flush=True,
            )
            result = OrderService(self.client).create_order(req)
            oid = str(_field(result, 'order_id', ''))
            if not oid:
                raise RuntimeError(f"T-Invest did not return order_id: {result!r}")

            self.tracked_orders[oid] = {
                'account_id': aid,
                'instrument_uid': req.instrument_uid,
                'ticker': ins.get('ticker', ''),
                'name': ins.get('name', ''),
                'operation': side.value,
                'quantity': qty,
                'order_type': typ.value,
                'currency': ins.get('currency', 'RUB'),
            }

            self.history.upsert(TradeRecord(
                account_id=aid,
                order_id=oid,
                instrument_uid=req.instrument_uid,
                operation=side.value,
                quantity=qty,
                order_type=typ.value,
                execution_price=None,
                amount=total + commission,
                commission=commission,
                currency=str(ins.get('currency', 'RUB')),
                status='IN_PROGRESS',
                ticker=ins.get('ticker', ''),
                name=ins.get('name', ''),
            ))
            print(f"[ORDER SUCCESS] account_id={aid} order_id={oid} ticker={ins.get('ticker', '')}", flush=True)
            self.show_page('orders')
        except Exception as exc:
            print(f"[ORDER FAILED] account_id={aid} ticker={ins.get('ticker', '')}: {type(exc).__name__}: {exc}", flush=True)
            self._show_error(exc, 'создание заявки')

    def _poll_orders(self: Any) -> None:
        for oid, meta in list(self.tracked_orders.items()):
            try:
                state = self.client.get_order_state(meta['account_id'], oid)
                raw_status = _field(state, 'execution_report_status', _field(state, 'status', ''))
                status = str(raw_status).upper()
                print(f"[ORDER STATUS] account_id={meta['account_id']} order_id={oid} ticker={meta['ticker']} status={status}", flush=True)

                executed_lots = int(_decimal(_field(state, 'lots_executed', _field(state, 'quantity_executed', 0))))
                execution_price = _decimal(_field(state, 'executed_order_price', None))
                amount = _decimal(_field(state, 'total_order_amount', None))
                commission = _decimal(_field(state, 'executed_commission', None))

                if 'FILL' in status and 'PART' not in status:
                    self.history.upsert(TradeRecord(
                        account_id=meta['account_id'],
                        order_id=oid,
                        instrument_uid=meta['instrument_uid'],
                        operation=meta['operation'],
                        quantity=executed_lots or int(meta['quantity']),
                        order_type=meta['order_type'],
                        execution_price=execution_price,
                        amount=amount if amount != 0 else None,
                        commission=commission,
                        currency=str(_field(state, 'currency', meta.get('currency', 'RUB'))),
                        status='FILLED',
                        figi=str(_field(state, 'figi', '')),
                        ticker=meta['ticker'],
                        name=meta['name'],
                    ))
                    self.tracked_orders.pop(oid, None)
                    print(f"[ORDER FILLED] account_id={meta['account_id']} order_id={oid} ticker={meta['ticker']} lots={executed_lots or meta['quantity']}", flush=True)
                    if self.current_page in {'overview', 'portfolio', 'history'}:
                        self.refresh_current()
                    continue

                if any(token in status for token in ('REJECT', 'CANCEL', 'FAIL', 'ERROR')):
                    self.history.upsert(TradeRecord(
                        account_id=meta['account_id'],
                        order_id=oid,
                        instrument_uid=meta['instrument_uid'],
                        operation=meta['operation'],
                        quantity=int(meta['quantity']),
                        order_type=meta['order_type'],
                        execution_price=None,
                        amount=None,
                        commission=Decimal('0'),
                        currency=str(meta.get('currency', 'RUB')),
                        status='ERROR',
                        ticker=meta['ticker'],
                        name=meta['name'],
                    ))
                    self.tracked_orders.pop(oid, None)
                    print(f"[ORDER FAILED] account_id={meta['account_id']} order_id={oid} ticker={meta['ticker']} status={status}", flush=True)
                    self.refresh_current()
            except Exception as exc:
                print(f"[POLL ERROR] account_id={meta.get('account_id')} order_id={oid}: {type(exc).__name__}: {exc}", flush=True)

    EdwardApp._submit = _submit
    EdwardApp._poll_orders = _poll_orders
