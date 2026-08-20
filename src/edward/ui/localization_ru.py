from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


_TRANSLATIONS = {
    "Trading Platform v0.1": "Торговая платформа v0.1",
    "⟳ Refresh": "⟳ Обновить",
    "Active account:": "Активный счёт:",
    "Ready": "Готово",
    "Overview": "Обзор",
    "Accounts": "Счета",
    "Portfolio": "Портфель",
    "Instruments": "Инструменты",
    "Active orders": "Активные заявки",
    "Create order": "Создать заявку",
    "Create sandbox account": "Создать тестовый счёт",
    "Close active account": "Закрыть активный счёт",
    "Account overview": "Обзор счёта",
    "Available": "Доступно",
    "Blocked": "Заблокировано",
    "Securities": "Ценные бумаги",
    "Portfolio value": "Стоимость портфеля",
    "Account": "Счёт",
    "Account ID": "ID счёта",
    "Name": "Название",
    "Status": "Статус",
    "Select an account in the top selector to make it active.": "Выберите счёт в верхнем списке, чтобы сделать его активным.",
    "Instrument catalog": "Каталог инструментов",
    "Load": "Загрузить",
    "Loaded": "Загружено",
    "Cancel selected order": "Отменить выбранную заявку",
    "Select an active order.": "Выберите активную заявку.",
    "Cancel order": "Отмена заявки",
    "Create order": "Создание заявки",
    "Instrument ticker": "Тикер инструмента",
    "Operation": "Операция",
    "Order type": "Тип заявки",
    "Quantity": "Количество",
    "Limit price": "Лимитная цена",
    "Stop price": "Стоп-цена",
    "Load instrument": "Выбрать инструмент",
    "Validate and confirm order": "Проверить и подтвердить заявку",
    "The final validation is performed immediately before submission using current adapter data.": "Финальная проверка выполняется непосредственно перед отправкой по актуальным данным адаптера.",
    "Select an open trading account first.": "Сначала выберите открытый торговый счёт.",
    "Select an instrument from the catalog first.": "Сначала выберите инструмент из каталога.",
    "Quantity must be a positive integer.": "Количество должно быть положительным целым числом.",
    "Order validation failed": "Ошибка проверки заявки",
    "Confirm order": "Подтверждение заявки",
    "Submit order?": "Отправить заявку?",
    "Order submitted.": "Заявка отправлена.",
    "Order ID": "ID заявки",
    "Sandbox account created.": "Тестовый счёт создан.",
    "Account name (optional):": "Название счёта (необязательно):",
    "Close sandbox account": "Закрытие тестового счёта",
    "Close account": "Закрыть счёт",
    "Error": "Ошибка",
    "Account": "Счёт",
    "Ticker": "Тикер",
    "Uid": "UID",
    "Balance": "Количество",
    "Blocked": "Заблокировано",
    "Price": "Цена",
    "Yield": "Доходность",
    "Direction": "Направление",
    "Quantity": "Количество",
    "Execution Report Status": "Статус исполнения",
    "Instrument": "Инструмент",
    "Currency": "Валюта",
    "Trade": "Доступность торговли",
    "Id": "ID",
    "Name": "Название",
    "Status": "Статус",
}


def tr(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _TRANSLATIONS.get(value, value)


_ORIGINAL_LABEL = ttk.Label
_ORIGINAL_BUTTON = ttk.Button
_ORIGINAL_CHECKBUTTON = ttk.Checkbutton
_ORIGINAL_RADIOBUTTON = ttk.Radiobutton
_ORIGINAL_TREEVIEW = ttk.Treeview
_ORIGINAL_MESSAGEBOX = {
    "showwarning": messagebox.showwarning,
    "showerror": messagebox.showerror,
    "showinfo": messagebox.showinfo,
    "askyesno": messagebox.askyesno,
}


class RussianTreeview(_ORIGINAL_TREEVIEW):
    def heading(self, column, option=None, **kw):
        if "text" in kw:
            kw["text"] = tr(kw["text"])
        return super().heading(column, option, **kw)


def _localized_widget_factory(original):
    def factory(*args, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = tr(kwargs["text"])
        return original(*args, **kwargs)
    return factory


def _patch_messagebox() -> None:
    for name, original in _ORIGINAL_MESSAGEBOX.items():
        def wrapper(title, message, *args, _original=original, **kwargs):
            return _original(tr(title), tr(message), *args, **kwargs)
        setattr(messagebox, name, wrapper)


# Translate widgets created by the existing GUI without changing application logic.
ttk.Label = _localized_widget_factory(_ORIGINAL_LABEL)
ttk.Button = _localized_widget_factory(_ORIGINAL_BUTTON)
ttk.Checkbutton = _localized_widget_factory(_ORIGINAL_CHECKBUTTON)
ttk.Radiobutton = _localized_widget_factory(_ORIGINAL_RADIOBUTTON)
ttk.Treeview = RussianTreeview
_patch_messagebox()


def localize_dynamic_text(value: str) -> str:
    if value.startswith("Active: "):
        return "Активный счёт: " + value[len("Active: "):]
    if value.endswith(" open account(s)"):
        return "Открытых счетов: " + value[:-len(" open account(s)")]
    if value.startswith("Loaded ") and value.endswith(" instruments"):
        return "Загружено инструментов: " + value[len("Loaded "):-len(" instruments")]
    if value == "Error":
        return "Ошибка"
    return str(tr(value))


# StringVar is used for status text as well as account/instrument values. Only
# known status messages are translated; identifiers and API values are kept intact.
_ORIGINAL_STRINGVAR_SET = tk.StringVar.set


def _stringvar_set(self, value):
    if isinstance(value, str):
        value = localize_dynamic_text(value)
    return _ORIGINAL_STRINGVAR_SET(self, value)


tk.StringVar.set = _stringvar_set
