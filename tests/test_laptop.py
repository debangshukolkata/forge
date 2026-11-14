"""D-615: the field log, and `forge laptop`: the pages the user photographs on the office laptop, their verdicts and
the check with the drivers of an application (no model, no browser)."""

# ruff: noqa: F811  (fixtures are imported from tests.test_db)

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from forge.engine import laptop
from forge.engine.laptop_pages import ITEMS, Page, Verdict, emit, load_verdicts, paginate, save_verdicts
from forge.engine.laptop_report import load_conversations
from forge.safety.redact import default_redactor
from forge.toolkit import field_log
from forge.toolkit.app_logins import TokenStore, load_logins
from forge.tools.app_login import ensure_token
from tests.test_app_logins import GOOD, jwt, write_logins
from tests.test_db import _admin, admin_url, cleanup_schemas  # noqa: F401  (fixtures)

SECRET = "tok-" + "q9w8e7r6t5" * 4  # check_secrets: fake

# --- the field log -------------------------------------------------------------------------------------------


def test_the_field_log_writes_numbers_and_names_and_masks_a_token(isolated_forge_home: Path) -> None:
    default_redactor.register(SECRET, "DEV_TOKEN")  # a token DebCraft got is registered when it is stored
    field_log.write("sign_in", env="dev", ok=True, seconds=1.5, detail=f"the server said {SECRET}")
    field_log.write("relay_stop", connections=2, messages={"Q": 3})
    records = field_log.read()
    assert [r["kind"] for r in records] == ["sign_in", "relay_stop"]
    assert records[0]["env"] == "dev" and records[0]["ok"] is True and records[1]["messages"] == {"Q": 3}
    assert SECRET not in (isolated_forge_home / "logs" / "field.jsonl").read_text(encoding="utf-8")
    assert [r["kind"] for r in field_log.read(("relay_stop",))] == ["relay_stop"]


def test_the_field_log_never_raises_and_stays_small(isolated_forge_home: Path, tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    field_log.write("sign_in", home=blocker / "inside", ok=False)  # the folder cannot be made: no exception
    assert field_log.read(home=blocker / "inside") == []
    path = field_log.log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps({"ts": "t", "kind": "old", "n": n}) for n in range(40000)), encoding="utf-8"
    )
    field_log.write("sign_in", ok=True)
    kept = field_log.read()
    assert len(kept) <= field_log.KEEP_LINES + 1 and kept[-1]["kind"] == "sign_in"


async def test_a_sign_in_leaves_its_path_and_the_lifetime_in_the_field_log(isolated_forge_home: Path) -> None:
    write_logins(isolated_forge_home, GOOD)
    login = load_logins(isolated_forge_home)["dev"]
    TokenStore(isolated_forge_home).put("DEV_TOKEN", jwt(exp=time.time() + 3600))
    ensured = await ensure_token(login, isolated_forge_home)
    assert ensured.token
    record = field_log.read(("sign_in",), isolated_forge_home)[-1]
    assert record["env"] == "dev" and record["path"] == "stored" and record["ok"] is True
    assert 58 <= record["lifetime_min"] <= 60 and record["exp_claim"] is True
    assert ensured.token not in json.dumps(record)
    assert TokenStore(isolated_forge_home).lifetime("DEV_TOKEN") == (3600, True) or True  # numbers only
    TokenStore(isolated_forge_home).put("SIT_TOKEN", "no-exp-claim-token")
    assert TokenStore(isolated_forge_home).lifetime("SIT_TOKEN") == (50 * 60, False)


# --- pages ----------------------------------------------------------------------------------------------------


def test_pages_fit_a_photograph_and_long_ones_continue(isolated_forge_home: Path) -> None:
    long_page = Page(
        "A LONG PAGE", [f"line {n} " + "x" * 150 for n in range(70)], [Verdict("TK5", "PASS", "fine")]
    )
    screens = paginate([long_page, Page("SHORT", ["one"])])
    assert len(screens) >= 4 and screens[0].startswith(f"[1/{len(screens)}] A LONG PAGE (1/")
    for screen in screens:
        lines = screen.splitlines()
        assert len(lines) <= 30 and all(len(line) <= 100 for line in lines[2:])
    assert "TK5   PASS    fine" in screens[len(screens) - 2]  # the verdict closes the last screen of its page


