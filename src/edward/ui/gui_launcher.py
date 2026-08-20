from __future__ import annotations

# Install localization and error reporting before starting the GUI so all
# presentation concerns stay outside the trading services and T-Invest adapter.
from edward.ui import localization_bootstrap  # noqa: F401
from edward.ui.app import EdwardApp, run_gui
from edward.ui.error_reporting import install_error_reporting


install_error_reporting(EdwardApp)


if __name__ == "__main__":
    run_gui()
