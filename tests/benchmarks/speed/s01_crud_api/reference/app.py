from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, field_validator

app = FastAPI()


class NoteIn(BaseModel):
    title: str
    body: str = ""

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be empty")
        return value


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(os.environ.get("NOTES_DB", "notes.db"))) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL)"
        )
        yield db
        db.commit()


def as_note(row: tuple[int, str, str]) -> dict[str, object]:
    return {"id": row[0], "title": row[1], "body": row[2]}


@app.on_event("startup")
def startup() -> None:
    with connect():
        pass


@app.post("/notes", status_code=201)
def create(note: NoteIn) -> dict[str, object]:
    with connect() as db:
        cursor = db.execute("INSERT INTO notes (title, body) VALUES (?, ?)", (note.title, note.body))
        return {"id": cursor.lastrowid, "title": note.title, "body": note.body}


@app.get("/notes")
def list_notes(q: str | None = None) -> list[dict[str, object]]:
    with connect() as db:
        rows = db.execute("SELECT id, title, body FROM notes ORDER BY id").fetchall()
    notes = [as_note(r) for r in rows]
    if q:
        needle = q.lower()
        notes = [n for n in notes if needle in str(n["title"]).lower() or needle in str(n["body"]).lower()]
    return notes


def fetch(db: sqlite3.Connection, note_id: int) -> tuple[int, str, str]:
    row = db.execute("SELECT id, title, body FROM notes WHERE id = ?", (note_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    return row  # type: ignore[no-any-return]


@app.get("/notes/{note_id}")
def get_note(note_id: int) -> dict[str, object]:
    with connect() as db:
        return as_note(fetch(db, note_id))


@app.put("/notes/{note_id}")
def update(note_id: int, note: NoteIn) -> dict[str, object]:
    with connect() as db:
        fetch(db, note_id)
        db.execute("UPDATE notes SET title = ?, body = ? WHERE id = ?", (note.title, note.body, note_id))
        return {"id": note_id, "title": note.title, "body": note.body}


@app.delete("/notes/{note_id}", status_code=204)
def delete(note_id: int) -> Response:
    with connect() as db:
        fetch(db, note_id)
        db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return Response(status_code=204)