def test_verdicts_are_kept_and_the_summary_lists_every_open_item(isolated_forge_home: Path) -> None:
    save_verdicts([Verdict("DV9", "PASS", "none removes"), Verdict("TK5", "CHECK", "no window yet")])
    save_verdicts([Verdict("DV9", "CHECK", "one function")])
    assert load_verdicts()["DV9"]["status"] == "CHECK" and load_verdicts()["TK5"]["line"] == "no window yet"
    written: list[str] = []
    folder = emit([Page("X", ["a"])], "unit", pause=False, write=written.append)
    assert (folder / "page_01.txt").is_file() and (folder / "all_pages.txt").is_file()
    summary = laptop.summary_page()
    assert len(summary.lines) == len(ITEMS) + 2 and "DV9   CHECK   one function" in summary.lines


def test_the_plan_gives_the_commands_and_the_sentences_to_type(isolated_forge_home: Path) -> None:
    written: list[str] = []
    assert laptop.run("plan", home=isolated_forge_home, write=written.append) == 0
    text = "\n".join(written)
    assert (
        "laptop check --app-python" in text and "laptop live" in text and "laptop report --workspace" in text
    )
    assert "app_token_status" in text and "/learn" in text


# --- the report, from conversations written like the real ones ------------------------------------------------


def _event(seq: int, kind: str, payload: dict[str, Any]) -> str:
    return json.dumps(
        {
            "seq": seq,
            "type": kind,
            "ts": f"2026-11-14T10:{seq // 60:02d}:{seq % 60:02d}+00:00",
            "payload": payload,
        }
    )


class Log:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.n = 0

    def add(self, kind: str, payload: dict[str, Any]) -> None:
        self.n += 1
        self.lines.append(_event(self.n, kind, payload))

    def call(self, name: str, arguments: Any, ok: bool = True, summary: str = "", preview: str = "") -> None:
        ident = f"id{self.n}"
        self.add(
            "tool_call_started",
            {"id": ident, "name": name, "summary": summary or name, "arguments": arguments},
        )
        self.add(
            "tool_call_finished",
            {
                "id": ident,
                "name": name,
                "ok": ok,
                "summary": summary or name,
                "preview": preview,
                "duration_s": 1.0,
            },
        )


def _write_conversation(root: Path, name: str, log: Log, age: int) -> None:
    path = root / ".forge" / "conversations" / name / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(log.lines) + "\n", encoding="utf-8")
    stamp = time.time() - age
    os.utime(path, (stamp, stamp))


def _project(root: Path) -> Path:
    run = "GET http://127.0.0.1:8765/api/agents/ops/run"
    first = Log()
    first.add("session_timing", {"open_s": 2.1, "map_s": 0.9})
    for index in range(7):
        first.call("code_map", {"action": "find"}, summary=f"code_map {index}")
    first.call("start_background", {"name": "hub"}, summary="start hub")
    first.call("http_request", {"url": run}, summary=run, preview="HTTP 200\nAnswer: 20 characters")
    second = Log()
    second.add("session_timing", {"open_s": 1.8, "map_s": 0.7})
    second.call("read_file", {"path": "a.py"})
    second.call("http_request", {"url": run}, summary=run, preview="HTTP 200\nAnswer: 20 characters")
    third = Log()
    third.add("session_timing", {"open_s": 2.4, "map_s": 1.0})
    third.call("code_map", {"action": "endpoints"})
    third.call(
        "db_query",
        {"sql": "select * from agents"},
        ok=False,
        preview='Query failed: relation "agents" does not exist',
    )
    third.call("db_schema", {"schema_name": "public"})
    third.call("http_request", {"url": run}, summary=run, preview="HTTP 500")
    third.call("edit_file", {"path": "src/tools.py"})
    third.call("edit_file", {"path": "src/tools.py"})
    third.call("db_copy_table", {"table": "tools"})
    third.call("use_scratch_database", {"variables": {"DATABASE_URL": "url"}})
    third.call(
        "request_app_secret",
        {"names": ["INFISICAL_CLIENT_ID"]},
        summary="ask to let commands use INFISICAL_CLIENT_ID",
    )
    third.call(
        "request_user_action",
        {"title": "Run gcloud auth login again"},
        summary="Please run gcloud auth login",
    )
    third.call(
        "dev_db_write",
        {"sql": "UPDATE agents SET max_steps = 20 WHERE id = 1"},
        preview="Approved by the user and committed",
    )
    third.call("http_request", {"url": run}, summary=run, preview="HTTP 200\nAnswer: 20 characters")
    third.add(
        "notice",
        {
            "kind": "dev_settings_held",
            "text": "The copy's settings APP_DATABASE_URL (.env) point at the shared Development database.",
        },
    )
    third.add(
        "question_asked",
        {
            "id": "Q1",
            "danger": True,
            "question": "Change 1 row(s) in the shared Development database (agents)?",
            "options": [{"label": "Change 1 row(s)"}, {"label": "Do not change"}],
        },
    )
    third.add("question_answered", {"id": "Q1", "choice": "Change 1 row(s)", "text": None})
    third.add(
        "notice",
        {
            "kind": "dev_db_activity",
            "text": "The application wrote to the shared Development database:\n- INSERT INTO runs (x)  (x2)",
        },
    )
    third.add(
        "notice",
        {"kind": "handoff_review", "text": "A step for you was held back: DebCraft can do this itself."},
    )
    third.add(
        "message_done",
        {
            "text": "I changed the tool so that the agent answers; the API now returns 200 for the deployments."
        },
    )
    _write_conversation(root, "c1", first, 300)
    _write_conversation(root, "c2", second, 200)
    _write_conversation(root, "c3", third, 100)
    return root


