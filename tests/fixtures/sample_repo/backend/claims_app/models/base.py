from __future__ import annotations

from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import DeclarativeBase

# BIGSERIAL on Postgres; SQLite only auto-increments an INTEGER primary key.
IdType = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass
