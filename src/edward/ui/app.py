from __future__ import annotations

import subprocess
from decimal import Decimal
from typing import Any
import tkinter as tk
from tkinter import messagebox, ttk

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.config.settings import Environment, Settings
from edward.main import _start_adapter, _wait_for_adapter
from edward.security.token_store import TokenStore
from edward.services.account_context import AccountContext
from edward.services.account_service import AccountService
from edward.services.balance_service import BalanceService
from edward.services.instrument_catalog_service import InstrumentCatalogService
from edward.services.order_service import OrderRequest, OrderService, OrderSide, OrderType
from edward.services.trading_data_provider import AdapterTradingDataProvider
from edward.ui.instrument_catalog import INSTRUMENT_KINDS
from edward.ui.token_dialog import request_and_save_token
from edward.validation.trading_validator import TradingValidator


class EdwardApp(tk.Tk):
    """Desktop presentation layer for Edward.

    The UI talks to application services/client abstractions only. T-Invest SDK
    details remain inside the existing Python 3.12 adapter process.
    """

    def __init__(self, client: TInvestAdapterClient, adapter_process: subprocess.Popen[bytes], environment: Environment) -> None:
        super().__init__()
        self.client = client
        self.adapter_process = adapter_process
        self.environment = environment
        self.context = AccountContext()
        self.accounts: list[Any] = []
        self.account_by_label: dict[str, Any] = {}
        self.current_page = "overview"
        self.selected_instrument: Any | None = None

        self.title("Edward Trading Platform v0.1")
        self.geometry("1280x780")
        self.minsize(1100, 680)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._configure_style()
        self._build_shell()
        self._refresh_accounts()
        self.show_page("overview")

    @staticmethod
    def _field(value: Any, name: str, default: Any = "") -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    @staticmethod
    def _items(response: Any, *names: str) -> list[Any]:
        if isinstance(response, list):
            return response
        for name in names:
            value = EdwardApp._field(response, name, None)
            if value is not None:
                return list(value)
        return []

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, dict) and ("units" in value or "nano" in value):
            return Decimal(str(value.get("units", 0))) + Decimal(str(value.get("nano", 0))) / Decimal("1000000000")
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    @staticmethod
    def _money(value: Any) -> str:
        return f"{EdwardApp._decimal(value):,.2f}".replace(",", " ")

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Card.TFrame", relief="solid", borderwidth=1)
        style.configure("CardTitle.TLabel", font=("Segoe UI", 10))
        style.configure("CardValue.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Nav.TButton", padding=(14, 10), anchor="w")

    def _build_shell(self) -> None:
        header = ttk.Frame(self, padding=(20, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Edward", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Trading Platform v0.1", style="Subtitle.TLabel").pack(side="left", padx=(12, 0), pady=(9, 0))
        self.environment_label = ttk.Label(header, text=self.environment.value.upper())
        self.environment_label.pack(side="right", padx=(10, 0))
        ttk.Button(header, text="⟳ Refresh", command=self.refresh_current).pack(side="right")

        account_bar = ttk.Frame(self, padding=(20, 0, 20, 12))
        account_bar.pack(fill="x")
        ttk.Label(account_bar, text="Active account:").pack(side="left")
        self.account_var = tk.StringVar()
        self.account_combo = ttk.Combobox(account_bar, textvariable=self.account_var, state="readonly", width=55)
        self.account_combo.pack(side="left", padx=10)
        self.account_combo.bind("<<ComboboxSelected>>", self._account_changed)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(account_bar, textvariable=self.status_var).pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.nav = ttk.Frame(body, padding=(20, 10, 10, 20), width=190)
        self.nav.pack(side="left", fill="y")
        self.content = ttk.Frame(body, padding=(10, 10, 20, 20))
        self.content.pack(side="left", fill="both", expand=True)

        pages = [("overview", "Overview"), ("accounts", "Accounts"), ("portfolio", "Portfolio"), ("instruments", "Instruments"), ("orders", "Active orders"), ("order", "Create order")]
        for key, label in pages:
            ttk.Button(self.nav, text=label, style="Nav.TButton", command=lambda k=key: self.show_page(k)).pack(fill="x", pady=2)
        ttk.Separator(self.nav).pack(fill="x", pady=14)
        if self.environment is Environment.SANDBOX:
            ttk.Button(self.nav, text="Create sandbox account", command=self._create_account).pack(fill="x", pady=2)
            ttk.Button(self.nav, text="Close active account", command=self._close_account).pack(fill="x", pady=2)

    def _clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def show_page(self, page: str) -> None:
        self.current_page = page
        self._clear_content()
        try:
            getattr(self, f"_page_{page}")()
        except Exception as exc:
            self._show_error(exc)

    def refresh_current(self) -> None:
        self._refresh_accounts()
        self.show_page(self.current_page)

    def _refresh_accounts(self) -> None:
        self.accounts = [a for a in self._items(self.client.get_accounts(), "accounts") if AccountService.is_open(a)]
        self.account_by_label.clear()
        labels: list[str] = []
        for account in self.accounts:
            account_id = str(self._field(account, "id", ""))
            name = str(self._field(account, "name", ""))
            status = str(self._field(account, "status", ""))
            label = f"{name or 'Account'} | {account_id} | {status}"
            labels.append(label)
            self.account_by_label[label] = account
        self.account_combo["values"] = labels
        active_id = self.context.active_account_id
        active = next((a for a in self.accounts if str(self._field(a, "id", "")) == active_id), None)
        if active is None and self.accounts:
            active = self.accounts[0]
            self.context.set_active(active)
        if active:
            label = next((k for k, v in self.account_by_label.items() if str(self._field(v, "id", "")) == self.context.active_account_id), "")
            self.account_var.set(label)
        else:
            self.account_var.set("")
        self.status_var.set(f"{len(self.accounts)} open account(s)")

    def _account_changed(self, _event: Any = None) -> None:
        account = self.account_by_label.get(self.account_var.get())
        if account:
            self.context.set_active(account)
            self.status_var.set(f"Active: {self.context.active_account_id}")
            self.show_page(self.current_page)

    def _require_account(self) -> str | None:
        try:
            return self.context.require_account_id()
        except RuntimeError:
            messagebox.showwarning("Edward", "Select an open trading account first.")
            return None

    def _card(self, parent: ttk.Frame, title: str, value: str, column: int) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.grid(row=0, column=column, sticky="nsew", padx=6)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text=value, style="CardValue.TLabel").pack(anchor="w", pady=(8, 0))

    def _page_overview(self) -> None:
        ttk.Label(self.content, text="Account overview", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        account_id = self._require_account()
        if not account_id:
            return
        positions = self.client.get_positions(account_id)
        portfolio = self.client.get_portfolio(account_id)
        summary = BalanceService.build_summary(positions, portfolio)

        cards = ttk.Frame(self.content)
        cards.pack(fill="x")
        for i in range(4):
            cards.columnconfigure(i, weight=1)
        self._card(cards, "Available", f"{self._money(summary.available)} {summary.currency}", 0)
        self._card(cards, "Blocked", f"{self._money(summary.blocked)} {summary.currency}", 1)
        self._card(cards, "Securities", f"{self._money(summary.securities)} {summary.currency}", 2)
        self._card(cards, "Portfolio value", f"{self._money(summary.portfolio_value)} {summary.currency}", 3)

        ttk.Label(self.content, text="Account", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(28, 8))
        active = self.context.active_account
        details = ttk.Frame(self.content)
        details.pack(fill="x")
        rows = [("Account ID", account_id), ("Name", active.name if active else ""), ("Status", active.status if active else "")]
        for row, (key, value) in enumerate(rows):
            ttk.Label(details, text=key, width=18).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Label(details, text=value).grid(row=row, column=1, sticky="w", pady=4)

    def _page_accounts(self) -> None:
        ttk.Label(self.content, text="Accounts", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        tree = self._tree(self.content, ("id", "name", "status"), (360, 180, 160))
        tree.pack(fill="both", expand=True)
        for account in self.accounts:
            tree.insert("", "end", values=(self._field(account, "id", ""), self._field(account, "name", ""), self._field(account, "status", "")))
        ttk.Label(self.content, text="Select an account in the top selector to make it active.").pack(anchor="w", pady=10)

    def _page_portfolio(self) -> None:
        ttk.Label(self.content, text="Portfolio", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        account_id = self._require_account()
        if not account_id:
            return
        response = self.client.get_positions(account_id)
        tree = self._tree(self.content, ("ticker", "uid", "balance", "blocked", "price", "yield"), (110, 360, 100, 100, 120, 120))
        tree.pack(fill="both", expand=True)
        for position in self._items(response, "securities"):
            tree.insert("", "end", values=(
                self._field(position, "ticker", ""),
                self._field(position, "instrument_uid", self._field(position, "figi", "")),
                self._field(position, "balance", ""),
                self._field(position, "blocked", ""),
                self._field(position, "current_price", ""),
                self._field(position, "expected_yield", ""),
            ))

    def _page_instruments(self) -> None:
        ttk.Label(self.content, text="Instrument catalog", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        controls = ttk.Frame(self.content)
        controls.pack(fill="x", pady=(0, 10))
        self.kind_var = tk.StringVar(value=INSTRUMENT_KINDS[0][1])
        self.kind_combo = ttk.Combobox(controls, textvariable=self.kind_var, state="readonly", values=[label for _, label in INSTRUMENT_KINDS], width=18)
        self.kind_combo.pack(side="left")
        self.filter_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.filter_var, width=35).pack(side="left", padx=8)
        ttk.Button(controls, text="Load", command=self._load_instruments).pack(side="left")
        self.instrument_tree = self._tree(self.content, ("ticker", "name", "currency", "uid", "trade"), (110, 280, 90, 400, 100))
        self.instrument_tree.pack(fill="both", expand=True)
        self.instrument_tree.bind("<Double-1>", self._instrument_selected)
        self._load_instruments()

    def _load_instruments(self) -> None:
        try:
            label = self.kind_var.get()
            kind = next(k for k, v in INSTRUMENT_KINDS if v == label)
            instruments = InstrumentCatalogService(self.client).list(kind, trade_available_only=True)
            query = self.filter_var.get().strip().casefold()
            if query:
                instruments = [i for i in instruments if query in str(self._field(i, "ticker", "")).casefold() or query in str(self._field(i, "name", "")).casefold()]
            for item in self.instrument_tree.get_children():
                self.instrument_tree.delete(item)
            for instrument in instruments:
                self.instrument_tree.insert("", "end", values=(
                    self._field(instrument, "ticker", ""),
                    self._field(instrument, "name", ""),
                    self._field(instrument, "currency", ""),
                    self._field(instrument, "uid", self._field(instrument, "instrument_uid", "")),
                    self._field(instrument, "api_trade_available_flag", ""),
                ), tags=(str(self._field(instrument, "uid", self._field(instrument, "instrument_uid", ""))),))
            self.status_var.set(f"Loaded {len(instruments)} instruments")
        except Exception as exc:
            self._show_error(exc)

    def _instrument_selected(self, _event: Any = None) -> None:
        selected = self.instrument_tree.selection()
        if not selected:
            return
        item = self.instrument_tree.item(selected[0])
        values = item.get("values", [])
        if not values:
            return
        self.selected_instrument = {"ticker": values[0], "name": values[1], "currency": values[2], "uid": values[3], "instrument_uid": values[3]}
        self.show_page("order")

    def _page_orders(self) -> None:
        ttk.Label(self.content, text="Active orders", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
        account_id = self._require_account()
        if not account_id:
            return
        orders = self._items(self.client.get_orders(account_id), "orders")
        tree = self._tree(self.content, ("order_id", "instrument", "direction", "quantity", "status"), (330, 300, 100, 100, 180))
        tree.pack(fill="both", expand=True)
        for order in orders:
            tree.insert("", "end", values=(
                self._field(order, "order_id", ""),
                self._field(order, "instrument_uid", ""),
                self._field(order, "direction", ""),
                self._field(order, "quantity", ""),
                self._field(order, "execution_report_status", self._field(order, "status", "")),
            ))
        ttk.Button(self.content, text="Cancel selected order", command=lambda t=tree: self._cancel_selected_order(t, orders)).pack(anchor="w", pady=10)

    def _cancel_selected_order(self, tree: ttk.Treeview, orders: list[Any]) -> None:
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Edward", "Select an active order.")
            return
        index = tree.index(selection[0])
        if index >= len(orders):
            return
        order_id = str(self._field(orders[index], "order_id", ""))
        account_id = self._require_account()
        if not account_id or not order_id:
            return
        if not messagebox.askyesno("Cancel order", f"Cancel order {order_id}?"):
            return
        try:
            OrderService(self.client).cancel_order(account_id, order_id)
            self.show_page("orders")
        except Exception as exc:
            self._show_error(exc)

    def _page_order(self) -> None:
        ttk.Label(self.content, text="Create order", style="Title.TLabel").pack(anchor="w", pady=(0, 16))
        account_id = self._require_account()
        if not account_id:
            return
        form = ttk.Frame(self.content)
        form.pack(anchor="nw", fill="x")
        self.order_vars = {name: tk.StringVar() for name in ("instrument", "side", "type", "quantity", "price", "stop_price")}
        self.order_vars["instrument"].set(self._field(self.selected_instrument, "ticker", ""))
        self.order_vars["side"].set("BUY")
        self.order_vars["type"].set("MARKET")
        fields = [("Instrument ticker", "instrument", "entry"), ("Operation", "side", "side"), ("Order type", "type", "type"), ("Quantity", "quantity", "entry"), ("Limit price", "price", "entry"), ("Stop price", "stop_price", "entry")]
        for row, (label, key, kind) in enumerate(fields):
            ttk.Label(form, text=label, width=20).grid(row=row, column=0, sticky="w", pady=5)
            if kind == "side":
                widget = ttk.Combobox(form, textvariable=self.order_vars[key], values=["BUY", "SELL"], state="readonly", width=28)
            elif kind == "type":
                widget = ttk.Combobox(form, textvariable=self.order_vars[key], values=["MARKET", "LIMIT", "STOP", "STOP_LIMIT"], state="readonly", width=28)
            else:
                widget = ttk.Entry(form, textvariable=self.order_vars[key], width=31)
            widget.grid(row=row, column=1, sticky="w", pady=5)
        ttk.Button(form, text="Load instrument", command=self._select_order_instrument).grid(row=0, column=2, padx=10)
        ttk.Button(self.content, text="Validate and confirm order", command=self._submit_order).pack(anchor="w", pady=18)
        ttk.Label(self.content, text="The final validation is performed immediately before submission using current adapter data.").pack(anchor="w")

    def _select_order_instrument(self) -> None:
        self.show_page("instruments")

    def _submit_order(self) -> None:
        account_id = self._require_account()
        if not account_id:
            return
        instrument = self.selected_instrument
        if not instrument:
            messagebox.showwarning("Edward", "Select an instrument from the catalog first.")
            return
        uid = str(self._field(instrument, "uid", self._field(instrument, "instrument_uid", "")))
        side = self.order_vars["side"].get().upper()
        order_type = self.order_vars["type"].get().upper()
        try:
            quantity = int(self.order_vars["quantity"].get())
        except ValueError:
            messagebox.showerror("Edward", "Quantity must be a positive integer.")
            return
        price = None
        stop_price = None
        try:
            if order_type in {"LIMIT", "STOP_LIMIT"}:
                price = Decimal(self.order_vars["price"].get())
            if order_type in {"STOP", "STOP_LIMIT"}:
                stop_price = Decimal(self.order_vars["stop_price"].get())
            request = OrderRequest(account_id=account_id, instrument_uid=uid, side=OrderSide(side), order_type=OrderType(order_type), quantity=quantity, price=price, stop_price=stop_price)
            validation = TradingValidator(AdapterTradingDataProvider(self.client)).validate(request)
        except Exception as exc:
            messagebox.showerror("Order validation failed", str(exc))
            return
        estimated = validation.estimated_total or Decimal("0")
        commission = validation.estimated_commission or Decimal("0")
        text = f"Instrument: {self._field(instrument, 'ticker', uid)}\nOperation: {side}\nType: {order_type}\nQuantity: {quantity}\nEstimated total: {self._money(estimated + commission)}\n\nSubmit order?"
        if not messagebox.askyesno("Confirm order", text):
            return
        try:
            result = OrderService(self.client).create_order(request)
            order_id = self._field(result, "order_id", self._field(result, "orderId", "unknown"))
            messagebox.showinfo("Edward", f"Order submitted.\nOrder ID: {order_id}")
            self.show_page("orders")
        except Exception as exc:
            self._show_error(exc)

    def _create_account(self) -> None:
        name = tk.simpledialog.askstring("Create sandbox account", "Account name (optional):") if hasattr(tk, "simpledialog") else None
        try:
            response = self.client.create_sandbox_account(name or None)
            new_id = self._field(response, "account_id", "")
            self._refresh_accounts()
            self.show_page("accounts")
            messagebox.showinfo("Edward", f"Sandbox account created.\n{new_id}")
        except Exception as exc:
            self._show_error(exc)

    def _close_account(self) -> None:
        account_id = self._require_account()
        if not account_id:
            return
        if not messagebox.askyesno("Close sandbox account", f"Close account {account_id}?"):
            return
        try:
            self.client.close_sandbox_account(account_id)
            self.context.clear()
            self._refresh_accounts()
            self.show_page("accounts")
        except Exception as exc:
            self._show_error(exc)

    @staticmethod
    def _tree(parent: ttk.Frame, columns: tuple[str, ...], widths: tuple[int, ...]) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        for column, width in zip(columns, widths):
            tree.heading(column, text=column.replace("_", " ").title())
            tree.column(column, width=width, minwidth=70, anchor="w")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        return tree

    def _show_error(self, exc: Exception) -> None:
        self.status_var.set("Error")
        messagebox.showerror("Edward", f"{type(exc).__name__}: {exc}")

    def _close(self) -> None:
        try:
            self.adapter_process.terminate()
            self.adapter_process.wait(timeout=5)
        except Exception:
            try:
                self.adapter_process.kill()
            except Exception:
                pass
        self.destroy()


def run_gui(production: bool = False) -> None:
    environment = Environment.PRODUCTION if production else Environment.SANDBOX
    token_store = TokenStore()
    token = token_store.get()
    if not token:
        token = request_and_save_token(token_store)
    if not token:
        return
    adapter_process = _start_adapter(token, environment)
    client = TInvestAdapterClient()
    try:
        _wait_for_adapter(client, adapter_process)
        app = EdwardApp(client, adapter_process, environment)
        app.mainloop()
    finally:
        if adapter_process.poll() is None:
            adapter_process.terminate()
            try:
                adapter_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                adapter_process.kill()
