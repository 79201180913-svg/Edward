from __future__ import annotations

# Install presentation/data routing hooks before starting the GUI.
from edward.ui import localization_bootstrap  # noqa: F401
from edward.ui.app import EdwardApp, main
from edward.ui.error_reporting import install_error_reporting
from edward.ui.trading_ui_guard import install_trading_ui_guard
from edward.ui.sandbox_funding_ui import install_sandbox_funding_ui
from edward.ui.sandbox_data_routing import install_sandbox_data_routing


install_sandbox_data_routing()
install_error_reporting(EdwardApp)
install_trading_ui_guard(EdwardApp)
install_sandbox_funding_ui(EdwardApp)


if __name__ == "__main__":
    main()
