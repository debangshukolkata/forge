"""Lessons (spec §12.3): what Forge learned about working well — from fixes, stuck episodes, user corrections,
diagnose findings and recurring review findings. Only lessons the user approved are ever used; they are
retrieved per task (search over the task text and paths) into the pinned `lessons` slot, capped (~800 tokens).

<forge_home>/learning/lessons.json   all lessons with scope, trigger keywords, evidence, confidence, usage
<forge_home>/learning/PLAYBOOK.md    the approved global lessons, readable by humans
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, TypeAdapter

from forge.kb.bm25 import BM25, tokenize
from forge.llm.tokens import count_text_tokens
from forge.safety.redact import default_redactor

Status = Literal["proposed", "approved", "rejected", "archived"]
DUPLICATE_OVERLAP = 0.8
DEFAULT_TOKEN_CAP = 800


class Lesson(BaseModel):
    id: str
    text: str
    scope: str  # repo:<slug> | profile:<name> | global | user
    keywords: list[str] = []
    evidence: str = ""  # workspace / step / report that produced it
    source: str = "retro"  # retro | fix | stuck | correction | diagnose | review | mid-run | contract
    confidence: Literal["high", "medium", "low"] = "medium"
    status: Status = "proposed"
    uses: int = 0
    helped: int = 0
    created: str = ""
    updated: str = ""


_LIST = TypeAdapter(list[Lesson])


class LessonStore:
    def __init__(self, home: Path) -> None:
        self.root = home / "learning"
        self.path = self.root / "lessons.json"

    def all(self) -> list[Lesson]:
        return _LIST.validate_json(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def _save(self, lessons: list[Lesson]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(_LIST.dump_json(lessons, indent=1))
        playbook = [item for item in lessons if item.scope == "global" and item.status == "approved"]
        lines = ["# Playbook (approved global lessons)", "", *[f"- {item.text}" for item in playbook]]
        (self.root / "PLAYBOOK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def propose(
        self, text: str, scope: str, *, source: str = "retro", evidence: str = "", confidence: str = "medium"
    ) -> Lesson:
        """Adds a proposed lesson (redacted), or returns the near-duplicate it matches (hygiene: merge)."""
        clean = default_redactor.redact(text.strip())
        lessons = self.all()
        for lesson in lessons:
            if (
                lesson.scope == scope
                and lesson.status != "rejected"
                and _overlap(lesson.text, clean) >= DUPLICATE_OVERLAP
            ):
                return lesson
        now = datetime.now().isoformat(timespec="seconds")
        lesson = Lesson(
            id=f"L{len(lessons) + 1}",
            text=clean,
            scope=scope,
            keywords=_keywords(clean),
            evidence=default_redactor.redact(evidence),
            source=source,
            confidence=confidence if confidence in ("high", "medium", "low") else "medium",  # type: ignore[arg-type]
            created=now,
            updated=now,
        )
        self._save([*lessons, lesson])
        return lesson

    def set_status(self, lesson_id: str, status: Status, text: str | None = None) -> Lesson:
        lessons = self.all()
        for lesson in lessons:
            if lesson.id.upper() == lesson_id.upper():
                lesson.status = status
                if text:
                    lesson.text = default_redactor.redact(text.strip())
                    lesson.keywords = _keywords(lesson.text)
                lesson.updated = datetime.now().isoformat(timespec="seconds")
                self._save(lessons)
                return lesson
        raise KeyError(lesson_id)

    def promote(self, lesson_id: str) -> Lesson:
        """Only on the user's explicit request: make a repo/profile lesson global."""
        lessons = self.all()
        for lesson in lessons:
            if lesson.id.upper() == lesson_id.upper():
                lesson.scope = "global"
                self._save(lessons)
                return lesson
        raise KeyError(lesson_id)

    def pending(self, scopes: tuple[str, ...]) -> list[Lesson]:
        return [item for item in self.all() if item.status == "proposed" and item.scope in scopes]

    def retrieve(
        self, scopes: tuple[str, ...], query: str, k: int = 5, token_cap: int = DEFAULT_TOKEN_CAP
    ) -> list[Lesson]:
        """The approved lessons most relevant to this task, within the scopes this workspace may see."""
        candidates = [item for item in self.all() if item.status == "approved" and item.scope in scopes]
        if not candidates:
            return []
        scores = BM25([tokenize(f"{item.text} {' '.join(item.keywords)}") for item in candidates]).scores(
            tokenize(query)
        )
        ranked = sorted(zip(scores, candidates, strict=True), key=lambda pair: -pair[0])
        chosen: list[Lesson] = []
        used = 0
        for score, lesson in ranked:
            if len(chosen) >= k:
                break
            if score <= 0 and lesson.scope != "user":  # user preferences always apply
                continue
            cost = count_text_tokens(lesson.text)
            if used + cost > token_cap:
                continue
            chosen.append(lesson)
            used += cost
        self._count_use(chosen)
        return chosen

    def _count_use(self, used: list[Lesson]) -> None:
        if not used:
            return
        ids = {item.id for item in used}
        lessons = self.all()
        for lesson in lessons:
            if lesson.id in ids:
                lesson.uses += 1
        self._save(lessons)

    def stale(self, min_uses: int = 0, older_than_days: int = 90) -> list[Lesson]:
        """Hygiene: approved lessons never used for a long time are suggested for archive."""
        cutoff = datetime.now().timestamp() - older_than_days * 86400
        return [
            item
            for item in self.all()
            if item.status == "approved"
            and item.uses <= min_uses
            and datetime.fromisoformat(item.created).timestamp() < cutoff
        ]


def render_for_pin(lessons: list[Lesson]) -> str | None:
    if not lessons:
        return None
    return "Lessons from earlier work (approved by the user):\n" + "\n".join(
        f"- {item.text}" for item in lessons
    )


def _keywords(text: str) -> list[str]:
    words = [w for w in tokenize(text) if len(w) > 3]
    return sorted(set(words))[:12]


def _overlap(a: str, b: str) -> float:
    left, right = set(tokenize(a)), set(tokenize(b))
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def parse_proposals(text: str) -> list[str]:
    """Lessons proposed in a retro, one per '- LESSON: ...' line."""
    return [m.strip() for m in re.findall(r"^\s*-\s*LESSON:\s*(.+)$", text, re.MULTILINE)]


def dump(home: Path) -> str:
    return json.dumps([item.model_dump() for item in LessonStore(home).all()])
