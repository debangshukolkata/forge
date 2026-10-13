Build a small REST API for notes in one file, `app.py`, using FastAPI and SQLite (the standard `sqlite3` module). Install what you need into this project's own environment.

- `app` is the FastAPI application object.
- The database file path comes from the environment variable `NOTES_DB` (default `notes.db`); create the table on startup if it does not exist. Read the variable when the application starts handling requests, not at import time, so a test can set it before creating a client.
- `POST /notes` with JSON `{"title": str, "body": str (optional, default "")}` creates a note and returns status 201 and `{"id": int, "title": ..., "body": ...}`. A missing or empty title (after trimming) is a 422.
- `GET /notes` returns a list of all notes ordered by id; `GET /notes?q=text` returns only notes whose title or body contains the text, ignoring case.
- `GET /notes/{id}` returns the note or 404 with `{"detail": "not found"}`.
- `PUT /notes/{id}` replaces title and body (same validation as create) and returns the note; 404 if it does not exist.
- `DELETE /notes/{id}` returns 204 with no body; 404 if it does not exist.

Write tests for it too (with FastAPI's `TestClient`). Keep it small and clean.
