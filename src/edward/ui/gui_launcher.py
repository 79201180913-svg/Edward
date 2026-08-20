from __future__ import annotations

# Install localization before importing the GUI so all existing presentation
# widgets and the application window use Russian labels without changing backend logic.
from edward.ui import localization_bootstrap  # noqa: F401
from edward.ui.app import run_gui


if __name__ == "__main__":
    run_gui()
