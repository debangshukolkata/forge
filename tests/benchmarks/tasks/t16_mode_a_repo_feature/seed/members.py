"""The people who may borrow."""

from __future__ import annotations

from models import Member


class MemberRegistry:
    def __init__(self) -> None:
        self._members: dict[str, Member] = {}

    def add(self, member_id: str, name: str) -> Member:
        if member_id in self._members:
            raise ValueError(f"member {member_id} already exists")
        member = Member(member_id, name)
        self._members[member_id] = member
        return member

    def get(self, member_id: str) -> Member:
        return self._members[member_id]  # KeyError for an unknown member
