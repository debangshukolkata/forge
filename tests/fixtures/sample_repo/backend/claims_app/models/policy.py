from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from claims_app.models.base import Base, IdType


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(IdType, primary_key=True)
    policy_number: Mapped[str] = mapped_column(String(30), unique=True)
    holder_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
