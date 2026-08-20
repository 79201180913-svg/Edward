from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from edward.ui.localization_ru import tr


_original_title = tk.Wm.title


def _title(self, string=None):
    if string is not None:
        string = tr(string)
    return _original_title(self, string) if string is not None else _original_title(self)


tk.Wm.title = _title


def _translate_message(value: object) -> object:
    if not isinstance(value, str):
        return value
    result = str(tr(value))
    replacements = {
        "Instrument:": "Инструмент:",
        "Operation:": "Операция:",
        "Type:": "Тип:",
        "Quantity:": "Количество:",
        "Estimated total:": "Расчётная сумма:",
        "Order ID:": "ID заявки:",
        "Submit order?": "Отправить заявку?",
        "Order submitted.": "Заявка отправлена.",
        "Cancel order ": "Отменить заявку ",
        "Close account ": "Закрыть счёт ",
    }
    for source, target in replacements.items():
        result = result.replace(source, target)
    return result


# localization_ru handles ordinary widget/messagebox strings. This second layer
# translates dynamic multi-line dialogs assembled at runtime by the UI.
for _name in ("showwarning", "showerror", "showinfo", "askyesno"):
    _original = getattr(messagebox, _name)

    def _wrapper(title, message, *args, _original=_original, **kwargs):
        return _original(_translate_message(title), _translate_message(message), *args, **kwargs)

    setattr(messagebox, _name, _wrapper)
