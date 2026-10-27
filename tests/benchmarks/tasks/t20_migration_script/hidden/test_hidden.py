from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from migrate import MigrationError, RecordError, main, migrate_data, migrate_file, migrate_record


def good(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": 1,
        "name": "Ana Paul",
        "email": "ANA@Example.org",
        "phone": "(555) 123-4567",
        "created": "03/15/2024",
        "tags": "admin, Beta,admin",
    }
    record.update(overrides)
    return record


def test_record_happy_path() -> None:
    assert migrate_record(good()) == {
        "id": 1,
        "first_name": "Ana",
        "last_name": "Paul",
        "email": "ana@example.org",
        "phone": "5551234567",
        "created_at": "2024-03-15",
        "tags": ["admin", "beta"],
    }


def test_record_error_is_a_value_error() -> None:
    assert issubclass(RecordError, ValueError)
    assert issubclass(MigrationError, Exception)


@pytest.mark.parametrize(
    "name, first, last",
    [("Cher", "Cher", ""), ("  Ana   Maria  de la Cruz ", "Ana", "Maria de la Cruz"), ("A\tB", "A", "B")],
)
def test_name_splitting(name: str, first: str, last: str) -> None:
    user = migrate_record(good(name=name))
    assert (user["first_name"], user["last_name"]) == (first, last)


@pytest.mark.parametrize("bad", [{"name": "   "}, {"name": None}, {"name": 5}, {"name": ""}])
def test_bad_names(bad: dict[str, Any]) -> None:
    with pytest.raises(RecordError):
        migrate_record(good(**bad))


def test_missing_name_and_id_rules() -> None:
    record = good()
    del record["name"]
    with pytest.raises(RecordError):
        migrate_record(record)
    for bad_id in (0, -3, "1", 1.0, True, None):
        with pytest.raises(RecordError):
            migrate_record(good(id=bad_id))
    record = good()
    del record["id"]
    with pytest.raises(RecordError):
        migrate_record(record)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_blank_email_is_null(value: Any) -> None:
    assert migrate_record(good(email=value))["email"] is None


def test_missing_email_is_null() -> None:
    record = good()
    del record["email"]
    assert migrate_record(record)["email"] is None


@pytest.mark.parametrize("value", ["nope", "@x.org", "a@", "a@@x.org", "a@b@c.org", "a b@x.org", 5, ["a@b.c"]])
def test_bad_emails(value: Any) -> None:
    with pytest.raises(RecordError):
        migrate_record(good(email=value))


def test_email_is_stripped_and_lowered() -> None:
    assert migrate_record(good(email="  Bob@X.ORG "))["email"] == "bob@x.org"


@pytest.mark.parametrize(
    "value, expected",
    [("555-1234", "5551234"), ("+44 20 7946 0958", "442079460958"), ("123456789012345", "123456789012345"), (None, None), ("", None), ("n/a", None), ("  ", None)],
)
def test_phone(value: Any, expected: Any) -> None:
    assert migrate_record(good(phone=value))["phone"] == expected


@pytest.mark.parametrize("value", ["123456", "1234567890123456", 5551234, ["555"]])
def test_bad_phone(value: Any) -> None:
    with pytest.raises(RecordError):
        migrate_record(good(phone=value))


def test_missing_phone_is_null() -> None:
    record = good()
    del record["phone"]
    assert migrate_record(record)["phone"] is None


@pytest.mark.parametrize("value", ["3/15/2024", "03/15/24", "2024-03-15", "02/30/2024", "13/01/2024", "00/10/2024", "03-15-2024", "", None, 20240315, "03/15/2024 "])
def test_bad_created(value: Any) -> None:
    with pytest.raises(RecordError):
        migrate_record(good(created=value))


