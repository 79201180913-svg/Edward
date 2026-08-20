from __future__ import annotations

from typing import Any, Callable

from edward.services.instrument_catalog_service import InstrumentCatalogService


INSTRUMENT_KINDS = (
    ("SHARE", "Shares"),
    ("BOND", "Bonds"),
    ("ETF", "ETF"),
    ("CURRENCY", "Currencies"),
    ("FUTURES", "Futures"),
    ("OPTION", "Options"),
)


def _field(value: Any, name: str, default: Any = "") -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _uid(instrument: Any) -> str:
    return str(_field(instrument, "uid", _field(instrument, "instrument_uid", "")))


def _flag(value: Any) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return str(value)


def _print_instruments(instruments: list[Any], start: int = 1) -> None:
    print("\nINSTRUMENTS")
    print("----------------------------------------")
    if not instruments:
        print("No instruments found.")
        return
    for index, instrument in enumerate(instruments, start=start):
        ticker = _field(instrument, "ticker", "")
        name = _field(instrument, "name", "")
        uid = _uid(instrument)
        currency = _field(instrument, "currency", "")
        buy = _flag(_field(instrument, "buy_available_flag", ""))
        sell = _flag(_field(instrument, "sell_available_flag", ""))
        trade = _flag(_field(instrument, "api_trade_available_flag", ""))
        print(f"{index}. {ticker} | {name} | {currency} | BUY={buy} SELL={sell} API={trade} | uid={uid}")
    print("----------------------------------------")


def show_catalog(client: Any, on_selected: Callable[[Any], None] | None = None) -> None:
    """Interactive catalog: type -> authoritative list -> local filter -> selection."""
    catalog = InstrumentCatalogService(client)

    print("\nINSTRUMENT CATALOG")
    print("----------------------------------------")
    for index, (_, label) in enumerate(INSTRUMENT_KINDS, start=1):
        print(f"{index}. {label}")
    print("0. Back")

    try:
        kind_index = int(input("Instrument type: ").strip())
    except ValueError:
        print("Invalid instrument type.")
        return
    if kind_index == 0:
        return
    if not 1 <= kind_index <= len(INSTRUMENT_KINDS):
        print("Invalid instrument type.")
        return

    kind, _ = INSTRUMENT_KINDS[kind_index - 1]
    try:
        instruments = catalog.list(kind, trade_available_only=True)
    except Exception as exc:
        print(f"Unable to load instrument catalog: {exc}")
        return

    print(f"\nLoaded {len(instruments)} instruments.")
    query = input("Filter by ticker/name (Enter = all): ").strip().casefold()
    if query:
        instruments = catalog.search(query, kind, True)

    page_size = 20
    page = 0
    while True:
        start = page * page_size
        current = instruments[start : start + page_size]
        if not current:
            print("No instruments on this page.")
            return
        _print_instruments(current, start + 1)
        total_pages = max(1, (len(instruments) + page_size - 1) // page_size)
        print(f"Page {page + 1}/{total_pages}")
        print("Enter number to select, N next, P previous, F new filter, B back")
        choice = input("Select: ").strip().casefold()
        if choice == "b":
            return
        if choice == "n":
            if page + 1 < total_pages:
                page += 1
            continue
        if choice == "p":
            if page > 0:
                page -= 1
            continue
        if choice == "f":
            query = input("Filter: ").strip().casefold()
            instruments = catalog.search(query, kind, True)
            page = 0
            continue
        try:
            absolute_index = int(choice) - 1
            if not start <= absolute_index < start + len(current):
                raise IndexError
            selected = instruments[absolute_index]
        except (ValueError, IndexError):
            print("Invalid instrument selection.")
            continue

        print("\nINSTRUMENT")
        print("----------------------------------------")
        print(f"Ticker:   {_field(selected, 'ticker', '')}")
        print(f"Name:     {_field(selected, 'name', '')}")
        print(f"UID:      {_uid(selected)}")
        print(f"FIGI:     {_field(selected, 'figi', '')}")
        print(f"ISIN:     {_field(selected, 'isin', '')}")
        print(f"Currency: {_field(selected, 'currency', '')}")
        print(f"Class:    {_field(selected, 'class_code', '')}")
        print(f"Buy:      {_flag(_field(selected, 'buy_available_flag', ''))}")
        print(f"Sell:     {_flag(_field(selected, 'sell_available_flag', ''))}")
        print(f"API:      {_flag(_field(selected, 'api_trade_available_flag', ''))}")
        print(f"Step:     {_field(selected, 'min_price_increment', '')}")
        print("----------------------------------------")
        if on_selected:
            on_selected(selected)
        return
