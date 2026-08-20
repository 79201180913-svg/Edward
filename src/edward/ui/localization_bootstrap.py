from __future__ import annotations

import tkinter as tk

from edward.ui.localization_ru import tr


_original_title = tk.Wm.title


def _title(self, string=None):
    if string is not None:
        string = tr(string)
    return _original_title(self, string) if string is not None else _original_title(self)


tk.Wm.title = _title
