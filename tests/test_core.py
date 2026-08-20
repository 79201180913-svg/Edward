from edward.core import hello


def test_hello() -> None:
    assert hello() == "Edward 0.1.0"