def test_created_leap_day_and_missing() -> None:
    assert migrate_record(good(created="02/29/2024"))["created_at"] == "2024-02-29"
    with pytest.raises(RecordError):
        migrate_record(good(created="02/29/2023"))
    record = good()
    del record["created"]
    with pytest.raises(RecordError):
        migrate_record(record)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("a,b", ["a", "b"]),
        (" A , a ,B,, ,b", ["a", "b"]),
        ("", []),
        (None, []),
        (["Red", " red ", "", "Blue"], ["red", "blue"]),
        ([], []),
    ],
)
def test_tags(value: Any, expected: list[str]) -> None:
    assert migrate_record(good(tags=value))["tags"] == expected


@pytest.mark.parametrize("value", [5, {"a": 1}, ["a", 2], True])
def test_bad_tags(value: Any) -> None:
    with pytest.raises(RecordError):
        migrate_record(good(tags=value))


def test_missing_tags_are_an_empty_list() -> None:
    record = good()
    del record["tags"]
    assert migrate_record(record)["tags"] == []


def test_extra_fields_are_kept_under_extra() -> None:
    user = migrate_record(good(nickname="Annie", score={"a": [1, 2]}))
    assert user["extra"] == {"nickname": "Annie", "score": {"a": [1, 2]}}
    assert "extra" not in migrate_record(good())


def test_not_an_object_is_bad() -> None:
    for record in ("text", 5, None, [1]):
        with pytest.raises(RecordError):
            migrate_record(record)  # type: ignore[arg-type]


def test_document_migration_skips_bad_records_and_logs_them() -> None:
    data = {
        "version": 1,
        "meta": {"exported_by": "legacy"},
        "users": [
            good(id=1),
            good(id=2, email="bad"),
            "junk",
            good(id=1, name="Dup Licate"),
            good(id=4, name="Dan"),
            good(id=2, name="Second Try"),
        ],
    }
    before = copy.deepcopy(data)
    result, log = migrate_data(data)
    assert data == before  # the argument is not modified
    assert result["schema_version"] == 2 and "version" not in result
    assert result["meta"] == {"exported_by": "legacy"}
    assert [u["id"] for u in result["users"]] == [1, 4, 2]
    assert result["users"][2]["first_name"] == "Second"  # id 2 was never accepted before
    assert [line.split(":")[0] for line in log] == ["record 1", "record 2", "record 3"]
    assert "duplicate" in log[2]
    assert all(isinstance(line, str) and line.startswith("record ") for line in log)


def test_result_does_not_share_objects_with_the_input() -> None:
    data = {"version": 1, "meta": {"k": [1]}, "users": [good(extra_list=[1, 2])]}
    result, _ = migrate_data(data)
    result["meta"]["k"].append(2)
    result["users"][0]["extra"]["extra_list"].append(3)
    assert data["meta"] == {"k": [1]} and data["users"][0]["extra_list"] == [1, 2]


def test_already_v2_is_returned_unchanged() -> None:
    doc = {"schema_version": 2, "users": [{"id": 1, "first_name": "A"}], "meta": {"x": 1}}
    result, log = migrate_data(doc)
    assert result == doc and result is not doc and log == []
    result["users"].append(1)
    assert len(doc["users"]) == 1


def test_migrating_twice_is_a_fixed_point() -> None:
    once, _ = migrate_data({"version": 1, "users": [good()]})
    twice, log = migrate_data(once)
    assert twice == once and log == []


@pytest.mark.parametrize(
    "doc",
    [{}, {"version": 3, "users": []}, {"version": 1}, {"version": 1, "users": {"a": 1}}, {"version": "1", "users": []}, {"schema_version": 3, "users": []}, {"users": []}],
)
def test_unmigratable_documents(doc: dict[str, Any]) -> None:
    with pytest.raises(MigrationError):
        migrate_data(doc)


def test_empty_users_list() -> None:
    result, log = migrate_data({"version": 1, "users": []})
    assert result == {"schema_version": 2, "users": []} and log == []


def write(path: Path, data: Any) -> bytes:
    raw = json.dumps(data, indent=1).encode("utf-8")
    path.write_bytes(raw)
    return raw


