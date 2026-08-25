from __future__ import annotations

from pathlib import Path
from tkinter import StringVar, filedialog, messagebox, ttk
from typing import Any

from edward.config.application_settings import ApplicationSettingsStore
from edward.security.token_store import TokenStore
from edward.storage.sqlite_store import SQLiteStore
from edward.ui.token_dialog import request_and_save_token


def install_settings_page(app_class: type[Any]) -> None:
    if getattr(app_class, "_settings_page_v04_installed", False):
        return

    original_shell = app_class._shell

    def shell(self: Any) -> None:
        original_shell(self)
        children = self.nav.winfo_children()
        if any(
            getattr(child, "winfo_class", lambda: "")() == "TButton"
            and child.cget("text") == "Настройки"
            for child in children
            if getattr(child, "winfo_class", lambda: "")() == "TButton"
        ):
            return

        separator = next(
            (child for child in children if getattr(child, "winfo_class", lambda: "")() == "TSeparator"),
            None,
        )
        button = ttk.Button(
            self.nav,
            text="Настройки",
            style="Nav.TButton",
            command=lambda: self.show_page("settings"),
        )
        if separator is not None:
            button.pack(fill="x", pady=2, before=separator)
        else:
            button.pack(fill="x", pady=2)

    def page_settings(self: Any) -> None:
        ttk.Label(self.content, text="Настройки", style="Title.TLabel").pack(anchor="w", pady=(0, 16))

        token_frame = ttk.LabelFrame(self.content, text="T-Invest", padding=16)
        token_frame.pack(fill="x", pady=(0, 14))
        token_store = TokenStore()
        token = token_store.get()
        status = "Токен не установлен"
        if token:
            status = f"Установлен: {'*' * max(0, len(token) - 4)}{token[-4:]}"
        token_var = StringVar(value=status)
        ttk.Label(token_frame, textvariable=token_var).pack(side="left")

        def replace_token() -> None:
            try:
                new_token = request_and_save_token(token_store)
                if new_token:
                    token_var.set(f"Установлен: {'*' * max(0, len(new_token) - 4)}{new_token[-4:]}")
                    self.status_var.set("T-Invest токен обновлён")
            except Exception as exc:
                messagebox.showerror("Ошибка токена", str(exc), parent=self)

        ttk.Button(token_frame, text="Заменить токен", command=replace_token).pack(side="right")

        storage_frame = ttk.LabelFrame(self.content, text="Локальное хранилище", padding=16)
        storage_frame.pack(fill="x")
        store = ApplicationSettingsStore()
        settings = store.load()
        SQLiteStore(settings.storage_path)
        storage_var = StringVar(value=settings.storage_path)
        ttk.Entry(storage_frame, textvariable=storage_var).pack(side="left", fill="x", expand=True)

        def choose_folder() -> None:
            current = Path(storage_var.get()).expanduser()
            selected = filedialog.askdirectory(
                parent=self,
                title="Выберите папку для локальных данных Edward",
                initialdir=str(current if current.is_dir() else Path.home()),
            )
            if selected:
                storage_var.set(str(Path(selected).resolve()))

        def save_storage() -> None:
            try:
                selected_path = str(Path(storage_var.get()).expanduser().resolve())
                store.save(type(settings)(storage_path=selected_path))
                SQLiteStore(selected_path)
                storage_var.set(selected_path)
                self.status_var.set("Путь локального хранилища сохранён")
                messagebox.showinfo(
                    "Настройки",
                    f"Путь локального хранилища сохранён:\n{selected_path}\n\nedward.db готова в выбранной папке.",
                    parent=self,
                )
            except Exception as exc:
                messagebox.showerror("Ошибка настроек", str(exc), parent=self)

        ttk.Button(storage_frame, text="Выбрать…", command=choose_folder).pack(side="left", padx=(8, 0))
        ttk.Button(storage_frame, text="Сохранить", command=save_storage).pack(side="left", padx=(8, 0))

        ttk.Label(
            self.content,
            text="Настройки приложения являются глобальными. Результаты Walk-Forward и анализа акций будут храниться в edward.db выбранной папки.",
            style="Subtitle.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(14, 0))

    app_class._shell = shell
    app_class._page_settings = page_settings
    app_class._settings_page_v04_installed = True
