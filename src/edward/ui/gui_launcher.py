from __future__ import annotations

# Route the GUI's adapter startup through the contract wrapper before importing
# edward.ui.app.main, because app.main imports _start_adapter into its module.
import edward.ui.app as _app_module

_original_start_adapter = _app_module._start_adapter


def _start_adapter_with_contract_wrapper(token, environment):
    from pathlib import Path
    import os
    import subprocess

    root = Path(__file__).resolve().parents[3]
    python_exe = root / ".venv-tinvest" / "Scripts" / "python.exe"
    wrapper = root / "runtime" / "tinvest_adapter_fixed.py"
    if not wrapper.exists():
        return _original_start_adapter(token, environment)
    env = os.environ.copy()
    env["EDWARD_TINVEST_TOKEN"] = token
    env["EDWARD_TINVEST_ENV"] = environment.value
    env["EDWARD_TINVEST_PORT"] = "8765"
    print(f"[ADAPTER] Starting contract wrapper: {wrapper}", flush=True)
    print(f"[ADAPTER] Environment: {environment.value.upper()}", flush=True)
    return subprocess.Popen(
        [str(python_exe), str(wrapper)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=None,
        stderr=None,
    )


_app_module._start_adapter = _start_adapter_with_contract_wrapper

from edward.ui import localization_bootstrap  # noqa: E402,F401
from edward.ui.app import EdwardApp, main  # noqa: E402
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


install_sandbox_data_routing()
install_error_reporting(EdwardApp)
install_trading_ui_guard(EdwardApp)
install_sandbox_funding_ui(EdwardApp)
install_operations_history_ui(EdwardApp)
install_ux_fixes(EdwardApp)
install_compat_fixes(EdwardApp)
install_console_logging(EdwardApp)
install_final_fixes(EdwardApp)
install_contract_ui_fixes(EdwardApp)
install_portfolio_quantity_fix(EdwardApp)
install_final_history_fix(EdwardApp)
install_final_order_history_fix(EdwardApp)


if __name__ == "__main__":
    main()
