from __future__ import annotations

# Install localization before importing the GUI so all ttk widgets created by
# the existing presentation layer use Russian labels without changing backend logic.
from edward.ui import localization_ru  # noqa: F401
from edward.ui.app import run_gui


if __name__ == "__main__":
    run_gui()
