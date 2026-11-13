"""D-607: `forge facts` prints three short screens with the facts that close the open items, never a secret."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from forge.engine.facts_report import build_pages, newest_workspace, show
from forge.toolkit.app_logins import TokenStore

SECRET = "tok-" + "a1b2c3d4e5" * 4  # check_secrets: fake


def event(seq: int, kind: str, payload: dict[str, object]) -> str:
    return json.dumps({"seq": seq, "type": kind, "ts": "2026-11-13T10:00:00+00:00", "payload": payload})


def project(root: Path) -> Path:
    log = root / ".forge" / "transcripts" / "events.jsonl"
    log.parent.mkdir(parents=True)
    tool = lambda n, name, ok, summary, preview="": event(  # noqa: E731
        n,
        "tool_call_finished",
        {"name": name, "ok": ok, "summary": summary, "preview": preview, "duration_s": 1.0},
    )
    lines = [
        event(1, "session_timing", {"open_s": 4.5, "map_s": 1.2}),
        tool(2, "db_query", False, "select 1", "Error: relation guessed_table does not exist"),
        tool(3, "db_query", True, "select 2"),
        tool(4, "app_login", True, "sign in to dev"),
        tool(5, "http_request", True, "GET https://dev.example.com/api/me?token=" + SECRET),
        tool(6, "request_user_action", True, "Please run gcloud auth login"),
        event(7, "notice", {"kind": "token_warning", "text": "No valid DEV_TOKEN for dev."}),
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def test_the_three_pages_carry_the_facts_and_no_secret(isolated_forge_home: Path, tmp_path: Path) -> None:
    (isolated_forge_home / "app_logins.yaml").write_text(
        yaml.safe_dump(
            {
                "environments": {
                    "dev": {
                        "login_url": "https://dev.example.com/app/login/",
                        "token_name": "DEV_TOKEN",
                        "token": {"cookie": "c"},
                        "warn_without_token": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    TokenStore(isolated_forge_home).put("DEV_TOKEN", SECRET)
    pages = build_pages(project(tmp_path / "proj"))
    text = "\n".join(pages)

    assert len(pages) == 3 and SECRET not in text
    assert "DEV_TOKEN = VALID" in pages[0] and "tunnels.yaml: NO" in pages[0]
    assert "opening the project: 1 x, median 4.5s" in pages[1]
    assert "db_query: 2 calls, 1 failed, 1 on a name that does not exist" in pages[1]
    assert "app_login: 1 calls, 0 failed" in pages[1] and "dev.example.com x1" in pages[1]
    assert "cards shown to the user: 1" in pages[2] and "token_warning: No valid DEV_TOKEN" in pages[2]


def test_the_newest_project_is_found_and_the_pages_pause_between_screens(
    isolated_forge_home: Path, tmp_path: Path
) -> None:
    root = project(tmp_path / "proj")
    (isolated_forge_home / "recent_workspaces.json").write_text(
        json.dumps([{"path": str(root)}]), encoding="utf-8"
    )
    assert newest_workspace() == root
    printed: list[str] = []
    waits: list[str] = []
    assert show(None, write=printed.append, wait=lambda prompt: waits.append(prompt) or "") == 0
    assert len(printed) == 3 and len(waits) == 2 and "PAGE 1 of 3" in printed[0]


def test_without_a_conversation_the_setup_page_still_prints(isolated_forge_home: Path) -> None:
    pages = build_pages(None)
    assert "PAGE 1 of 3" in pages[0] and "no conversation found" in pages[1]
