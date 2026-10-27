"""Migrate a JSON data file from schema version 1 to version 2."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

KNOWN_FIELDS = {"id", "name", "email", "phone", "created", "tags"}
CREATED = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class MigrationError(Exception):
    """The document cannot be migrated at all."""


class RecordError(ValueError):
    """One record is malformed."""


def _email(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise RecordError("email is not a string")
    email = value.strip().lower()
    local, at, domain = email.partition("@")
    if not at or "@" in domain or not local or not domain or re.search(r"\s", email):
        raise RecordError(f"bad email {value!r}")
    return email


def _phone(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordError("phone is not a string")
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if not 7 <= len(digits) <= 15:
        raise RecordError(f"phone has {len(digits)} digits")
    return digits


def _created(value: Any) -> str:
    match = CREATED.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise RecordError(f"bad created date {value!r}")
    month, day, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        raise RecordError(f"not a real date {value!r}") from None


def _tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts: list[Any] = value.split(",")
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        parts = value
    else:
        raise RecordError("tags must be a string or a list of strings")
    tags: list[str] = []
    for part in parts:
        tag = part.strip().lower()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def migrate_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise RecordError("not an object")
    user_id = record.get("id")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id < 1:
        raise RecordError(f"bad id {user_id!r}")
    name = record.get("name")
    words = name.split() if isinstance(name, str) else []
    if not words:
        raise RecordError("missing name")
    user: dict[str, Any] = {
        "id": user_id,
        "first_name": words[0],
        "last_name": " ".join(words[1:]),
        "email": _email(record.get("email")),
        "phone": _phone(record.get("phone")),
        "created_at": _created(record.get("created")),
        "tags": _tags(record.get("tags")),
    }
    extra = {key: copy.deepcopy(value) for key, value in record.items() if key not in KNOWN_FIELDS}
    if extra:
        user["extra"] = extra
    return user


def migrate_data(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(data, dict):
        raise MigrationError("the document is not an object")
    if data.get("schema_version") == 2:
        return copy.deepcopy(data), []
    if data.get("version") != 1:
        raise MigrationError("unknown schema version")
    users = data.get("users")
    if not isinstance(users, list):
        raise MigrationError("users is not a list")
    result: dict[str, Any] = {"schema_version": 2}
    for key, value in data.items():
        if key not in ("version", "users"):
            result[key] = copy.deepcopy(value)
    migrated: list[dict[str, Any]] = []
    seen: set[int] = set()
    log: list[str] = []
    for index, record in enumerate(users):
        try:
            user = migrate_record(record)
            if user["id"] in seen:
                raise RecordError(f"duplicate id {user['id']}")
        except RecordError as error:
            log.append(f"record {index}: {error}")
            continue
        seen.add(user["id"])
        migrated.append(user)
    result["users"] = migrated
    return result, log


def migrate_file(path: Path | str, log_path: Path | str | None = None) -> dict[str, Any]:
    path = Path(path)
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as error:
        raise MigrationError(f"cannot read {path}: {error}") from None
    result, log = migrate_data(data)
    if data.get("schema_version") == 2:
        return {"status": "already_current", "migrated": 0, "skipped": 0, "log": []}
    backup = path.with_name(path.name + ".v1.bak")
    if not backup.exists():
        shutil.copyfile(path, backup)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    if log_path is not None and log:
        with open(log_path, "a", encoding="utf-8", newline="\n") as stream:
            stream.write("".join(line + "\n" for line in log))
    return {"status": "migrated", "migrated": len(result["users"]), "skipped": len(log), "log": log}


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        file_arg, log_arg = argv[0], None
    elif len(argv) == 3 and argv[1] == "--log":
        file_arg, log_arg = argv[0], argv[2]
    else:
        print("usage: migrate FILE [--log LOGFILE]", file=sys.stderr)
        return 2
    try:
        summary = migrate_file(file_arg, log_arg)
    except MigrationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{summary['status']}: {summary['migrated']} migrated, {summary['skipped']} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
