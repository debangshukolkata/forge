# ruff: noqa: F811, I001
"""T04: an email typed in a different letter case is the same account (sign-up, lookup, login, changing your own email)."""

from __future__ import annotations

from template_support import PASSWORD, harness  # noqa: F401  (pytest fixture)

from app import crud


def _signup(harness, email):
    return harness.client.post("/api/v1/users/signup", json={"email": email, "password": PASSWORD})


def test_second_signup_with_other_case_is_refused(harness):
    assert _signup(harness, "Case.Test@Example.com").status_code == 200
    assert _signup(harness, "case.test@example.com").status_code == 400
    assert _signup(harness, "CASE.TEST@EXAMPLE.COM").status_code == 400


def test_lookup_ignores_case(harness):
    assert _signup(harness, "Mixed.Case@Example.com").status_code == 200
    assert crud.get_user_by_email(session=harness.session, email="mixed.case@example.com") is not None
    assert crud.get_user_by_email(session=harness.session, email="MIXED.CASE@EXAMPLE.COM") is not None


def test_login_ignores_case(harness):
    assert _signup(harness, "login.case@example.com").status_code == 200
    for typed in ("login.case@example.com", "Login.Case@Example.com", "LOGIN.CASE@EXAMPLE.COM"):
        response = harness.client.post(
            "/api/v1/login/access-token", data={"username": typed, "password": PASSWORD}
        )
        assert response.status_code == 200, typed


def test_changing_own_email_to_a_taken_one_in_other_case_is_refused(harness):
    first = harness.make_user("taken@example.com")
    second = harness.make_user("second@example.com")
    harness.login_as(second)
    assert harness.client.patch("/api/v1/users/me", json={"email": "TAKEN@example.com"}).status_code == 409
    assert first.email == "taken@example.com"


def test_exact_duplicate_is_still_refused_and_unknown_user_still_fails(harness):
    assert _signup(harness, "plain@example.com").status_code == 200
    assert _signup(harness, "plain@example.com").status_code == 400
    response = harness.client.post(
        "/api/v1/login/access-token", data={"username": "nobody@example.com", "password": PASSWORD}
    )
    assert response.status_code == 400
