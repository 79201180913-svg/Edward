from __future__ import annotations

import os
import subprocess
from pathlib import Path

from edward.ui import localization_bootstrap  # noqa: F401
from edward.ui import app as app_module
from edward.ui.app import EdwardApp, main
from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.api.stop_order_json_fix import install as install_stop_order_json_fix
from edward.ui.error_reporting import install_error_reporting
from edward.ui.trading_ui_guard import install_trading_ui_guard
from edward.ui.sandbox_funding_ui import install_sandbox_funding_ui
from edward.ui.sandbox_data_routing import install_sandbox_data_routing
from edward.ui.operations_history_ui import install_operations_history_ui
from edward.ui.ux_fixes import install_ux_fixes
from edward.ui.compat_fixes import install_compat_fixes
from edward.ui.console_logging import install_console_logging
from edward.ui.final_fixes import install_final_fixes
from edward.ui.contract_ui_fixes import install_contract_ui_fixes
from edward.ui.portfolio_quantity_fix import install_portfolio_quantity_fix
from edward.ui.final_history_fix import install_final_history_fix
from edward.ui.final_order_history_fix import install_final_order_history_fix
from edward.ui.final_contract_override import install_final_contract_override
from edward.ui.price_fallback_fix import install_price_fallback
from edward.ui.version_ui_fix import install_version_ui_fix
from edward.ui.instrument_screen import install_instrument_screen
from edward.ui.instrument_screen_ux_v03 import install_instrument_screen_ux
from edward.ui.stop_order_ui_v03_fixed import install_stop_order_ui
from edward.ui.order_ticket_v03 import install_order_ticket
from edward.ui.stop_limit_ui_v03 import install_stop_limit_ui
from edward.ui.instrument_scroll_v03 import install_instrument_scroll
from edward.ui.portfolio_pnl_v03 import install_portfolio_pnl
from edward.config.settings import Environment


def _contract_adapter_start(token: str, environment: Environment):
    root = Path(__file__).resolve().parents[3]
    python_exe = root / ".venv-tinvest" / "Scripts" / "python.exe"
    adapter_script = root / "runtime" / "tinvest_adapter_fixed.py"
    if not python_exe.exists():
        raise RuntimeError(f"T-Invest Python runtime not found: {python_exe}")
    if not adapter_script.exists():
        raise RuntimeError(f"Contract adapter wrapper not found: {adapter_script}")
    env = os.environ.copy()
    env["EDWARD_TINVEST_TOKEN"] = token
    env["EDWARD_TINVEST_ENV"] = environment.value
    env["EDWARD_TINVEST_PORT"] = "8765"
    print(f"[ADAPTER] Starting contract wrapper: {adapter_script}", flush=True)
    print(f"[ADAPTER] Environment: {environment.value.upper()}", flush=True)
    return subprocess.Popen(
        [str(python_exe), str(adapter_script)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=None,
        stderr=None,
    )


app_module._start_adapter = _contract_adapter_start
install_stop_order_json_fix(TInvestAdapterClient)

install_sandbox_data_routing()
install_error_reporting(EdwardApp)
install_trading_ui_guard(EdwardApp)
install_sandbox_funding_ui(EdwardApp)
install_operations_history_ui(EdwardApp)
install_ux_fixes(EdwardApp)
install_price_fallback()
install_compat_fixes(EdwardApp)
install_console_logging(EdwardApp)
install_final_fixes(EdwardApp)
install_contract_ui_fixes(EdwardApp)
install_portfolio_quantity_fix(EdwardApp)
install_final_history_fix(EdwardApp)
install_final_order_history_fix(EdwardApp)
install_final_contract_override(EdwardApp)
install_version_ui_fix(EdwardApp)
install_instrument_screen(EdwardApp)
install_instrument_screen_ux(EdwardApp)
install_stop_order_ui(EdwardApp)
install_order_ticket(EdwardApp)
install_stop_limit_ui(EdwardApp)
install_instrument_scroll(EdwardApp)
install_portfolio_pnl(EdwardApp)


if __name__ == "__main__":
    main()