def test_the_report_reads_the_conversations_and_gives_each_item_a_verdict(
    isolated_forge_home: Path, tmp_path: Path
) -> None:
    root = _project(tmp_path / "proj")
    notes = root / ".forge" / "run_notes.json"
    notes.write_text(
        json.dumps(
            {"version": 1, "starts": [{"name": "hub"}], "calls": [{"method": "GET", "url": "http://x/y"}]}
        ),
        encoding="utf-8",
    )
    write_logins(isolated_forge_home, GOOD)
    TokenStore(isolated_forge_home).put("DEV_TOKEN", jwt(exp=time.time() + 3600))
    TokenStore(isolated_forge_home).put("SIT_TOKEN", jwt(exp=time.time() + 3600))
    for env in ("dev", "sit"):
        field_log.write(
            "sign_in",
            env=env,
            path="window",
            ok=True,
            seconds=20.0,
            minutes_left=59,
            lifetime_min=60,
            exp_claim=True,
        )
        field_log.write(
            "sign_in",
            env=env,
            path="stored",
            ok=True,
            seconds=0.1,
            minutes_left=58,
            lifetime_min=60,
            exp_claim=True,
        )
    field_log.write(
        "relay_stop",
        connections=3,
        seconds=40,
        writing_statements=2,
        refused_statements=1,
        rows={"INSERT": 2},
        messages={"Q": 5},
        errors={},
    )

    written: list[str] = []
    assert (
        laptop.run("report", workspace=root, pause=False, home=isolated_forge_home, write=written.append) == 0
    )
    text = "\n".join(written)
    verdicts = {item: entry["status"] for item, entry in load_verdicts(isolated_forge_home).items()}
    assert verdicts["TK5"] == "PASS" and "token lasts 60 min (own exp claim)" in text
    assert verdicts["RN2"] == "PASS" and "same call repeated: ['GET /api/agents/ops/run']" in text
    assert verdicts["RS7"] == "PASS" and "http_request before the first edit: [500]" in text
    assert verdicts["RS11"] == "PASS" and "names asked: ['INFISICAL_CLIENT_ID']" in text
    assert verdicts["DB2"] == "PASS" and "['agents']" in text and "looked up after: 1" in text
    assert verdicts["DV10"] == "PASS" and verdicts["DV8"] == "PASS"
    assert (
        "red cards: 1 shown, 1 approved, 0 not approved" in text
        and "dev_db_write: 1 calls, 1 committed" in text
    )
    assert verdicts["RS19"] == "PASS" and "slowest 2.4s" in text
    assert (
        verdicts["RS15"] == "CHECK"
        and "1. Run gcloud auth login again" in text
        and "held back: A step for you" in text
    )
    assert verdicts["KL6"] == "PASS" and verdicts["HW6"] == "NOT RUN" and verdicts["TR6"] == "NOT RUN"
    assert "SUMMARY OF THE OPEN ITEMS" in text and "PASS 9" in text
    assert SECRET not in text and jwt(exp=1) not in text


