from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Task:
    id: int
    title: str
    done: bool = False

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "title": self.title, "done": self.done}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Task:
        return cls(id=int(data["id"]), title=str(data["title"]), done=bool(data.get("done", False)))  # type: ignore[call-overload]
