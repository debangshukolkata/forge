"""D-650: the export of candidates for general lessons: what is collected, what is hidden, and that it stays here."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.engine.learnings_export import build_export, corrections_in, masker, write_export
from forge.memory.store import MemoryStore

LOGINS = """environments:
  dev:
    login_url: https://dev.nonprod.acmewisdom.acmeapps.com/app/login/
    token_name: DEV_TOKEN
    token: {cookie: access_token}
    steps:
      - click: "Sign in"
"""


def event(event_type: str, /, **payload: object) -> str:
    return (
        json.dumps({"seq": 1, "ts": "2026-11-24T10:00:00+00:00", "type": event_type, "payload": payload})
        + "\n"
    )


@pytest.fixture
def home(tmp_path: Path) -> Path:
    base = tmp_path / "home"
    (base / "data").mkdir(parents=True)
    (base / "app_logins.yaml").write_text(LOGINS, encoding="utf-8")
    projects = []
    for name in ("video-playback", "argo-helper"):
        root = tmp_path / name
        folder = root / ".forge" / "conversations" / "c1"
        folder.mkdir(parents=True)
        (folder / "events.jsonl").write_text(
            event("user_message", text="Please build it. You should have told me about the local token.")
            + event("user_message", text='{"msg": "wrong", "never": 1}')
            + event(
                "tool_call_finished",
                name="db_copy_table",
                ok=False,
                preview="public.persona_master_data was not found",
            )
            + event(
                "tool_call_finished",
                name="db_copy_table",
                ok=False,
                preview="public.token_blocklist was not found",
            )
            + event("tool_call_finished", name="read_file", ok=True, preview="fine")
            + event("notice", kind="handover_check", text="x")
            + event("notice", kind="usage", text="x")
            + "not json at all user_message\n",
            encoding="utf-8",
        )
        projects.append(
            {"name": name, "path": str(root), "repo": r"C:\Work\LocalDevelopment\wnxtv35-biz-exec"}
        )
    (base / "data" / "recent_workspaces.json").write_text(json.dumps(projects), encoding="utf-8")
    MemoryStore(base).save(
        "say-the-token", "Say which token a curl needs", "feedback", "Ask Acmewisdom first."
    )
    MemoryStore(base).save("tables", "The users table", "project", "video_transcript_details holds the text")
    MemoryStore(base, "repo:x").save("slow", "Do not start the app ten times", "feedback", "It wastes time.")
    return base


def test_it_collects_feedback_corrections_repeated_failures_and_checks(home: Path) -> None:
    text = build_export(home)
    assert "Say which token a curl needs" in text and "Do not start the app ten times" in text
    assert "2x You should have told me about the local token." in text
    assert "4x in 2 project(s), db_copy_table:" in text
    assert "2x handover_check" in text and "usage" not in text
    assert (
        "The users table" not in text and "Please build it" not in text
    )  # a fact of a repository, an instruction


def test_names_addresses_and_paths_are_hidden(home: Path) -> None:
    (home / "private_terms.txt").write_text("# mine\nProject Falcon\n", encoding="utf-8")
    mask = masker(
        home, [{"name": "video-playback", "path": r"C:\Work\x", "repo": r"C:\Work\wnxtv35-biz-exec"}]
    )
    text = mask(
        "See https://dev.nonprod.acmewisdom.acmeapps.com/api and mail a.b@acme.com, host db.acme.internal.net, 10.1.2.3, "
        r"C:\Users\211258\x.py, core_features/video_chat/x.py, main.py, video_transcript_details, VideoAgentService, "
        "videoId, wnxtv35, WisdomNext at AcmeWisdom, Project Falcon, 449d2edf-0ca1-4b1c-9d2e-123456789abc, 211258, "
        "then call http_request on http://127.0.0.1:5045/x"
    )
    for secret in (
        "acme", "211258", "core_features", "main.py", "transcript", "VideoAgent", "videoId", "wnxtv35", "Falcon",
        "449d2edf", "10.1.2.3", "5045",
    ):  # fmt: skip
        assert secret.lower() not in text.lower(), (secret, text)
    assert "http_request" in text and "<local address>" in text  # what makes the lesson readable stays


def test_only_sentences_that_correct_are_taken() -> None:
    assert corrections_in("Do not use the local token. Thanks!") == ["Do not use the local token."]
    assert corrections_in("Build three endpoints. Make them simple.") == []
    assert corrections_in('{"error": "wrong"}') == [] and corrections_in("wrong") == []


def test_the_export_is_one_local_file_that_says_to_read_it_first(home: Path) -> None:
    target = write_export(home)
    assert target.parent == home / "reports"
    assert "READ THIS BEFORE YOU SEND IT" in target.read_text(encoding="utf-8")
    source = Path("src/forge/engine/learnings_export.py")
    code = (Path(__file__).resolve().parent.parent / source).read_text(encoding="utf-8")
    assert "httpx" not in code and "router" not in code  # no network and no model sees it


def test_an_empty_home_gives_an_empty_list(tmp_path: Path) -> None:
    assert build_export(tmp_path).count("none") >= 4


def test_the_full_export_keeps_names_and_masks_keys(home: Path) -> None:
    key = "sk-" + "a1B2" * 12  # check_secrets: fake
    folder = home / "memory" / "scopes" / "repo-x" / "knowledge" / "topics"
    folder.mkdir(parents=True)
    (folder / "video.md").write_text(f"The endpoint /video-agent/index uses {key}", encoding="utf-8")
    text = build_export(home, full=True)
    assert "public.persona_master_data" in text and "The users table" in text and "/video-agent/index" in text
    assert key not in text and "READ THIS BEFORE YOU SEND" not in text
    assert write_export(home, full=True).name.startswith("learnings-full-")