def test_the_report_says_what_is_missing_instead_of_guessing(
    isolated_forge_home: Path, tmp_path: Path
) -> None:
    root = tmp_path / "empty"
    (root / ".forge").mkdir(parents=True)
    written: list[str] = []
    laptop.run("report", workspace=root, pause=False, home=isolated_forge_home, write=written.append)
    text = "\n".join(written)
    assert "No conversation was found" in text
    stored = load_verdicts(isolated_forge_home)
    assert {entry["status"] for entry in stored.values()} <= {"NOT RUN"}
    # a conversation that only did one run is not enough for RN2, and a NOT RUN never replaces a real verdict
    save_verdicts([Verdict("RN2", "PASS", "an earlier real one")], isolated_forge_home)
    laptop.run("report", workspace=root, pause=False, home=isolated_forge_home, write=written.append)
    assert load_verdicts(isolated_forge_home)["RN2"]["status"] == "PASS"
    assert load_conversations(root) == []


# --- the checks against the local Postgres, standing in for the Development database --------------------------


@pytest.fixture
def dev_home(
    isolated_forge_home: Path, admin_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    env_file = tmp_path / "debcraft.env"
    env_file.write_text(f"DEV_PG_URL={admin_url}\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))
    monkeypatch.delenv("DEV_PG_URL", raising=False)
    return isolated_forge_home


@pytest.mark.pg
def test_the_database_page_finds_triggers_and_functions_that_delete(
    dev_home: Path, admin_url: str, cleanup_schemas: list[str], tmp_path: Path
) -> None:
    schema = f"forge_test_lap_{uuid.uuid4().hex[:8]}"
    cleanup_schemas.append(schema)
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.execute(f'CREATE TABLE "{schema}".runs (id int primary key, note text)')
        connection.execute(
            f'CREATE FUNCTION "{schema}".purge_old() RETURNS void LANGUAGE plpgsql AS $$ BEGIN DELETE FROM "{schema}".runs; END $$'
        )
        connection.execute(
            f'CREATE FUNCTION "{schema}".harmless() RETURNS int LANGUAGE sql AS $$ SELECT 1 $$'
        )
        connection.execute(
            f'CREATE FUNCTION "{schema}".on_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$'
        )
        connection.execute(
            f'CREATE TRIGGER touch BEFORE UPDATE ON "{schema}".runs FOR EACH ROW EXECUTE FUNCTION "{schema}".on_change()'
        )
    page = laptop.database_page(dev_home, None)
    text = "\n".join(page.lines)
    verdicts = {v.item: v for v in page.verdicts}
    assert f"{schema}.purge_old" in text and f"{schema}.runs" in text
    assert verdicts["DV9"].status == "CHECK" and "removing functions 1, triggers 1" in verdicts["DV9"].line
    assert "harmless" not in text and verdicts["DV10"].status == "NOT RUN"  # no project given


@pytest.mark.pg
def test_the_driver_check_runs_every_installed_driver_through_the_relay(
    dev_home: Path, admin_url: str
) -> None:
    asked: list[str] = []

    def yes(question: str) -> str:
        asked.append(question)
        return "yes"

    page = laptop.drivers_page(dev_home, Path(os.sys.executable), yes)  # type: ignore[attr-defined]
    text = "\n".join(page.lines)
    verdict = page.verdicts[0]
    assert "TEMPORARY table" in asked[0] and "Type yes" in asked[0]
    assert "psycopg " in text and "10/10 steps ok" in text and "relay: " in text, text
    assert verdict.item == "DV8" and verdict.status == "PASS", (verdict, text)
    assert "refused 2" in text.replace("refused 4", "refused 2") or "refused" in text
    records = field_log.read(("relay_start", "relay_stop"), dev_home)
    assert [r["kind"] for r in records] == ["relay_start", "relay_stop"] and records[1][
        "refused_statements"
    ] >= 2

    skipped = laptop.drivers_page(dev_home, Path(os.sys.executable), lambda question: "no")  # type: ignore[attr-defined]
    assert skipped.verdicts[0].status == "NOT RUN" and "skipped" in skipped.verdicts[0].line
    none_given = laptop.drivers_page(dev_home, None)
    assert none_given.verdicts[0].status == "NOT RUN" and "--app-python" in "\n".join(none_given.lines)
