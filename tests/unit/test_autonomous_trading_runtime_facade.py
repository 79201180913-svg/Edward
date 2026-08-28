import inspect

from edward.services.autonomous_trading_runtime_facade import AutonomousTradingRuntimeFacade


def test_facade_constructor_accepts_ui_account_positional_and_optional_policy():
    signature = inspect.signature(AutonomousTradingRuntimeFacade.__init__)

    account_id = signature.parameters["account_id"]
    policy = signature.parameters["policy"]

    assert account_id.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert policy.default is not inspect.Parameter.empty


def test_facade_default_policy_matches_autonomous_ui_defaults():
    signature = inspect.signature(AutonomousTradingRuntimeFacade.__init__)
    policy = signature.parameters["policy"].default

    assert policy.slots == 5
    assert str(policy.reserve_pct) == "10"
