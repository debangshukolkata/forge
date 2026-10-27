Write `migrate.py` (standard library only): a migration of a JSON data file from schema version 1 to version 2. `sample_v1.json` in this folder shows the old format. It must be safe to run twice, must not lose the original, and must cope with bad records by logging and skipping them.

**Version 1 document**: `{"version": 1, "users": [...], ...other top-level keys...}`; a record has `id`, `name`, `email`, `phone`, `created` (`MM/DD/YYYY`), `tags` (one comma-separated string) and possibly other fields.

**Version 2 document**: `{"schema_version": 2, "users": [...], ...the other top-level keys unchanged...}` (the `version` key is gone); a user is
`{"id": int, "first_name": str, "last_name": str, "email": str | null, "phone": str | null, "created_at": "YYYY-MM-DD", "tags": [str, ...]}` plus `"extra": {...}` only when the v1 record had fields beyond the six known ones (those fields, copied unchanged). Users keep their input order.

**Record rules** (`migrate_record(record: dict) -> dict` returns the v2 user, or raises `RecordError`, a subclass of `ValueError`, with a short reason)
- `id`: a positive integer (not a boolean). Required.
- `name`: a string with some non-blank text. `first_name` is its first whitespace-separated word, `last_name` the remaining words joined by single spaces (`""` when there is only one word).
- `email`: missing, `null` or blank gives `null`. Otherwise it must be a string (anything else is bad); it is stripped and lower-cased and must contain exactly one `@` with a non-empty part on each side and no whitespace, else the record is bad.
- `phone`: missing, `null` or without digits gives `null`. Otherwise keep only the digits (`"(555) 123-4567"` becomes `"5551234567"`); fewer than 7 or more than 15 digits makes the record bad. A non-string phone is bad.
- `created`: required, exactly `MM/DD/YYYY` with two-digit month and day and four-digit year, and a real calendar date (`02/30/2024` is bad). Output `YYYY-MM-DD`.
- `tags`: missing or `null` gives `[]`. A string is split on commas; a list of strings is accepted as is. Each tag is stripped and lower-cased, empty ones dropped, duplicates removed keeping the first occurrence. Anything else (or a list with a non-string) makes the record bad.
- A record that is not a JSON object is bad.

**Document rules** (`migrate_data(data: dict) -> tuple[dict, list[str]]` returns the v2 document and the log lines; it never changes its argument)
- `version == 1` is migrated. `schema_version == 2` is already current: return an equal deep copy and no log lines. Anything else, or a `users` value that is not a list, raises `MigrationError` (define it in the module).
- A bad record is skipped and one log line `record <index>: <reason>` is produced (index = 0-based position in the v1 `users` list). A record whose `id` was already used by an earlier good record is skipped too (reason mentions `duplicate`). Other records are still migrated.

**File function** `migrate_file(path, log_path=None) -> dict`
- Reads the JSON file at `path` (UTF-8). Unreadable file or invalid JSON raises `MigrationError` and leaves everything untouched.
- Already version 2: nothing is written (not the file, not a backup, not the log); returns `{"status": "already_current", "migrated": 0, "skipped": 0, "log": []}`.
- Version 1: first copies the original bytes to `<path>.v1.bak` in the same folder, but never overwrites a backup that exists; then writes the v2 document to `path` atomically (a temporary file in the same folder, then replace; no temporary file may be left behind), UTF-8, `ensure_ascii=False`, `indent=2`, ending with a newline. When `log_path` is given, appends each log line plus `\n` to it (UTF-8). Returns `{"status": "migrated", "migrated": n, "skipped": m, "log": [...]}`. If the document is rejected (`MigrationError`) nothing is written.
- Running it a second time on the result therefore changes nothing.

**`main(argv: list[str]) -> int`**: `migrate FILE [--log LOGFILE]`; exit code 0 on success (including already current), 1 on a `MigrationError` (and nothing written), 2 on a usage error. You may print messages.

Write tests for it too (`test_migrate.py`).