def test_file_migration_backup_log_and_format(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    original = write(path, {"version": 1, "users": [good(name="Zoë Muñoz"), good(id=2, created="bad"), good(id=3)]})
    log_path = tmp_path / "migration.log"
    summary = migrate_file(path, log_path)
    assert summary["status"] == "migrated" and (summary["migrated"], summary["skipped"]) == (2, 1)
    assert len(summary["log"]) == 1 and summary["log"][0].startswith("record 1:")
    backup = tmp_path / "data.json.v1.bak"
    assert backup.read_bytes() == original
    text = path.read_text(encoding="utf-8")
    assert text.endswith("}\n") and not text.endswith("}\n\n")
    assert "Zoë" in text and "\\u00eb" not in text  # ensure_ascii=False
    assert text == json.dumps(json.loads(text), ensure_ascii=False, indent=2) + "\n"
    data = json.loads(text)
    assert data["schema_version"] == 2 and [u["id"] for u in data["users"]] == [1, 3]
    assert log_path.read_text(encoding="utf-8").splitlines() == summary["log"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data.json", "data.json.v1.bak", "migration.log"]


def test_running_twice_changes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write(path, {"version": 1, "users": [good(), good(id=2, email="x")]})
    log_path = tmp_path / "migration.log"
    migrate_file(path, log_path)
    snapshot = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    again = migrate_file(path, log_path)
    assert again == {"status": "already_current", "migrated": 0, "skipped": 0, "log": []}
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == snapshot


def test_existing_backup_is_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write(path, {"version": 1, "users": [good()]})
    backup = tmp_path / "data.json.v1.bak"
    backup.write_bytes(b"precious earlier backup")
    migrate_file(path)
    assert backup.read_bytes() == b"precious earlier backup"
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 2


def test_log_is_appended_not_overwritten(tmp_path: Path) -> None:
    log_path = tmp_path / "migration.log"
    log_path.write_text("older line\n", encoding="utf-8")
    path = tmp_path / "data.json"
    write(path, {"version": 1, "users": [good(email="bad")]})
    migrate_file(path, log_path)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "older line" and len(lines) == 2 and lines[1].startswith("record 0:")


def test_all_records_bad_still_migrates_the_document(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write(path, {"version": 1, "users": [{"id": "x"}, 5]})
    summary = migrate_file(path)
    assert (summary["status"], summary["migrated"], summary["skipped"]) == ("migrated", 0, 2)
    assert json.loads(path.read_text(encoding="utf-8")) == {"schema_version": 2, "users": []}


@pytest.mark.parametrize("content", [b"{not json", b"", b"\xff\xfe\x00", b"[1, 2]", b'{"version": 7}', b'{"version": 1, "users": 3}'])
def test_unmigratable_files_are_left_untouched(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "data.json"
    path.write_bytes(content)
    log_path = tmp_path / "migration.log"
    with pytest.raises(MigrationError):
        migrate_file(path, log_path)
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]
    assert path.read_bytes() == content


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(MigrationError):
        migrate_file(tmp_path / "nothing.json")
    assert list(tmp_path.iterdir()) == []


def test_accepts_str_paths(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write(path, {"version": 1, "users": [good()]})
    assert migrate_file(str(path), str(tmp_path / "l.log"))["migrated"] == 1


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "data.json"
    write(path, {"version": 1, "users": [good(), good(id=2, email="bad")]})
    log_path = tmp_path / "m.log"
    assert main([str(path), "--log", str(log_path)]) == 0
    assert log_path.read_text(encoding="utf-8").startswith("record 1:")
    assert main([str(path)]) == 0  # already current
    broken = tmp_path / "broken.json"
    broken.write_text("{nope", encoding="utf-8")
    assert main([str(broken)]) == 1
    assert broken.read_text(encoding="utf-8") == "{nope"
    assert main([]) == 2
    assert main([str(path), "--oops"]) == 2
    assert main([str(path), "--log"]) == 2
    capsys.readouterr()
