from pathlib import Path


ADAPTER_PATH = Path(__file__).parents[2] / "runtime" / "tinvest_adapter_fixed.py"


def test_sandbox_adapter_supports_contractual_instrument_kinds():
    source = ADAPTER_PATH.read_text(encoding="utf-8")

    expected = {
        '"SHARE"': '"Shares"',
        '"BOND"': '"Bonds"',
        '"ETF"': '"Etfs"',
        '"CURRENCY"': '"Currencies"',
        '"FUTURES"': '"Futures"',
        '"OPTION"': '"Options"',
        '"SP"': '"StructuredNotes"',
        '"DFA"': '"Dfas"',
    }

    for kind, method in expected.items():
        assert f"{kind}: {method}" in source


def test_sandbox_adapter_no_longer_rejects_option_kind():
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert '"OPTION": "Options"' in source
    assert 'raise ValueError(f"Unsupported instrument kind: {kind}")' in source
