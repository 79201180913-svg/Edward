from __future__ import annotations

from pathlib import Path


def _read_version() -> str:
    root = Path(__file__).resolve().parents[3]
    version_file = root / "VERSION"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        version = "0.2.0"
    return version or "0.2.0"


def install_version_ui_fix(EdwardApp) -> None:
    original_shell = EdwardApp._shell
    version = _read_version()
    target = f"Торговая платформа v{version.removesuffix('.0')}"

    def patched_shell(self):
        original_shell(self)
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                except Exception:
                    continue
                if isinstance(text, str) and text.startswith("Торговая платформа v"):
                    child.configure(text=target)

    EdwardApp._shell = patched_shell
