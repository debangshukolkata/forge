from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from claims_app.models.base import Base, IdType


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(IdType, primary_key=True)
    claim_number: Mapped[str] = mapped_column(String(30), unique=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"))
    status: Mapped[str] = mapped_column(String(20), default="submitted")
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False))
    description: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
