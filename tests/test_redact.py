from __future__ import annotations

from forge.safety.redact import Redactor


def test_registered_value_is_masked_everywhere() -> None:
    redactor = Redactor()
    redactor.register("canary-value-42", "TEST_KEY")

    assert (
        redactor.redact("a canary-value-42 b canary-value-42")
        == "a [REDACTED:TEST_KEY] b [REDACTED:TEST_KEY]"
    )


def test_short_values_are_not_registered() -> None:
    redactor = Redactor()
    redactor.register("admin", "PG")

    assert redactor.redact("admin panel") == "admin panel"


def test_patterns_catch_unregistered_secrets() -> None:
    redactor = Redactor()
    url = "postgresql://app:s3cr3t-pw@db:5432/claims"  # check_secrets: fake
    traceback_line = f"OperationalError: connection to {url} failed"
    token = ".".join(["eyJhbGciOiJIUzI1NiJ9", "eyJzdWIiOiJ1c2VyMTIzNCJ9", "c2lnbmF0dXJlLXZhbHVlLXg"])

    assert "s3cr3t-pw" not in redactor.redact(traceback_line)
    assert "postgresql://app:" in redactor.redact(traceback_line)  # structure stays readable
    assert redactor.redact(f"token={token}").count("REDACTED") == 1
    assert "abcdefghij0123456789" not in redactor.redact("Authorization: Bearer abcdefghij0123456789")
    assert "hunter22" not in redactor.redact("DB_PASSWORD=hunter22")


def test_nested_data_is_redacted() -> None:
    redactor = Redactor()
    redactor.register("canary-value-42", "K")

    data = {"a": ["x canary-value-42", {"b": "canary-value-42"}], "n": 3}

    assert redactor.redact_data(data) == {"a": ["x [REDACTED:K]", {"b": "[REDACTED:K]"}], "n": 3}
