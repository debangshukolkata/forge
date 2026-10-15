from settings import get_port


def test_port_default() -> None:
    assert get_port({}) == 8080


def test_port_from_config() -> None:
    assert get_port({"port": "9000"}) == 9000
