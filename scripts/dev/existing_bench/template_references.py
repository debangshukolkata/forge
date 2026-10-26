"""Known solutions for the template challenges, used only by `selftest` to prove the checks can pass."""

from __future__ import annotations

from .harness import Edit

CRUD = "backend/app/crud.py"


def _doc(signature: str, docstring: str) -> Edit:
    return Edit(CRUD, signature + "\n", signature + f'\n    """{docstring}"""\n')


T02_REFERENCE = (
    Edit(
        CRUD,
        "def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:\n",
        "def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:\n"
        '    """Apply the given changes to a user, hashing a new password; returns the saved user."""\n',
    ),
    _doc(
        "def create_user(*, session: Session, user_create: UserCreate) -> User:",
        "Create a user with a hashed password; returns the saved user.",
    ),
    _doc(
        "def get_user_by_email(*, session: Session, email: str) -> User | None:",
        "Find a user by email; returns None when there is none.",
    ),
    _doc(
        "def authenticate(*, session: Session, email: str, password: str) -> User | None:",
        "Check an email and password; returns the user, or None when they do not match.",
    ),
    _doc(
        "def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:",
        "Create an item for an owner; returns the saved item.",
    ),
    Edit(CRUD, "from typing import Any\n\n", "\n"),
)

T03_REFERENCE = (
    Edit(
        "backend/app/models.py",
        "    created_at: datetime | None = Field(default_factory=get_datetime_utc)\n    owner_id: uuid.UUID = Field(",
        "    created_at: datetime | None = Field(default_factory=get_datetime_utc)\n"
        "    updated_at: datetime | None = Field(default_factory=get_datetime_utc)\n    owner_id: uuid.UUID = Field(",
    ),
    Edit(
        "backend/app/models.py",
        "    owner_id: uuid.UUID\n    created_at: datetime | None = None\n\n\nclass ItemsPublic",
        "    owner_id: uuid.UUID\n    created_at: datetime | None = None\n    updated_at: datetime | None = None\n\n\nclass ItemsPublic",
    ),
    Edit(
        "backend/app/api/routes/items.py",
        "    item.sqlmodel_update(update_dict)\n",
        "    item.sqlmodel_update(update_dict)\n    item.updated_at = get_datetime_utc()\n",
    ),
    Edit(
        "backend/app/api/routes/items.py",
        "from app.models import Item,",
        "from app.models import get_datetime_utc, Item,",
    ),
)

T03_MIGRATION = '''"""Add updated_at to Item

Revision ID: a1b2c3d4e5f6
Revises: fe56fa70289e
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('item', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('item', 'updated_at')
'''

T03_REFERENCE_FILES = {
    "backend/app/alembic/versions/a1b2c3d4e5f6_add_updated_at_to_item.py": T03_MIGRATION,
    "backend/tests/api/routes/test_item_updated_at.py": "def test_placeholder_counts_as_a_new_test():\n    assert True\n",
}

T04_REFERENCE = (
    Edit(
        CRUD,
        '    db_obj = User.model_validate(\n        user_create, update={"hashed_password": get_password_hash(user_create.password)}\n    )\n',
        "    db_obj = User.model_validate(\n        user_create,\n        update={\n"
        '            "hashed_password": get_password_hash(user_create.password),\n'
        '            "email": user_create.email.lower(),\n        },\n    )\n',
    ),
    Edit(
        CRUD,
        "    statement = select(User).where(User.email == email)\n",
        "    statement = select(User).where(func.lower(User.email) == email.lower())\n",
    ),
    Edit(CRUD, "from sqlmodel import Session, select", "from sqlmodel import Session, func, select"),
)
