from __future__ import annotations

from typing import Any
from tkinter import ttk


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _instrument_name(response: Any) -> str:
    """Extract a user-facing instrument name from adapter GetInstrument response."""
    candidates = [response]
    for key in ("instrument", "security", "item", "data"):
        nested = _field(response, key, None)
        if nested is not None:
            candidates.append(nested)

    for candidate in candidates:
        for key in ("name", "instrument_name", "instrumentName", "short_name", "shortName"):
            value = _field(candidate, key, None)
            if value not in (None, ""):
                return str(value)
    return ""


def _load_name(client: Any, uid: str, ticker: str) -> str:
    try:
        response = client.get_instrument(uid)
        name = _instrument_name(response)
        if name:
            return name
    except Exception as exc:
        print(f"[PORTFOLIO INSTRUMENT NAME] ticker={ticker!r} lookup failed: {type(exc).__name__}: {exc}", flush=True)
    return ticker or "—"


def install(app_class: type[Any]) -> None:
    original = getattr(app_class, "_page_portfolio", None)
    if original is None or getattr(original, "_portfolio_names_v03_wrapped", False):
        return

    def page_portfolio(self: Any) -> None:
        original(self)
        tree = getattr(self, "_portfolio_tree", None)
        if tree is None or not isinstance(tree, ttk.Treeview):
            return

        columns = tuple(tree["columns"])
        if "instrument_name" in columns:
            return

        # Preserve the existing order and insert the human-readable name after ticker.
        new_columns = ("ticker", "instrument_name") + tuple(c for c in columns if c != "ticker")
        tree["columns"] = new_columns
        tree.heading("ticker", text="Тикер")
        tree.column("ticker", width=90, anchor="w")
        tree.heading("instrument_name", text="Инструмент")
        tree.column("instrument_name", width=260, anchor="w")

        client = getattr(self, "client", None)
        if client is None:
            return

        cache: dict[str, str] = {}
        for iid in tree.get_children(""):
            values = list(tree.item(iid, "values"))
            if not values:
                continue
            ticker = str(values[0] or "")
            # Find position through the row index used by portfolio_page_v03.
            position = None
            if iid.startswith("position-"):
                try:
                    index = int(iid.split("-", 1)[1])
                    positions = getattr(self, "_portfolio_tree_positions", None)
                    if isinstance(positions, list) and 0 <= index < len(positions):
                        position = positions[index]
                except (TypeError, ValueError):
                    position = None

            uid = ""
            if isinstance(position, dict):
                uid = str(position.get("instrument_uid", position.get("uid", "")) or "")
            if not uid:
                name = ticker or "—"
            else:
                if uid not in cache:
                    cache[uid] = _load_name(client, uid, ticker)
                name = cache[uid]

            tree.item(iid, values=[ticker, name, *values[1:]])

    page_portfolio._portfolio_names_v03_wrapped = True
    app_class._page_portfolio = page_portfolio
