# ruff: noqa: F811, I001
"""T02: crud.py has no `Any` return type and every public function has a docstring; behaviour is unchanged.

(The mypy error count is compared by the runner, which has the baseline number.)"""

from __future__ import annotations

import ast

from template_support import PASSWORD, harness  # noqa: F401  (pytest fixture)

from app import crud
from app.models import UserUpdate


def _functions(repo):
    tree = ast.parse((repo / "backend" / "app" / "crud.py").read_text(encoding="utf-8"))
    return [n for n in tree.body if isinstance(n, ast.FunctionDef)]


def test_no_function_returns_any(repo):
    for function in _functions(repo):
        returns = function.returns
        assert returns is not None, f"{function.name} has no return annotation"
        assert "Any" not in ast.dump(returns), f"{function.name} returns Any"


def test_update_user_returns_user(repo):
    update = next(f for f in _functions(repo) if f.name == "update_user")
    assert ast.unparse(update.returns) == "User"


def test_every_public_function_has_a_docstring(repo):
    for function in _functions(repo):
        if not function.name.startswith("_"):
            assert ast.get_docstring(function), f"{function.name} has no docstring"


def test_update_user_still_changes_email_and_password(harness):
    user = harness.make_user("typed@example.com")
    updated = crud.update_user(
        session=harness.session,
        db_user=user,
        user_in=UserUpdate(email="typed2@example.com", password="another-pass-2"),
    )
    assert updated.email == "typed2@example.com"
    assert (
        crud.authenticate(session=harness.session, email="typed2@example.com", password="another-pass-2")
        is not None
    )
    assert crud.authenticate(session=harness.session, email="typed2@example.com", password=PASSWORD) is None


def test_authenticate_unknown_user_is_none(harness):
    assert crud.authenticate(session=harness.session, email="nobody@example.com", password=PASSWORD) is None
