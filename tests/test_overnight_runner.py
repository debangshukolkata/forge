"""The overnight kit (scripts/overnight): the runner stops a stalled or slow job and goes on, writes a failure report, resumes; the task checks accept a correct solution and refuse a wrong one."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "overnight"
sys.path.insert(0, str(SCRIPTS))
import run_overnight  # noqa: E402
import verify_tasks  # noqa: E402
from jobs import Ctx, Job, catalogue  # noqa: E402
from make_signature_sample import make as make_sample  # noqa: E402
from report import write_report  # noqa: E402

REPO = SCRIPTS.parents[1]


def job(job_id: str, code: str, **kw: object) -> Job:
    return Job(
        id=job_id,
        title=f"test job {job_id}",
        group="test",
        est_min=1,
        timeout_min=int(kw.pop("timeout_min", 1)),
        argv=lambda ctx: [sys.executable, "-u", "-c", code],
        **kw,
    )  # type: ignore[arg-type]


@pytest.fixture
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_overnight, "POLL_S", 0.2)


def run_one(tmp_path: Path, spec: Job, limit_s: float = 30) -> dict[str, object]:
    ctx = Ctx(repo=REPO, out=tmp_path, env_file="")
    entry: dict[str, object] = {"id": spec.id}
    run_overnight.run_job(spec, ctx, __import__("time").time() + limit_s, entry, lambda: None)
    return entry


def test_a_job_that_finishes_passes(tmp_path: Path, fast: None) -> None:
    entry = run_one(tmp_path, job("ok", "print('hello')"))
    assert entry["status"] == "PASS" and "hello" in (tmp_path / "jobs" / "ok" / "console.log").read_text(
        encoding="utf-8"
    )
    assert not (tmp_path / "jobs" / "ok" / "failure.md").exists()


def test_a_job_that_fails_leaves_a_failure_report(tmp_path: Path, fast: None) -> None:
    entry = run_one(tmp_path, job("bad", "import sys; print('about to fail'); sys.exit(3)"))
    assert entry["status"] == "FAILED" and entry["exit_code"] == 3
    failure = (tmp_path / "jobs" / "bad" / "failure.md").read_text(encoding="utf-8")
    assert "about to fail" in failure and "exit code 3" in failure and "Command:" in failure


def test_a_job_that_goes_quiet_is_stopped_as_stalled_and_the_night_goes_on(
    tmp_path: Path, fast: None
) -> None:
    spec = job(
        "quiet", "import time; print('started', flush=True); time.sleep(600)", stall_min=0.02
    )  # 1.2 seconds without a change
    entry = run_one(tmp_path, spec)
    assert entry["status"] == "STALLED" and "nothing changed" in str(entry["finding"])
    assert "STALLED" in (tmp_path / "jobs" / "quiet" / "failure.md").read_text(encoding="utf-8")
    follow = run_one(tmp_path, job("after", "print('still running the night')"))
    assert follow["status"] == "PASS"


def test_a_job_over_its_time_limit_is_stopped_as_timeout(tmp_path: Path, fast: None) -> None:
    spec = job(
        "slow", "import time\nwhile True:\n    print('tick', flush=True); time.sleep(0.1)", timeout_min=0.03
    )  # 1.8 seconds, output keeps changing
    entry = run_one(tmp_path, spec)
    assert entry["status"] == "TIMEOUT"


def test_the_night_budget_ends_a_running_job(tmp_path: Path, fast: None) -> None:
    spec = job(
        "budget", "import time\nwhile True:\n    print('tick', flush=True); time.sleep(0.1)", timeout_min=60
    )
    ctx = Ctx(repo=REPO, out=tmp_path, env_file="")
    entry: dict[str, object] = {"id": "budget"}
    run_overnight.run_job(
        spec, ctx, __import__("time").time() + 1.0, entry, lambda: None
    )  # run_job never gives a job less than 60 s: the floor protects a job that just started
    assert entry["status"] in ("TIMEOUT", "PASS", "FAILED")


def test_a_pytest_job_is_judged_by_its_summary(tmp_path: Path) -> None:
    console = tmp_path / "jobs" / "t"
    console.mkdir(parents=True)
    (console / "console.log").write_text(
        "FAILED tests/test_x.py::test_a - assert 1 == 2\n1 failed, 4 passed in 1.2s\n", encoding="utf-8"
    )
    spec = Job(id="t", title="t", group="tests", est_min=1, timeout_min=1, argv=lambda ctx: [], kind="pytest")
    status, finding, details = run_overnight.analyse(
        spec, 1, "done", console, Ctx(repo=REPO, out=tmp_path, env_file="")
    )
    assert (
        status == "PROBLEMS"
        and "1 failed, 4 passed" in finding
        and details[0].startswith("FAILED tests/test_x.py")
    )


def test_without_xdist_the_parallel_flags_are_dropped() -> None:
    assert run_overnight.strip_xdist(
        ["-m", "pytest", "-q", "-n", "4", "--dist", "loadfile", "-m", "not live"]
    ) == ["-m", "pytest", "-q", "-m", "not live"]


def test_the_report_names_what_to_send_back(tmp_path: Path) -> None:
    (tmp_path / "jobs" / "bad").mkdir(parents=True)
    (tmp_path / "jobs" / "bad" / "failure.md").write_text(
        "# bad\nsomething broke api_key=sk-abc123456789", encoding="utf-8"
    )
    state = {
        "started": "now",
        "profile": "core",
        "finished": True,
        "environment": "x",
        "jobs": [
            {"id": "ok", "title": "Good", "status": "PASS", "seconds": 5, "finding": "fine", "evidence": []},
            {
                "id": "bad",
                "title": "Bad one",
                "status": "FAILED",
                "seconds": 9,
                "finding": "boom",
                "evidence": ["00-shot.png"],
            },
        ],
    }
    write_report(tmp_path, state)
    text = (tmp_path / "MORNING_REPORT.md").read_text(encoding="utf-8")
    assert (
        "jobs/bad/failure.md" in text
        and "jobs/bad/evidence/00-shot.png" in text
        and "1 failed" in text
        and "1 pass" in text
    )
    page = (tmp_path / "MORNING_REPORT.html").read_text(encoding="utf-8")
    assert "Bad one" in page and "sk-abc123456789" not in page  # secrets never reach the report


def test_the_catalogue_is_complete_and_every_task_has_a_prompt_and_a_verifier() -> None:
    jobs = catalogue()
    assert len({j.id for j in jobs}) == len(jobs)
    for j in jobs:
        assert j.est_min > 0 and j.timeout_min >= j.est_min and j.tier in (1, 2)
    folder = REPO / "tests" / "benchmarks" / "overnight"
    for path in folder.glob("*/task.json"):
        task = json.loads(path.read_text(encoding="utf-8"))
        assert (path.parent / "prompt.md").is_file() and task["verify"] in verify_tasks.VERIFIERS, task["id"]
    core = sum(j.est_min for j in jobs if j.tier == 1)
    assert 300 <= core <= 720, f"the core night is {core} minutes: it should fit a night"


def test_a_dry_run_lists_the_plan_without_running_anything(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_overnight.main(["--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert (
        "tests_fast" in printed and "task_invoice_app" in printed and "hours if nothing is skipped" in printed
    )


# --- the checks of the tasks -----------------------------------------------------------------------------------------------------

LOGSTATS = """
import re, sys
from collections import Counter
text = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
pattern = re.compile(r'^(\\S+) \\S+ \\S+ \\[([^\\]]+)\\] "(\\S+) (\\S+) [^"]*" (\\d{3}) (\\d+|-)$')
paths, statuses, sizes, minutes, bad = Counter(), Counter(), [], Counter(), 0
for line in text.splitlines():
    if not line.strip():
        continue
    m = pattern.match(line)
    if not m:
        bad += 1
        continue
    paths[m.group(4)] += 1; statuses[m.group(5)] += 1
    sizes.append(0 if m.group(6) == "-" else int(m.group(6))); minutes[m.group(2)[:17]] += 1
sizes.sort()
p95 = sizes[max(0, -(-95 * len(sizes) // 100) - 1)]
print(f"Total requests: {sum(paths.values())}"); print(f"Malformed lines: {bad}")
print("Top paths:"); [print(f"  {p} {c}") for p, c in paths.most_common(5)]
print("Status codes:"); [print(f"  {s} {c}") for s, c in sorted(statuses.items())]
print(f"95th percentile size: {p95}")
minute, count = minutes.most_common(1)[0]; print(f"Busiest minute: {minute} ({count} requests)")
"""


def workspace_with(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        target = tmp_path / "project" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


def test_the_logstats_check_accepts_a_correct_tool_and_refuses_a_wrong_one(tmp_path: Path) -> None:
    good = workspace_with(tmp_path / "good", {"logstats.py": LOGSTATS})
    result = verify_tasks.verify({"verify": "logstats"}, good, tmp_path / "good-run", REPO)
    failed = [c["name"] for c in result["checks"] if not c["ok"]]
    assert failed == ["the project's own tests pass"], (
        failed
    )  # the tool is right; this workspace has no tests
    wrong = workspace_with(tmp_path / "wrong", {"logstats.py": "print('Total requests: 7')"})
    bad = verify_tasks.verify({"verify": "logstats"}, wrong, tmp_path / "wrong-run", REPO)
    assert bad["passed"] < bad["total"] - 3


def test_the_bugfix_check_notices_edited_tests_and_a_wrong_fix(tmp_path: Path) -> None:
    seed = REPO / "tests" / "benchmarks" / "overnight" / "bugfix" / "seed"
    shutil.copytree(seed, tmp_path / "project")
    result = verify_tasks.verify({"verify": "bugfix"}, tmp_path, tmp_path / "run", REPO)
    assert (
        result["checks"][0]["ok"] and not result["checks"][1]["ok"]
    )  # untouched tests, the seeded bugs still fail them
    (tmp_path / "project" / "tests" / "test_pricing.py").write_text(
        "def test_nothing():\n    assert True\n", encoding="utf-8"
    )
    cheated = verify_tasks.verify({"verify": "bugfix"}, tmp_path, tmp_path / "run2", REPO)
    assert not cheated["checks"][0]["ok"]


SIGNATURE_TOOL = """
import sys
from PIL import Image
image = Image.open(sys.argv[1]).convert("RGB")
w, h = image.size
box = (w // 2, int(h * 0.68), w, h)
region = image.crop(box)
out = Image.new("RGBA", region.size, (0, 0, 0, 0))
px, src = out.load(), region.load()
xs, ys = [], []
for y in range(region.size[1]):
    for x in range(region.size[0]):
        r, g, b = src[x, y]
        if b > r + 40 and b > g + 40:
            px[x, y] = (r, g, b, 255); xs.append(x); ys.append(y)
out.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1)).save(sys.argv[2])
"""


def test_the_signature_check_scores_a_good_crop_and_a_fragment(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    good = workspace_with(tmp_path / "good", {"extract_signature.py": SIGNATURE_TOOL})
    result = verify_tasks.verify({"verify": "sigcrop"}, good, tmp_path / "good-run", REPO)
    failed = [c["name"] for c in result["checks"] if not c["ok"]]
    assert failed == ["the project's own tests pass"], failed
    fragment = SIGNATURE_TOOL.replace(
        "out.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))",
        "out.crop((min(xs), min(ys), min(xs) + 20, min(ys) + 22))",
    )
    bad = verify_tasks.verify(
        {"verify": "sigcrop"},
        workspace_with(tmp_path / "bad", {"extract_signature.py": fragment}),
        tmp_path / "bad-run",
        REPO,
    )
    assert any("right amount" in c["name"] and not c["ok"] for c in bad["checks"])


def test_the_synthetic_prescription_has_a_known_signature(tmp_path: Path) -> None:
    truth = make_sample(tmp_path, 7)
    assert (
        (tmp_path / "prescription.jpg").is_file()
        and 100 < truth["width"] < 260
        and truth["ink_pixels"] > 1000
    )


def test_the_research_check_wants_sources_and_honesty(tmp_path: Path) -> None:
    sources = "\n".join(f"- https://example.org/page{n}" for n in range(6))
    report = (
        "Tesseract is the usual choice. " * 60
        + "I recommend it.\nI could not confirm the licence of one engine.\n"
        + sources
    )
    result = verify_tasks.verify(
        {"verify": "research"}, workspace_with(tmp_path, {"report.md": report}), tmp_path / "run", REPO
    )
    assert result["passed"] == result["total"]
    thin = verify_tasks.verify(
        {"verify": "research"},
        workspace_with(tmp_path / "thin", {"report.md": "Tesseract."}),
        tmp_path / "run2",
        REPO,
    )
    assert thin["passed"] < thin["total"]


def test_python_is_launchable_for_the_helpers() -> None:
    assert (
        subprocess.run(
            [sys.executable, str(SCRIPTS / "make_signature_sample.py"), "--help"],
            capture_output=True,
            timeout=60,
        ).returncode
        == 0
    )


def test_test_jobs_do_not_get_the_env_file_override_except_the_live_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fast: None
) -> None:
    """The first night failed two DebCraft tests only because FORGE_ENV_FILE replaced the tests' isolated home (D-443)."""
    seen: dict[str, str] = {}
    code = "import os, json; print(json.dumps({'env_file': os.environ.get('FORGE_ENV_FILE', ''), 'ci': os.environ.get('CI', '')}))"
    for job_id in ("tests_fast", "tests_live", "smoke_gemini"):
        spec = next(j for j in catalogue() if j.id == job_id)
        spec.argv = lambda ctx: [sys.executable, "-c", code]
        ctx = Ctx(repo=REPO, out=tmp_path / job_id, env_file="C:/x/.env")
        run_overnight.run_job(spec, ctx, __import__("time").time() + 60, {"id": job_id}, lambda: None)
        seen[job_id] = (ctx.out / "jobs" / job_id / "console.log").read_text(encoding="utf-8")
    assert '"env_file": ""' in seen["tests_fast"] and '"ci": ""' in seen["tests_fast"]
    assert "C:/x/.env" in seen["tests_live"]
    assert "C:/x/.env" in seen["smoke_gemini"]


def test_retry_runs_again_what_did_not_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--retry in an old folder keeps the jobs that passed and runs the rest again (the second night after a fix)."""
    ran: list[str] = []

    def fake_run_job(spec: Job, ctx: Ctx, deadline: float, entry: dict[str, object], save: object) -> None:
        ran.append(spec.id)
        entry.update(status="PASS", seconds=1, finding="ok", evidence=[])

    monkeypatch.setattr(run_overnight, "run_job", fake_run_job)
    monkeypatch.setattr(
        run_overnight,
        "preflight",
        lambda ctx: ({"pytest": True, "azure": True, "node": True, "edge": True, "xdist": True}, "env"),
    )
    states = [
        {
            "id": "preflight",
            "title": "p",
            "group": "p",
            "status": "PASS",
            "seconds": 1,
            "finding": "",
            "evidence": [],
        }
    ]
    states += [
        {
            "id": "bugfix_x",
            "title": "x",
            "group": "g",
            "status": "PASS",
            "seconds": 1,
            "finding": "",
            "evidence": [],
        }
    ]
    states += [
        {
            "id": "task_bugfix",
            "title": "b",
            "group": "g",
            "status": "TIMEOUT",
            "seconds": 1,
            "finding": "",
            "evidence": [],
        }
    ]
    (tmp_path / "state.json").write_text(
        json.dumps({"started": "x", "profile": "core", "finished": True, "jobs": states}), encoding="utf-8"
    )
    (tmp_path / "preflight.json").write_text(json.dumps({"caps": {"pytest": True}}), encoding="utf-8")
    assert (
        run_overnight.main(
            ["--out", str(tmp_path), "--env-file", "", "--only", "task_bugfix", "--retry", "--max-hours", "1"]
        )
        == 0
    )
    assert ran == ["task_bugfix"]


def test_stop_now_ends_the_running_job_without_a_failure_report(tmp_path: Path, fast: None) -> None:
    """Pause-Overnight-Now.cmd writes STOP_NOW: the job stops, is marked INTERRUPTED and is not a failure."""
    import threading
    import time

    spec = job(
        "long", "import time\nwhile True:\n    print('tick', flush=True); time.sleep(0.1)", timeout_min=60
    )
    threading.Timer(1.5, lambda: (tmp_path / "STOP_NOW").write_text("stop")).start()
    started = time.time()
    entry = run_one(tmp_path, spec, 120)
    assert entry["status"] == "INTERRUPTED" and time.time() - started < 30
    assert not (tmp_path / "jobs" / "long" / "failure.md").exists()


def test_a_pause_between_jobs_and_a_resume_continue_where_it_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The traveller's case: stop after one job, shut the laptop, start again with --out latest: only the rest runs."""
    ran: list[str] = []

    def fake_run_job(spec: Job, ctx: Ctx, deadline: float, entry: dict[str, object], save: object) -> None:
        ran.append(spec.id)
        entry.update(status="PASS", seconds=1, finding="ok", evidence=[])
        if len(ran) == 1:
            (ctx.out / "STOP").write_text("pause")  # Pause-Overnight.cmd, pressed while the first job ran

    monkeypatch.setattr(run_overnight, "run_job", fake_run_job)
    monkeypatch.setattr(
        run_overnight,
        "preflight",
        lambda ctx: ({"pytest": True, "azure": True, "node": True, "edge": True, "xdist": True}, "env"),
    )
    monkeypatch.setattr(run_overnight, "REPO", tmp_path)
    out = tmp_path / "overnight-results" / "20260101-0000"
    first = [
        "--out",
        str(out),
        "--env-file",
        "",
        "--only",
        "tests_fast,task_bugfix,task_logstats",
        "--max-hours",
        "1",
    ]
    assert run_overnight.main(first) == 0
    assert ran == ["tests_fast"]
    state = json.loads((out / "state.json").read_text(encoding="utf-8"))
    assert state["finished"] is False and [j["status"] for j in state["jobs"]][-2:] == ["PENDING", "PENDING"]
    assert "Not finished" in (out / "MORNING_REPORT.md").read_text(encoding="utf-8")
    assert (
        run_overnight.main(
            [
                "--out",
                "latest",
                "--env-file",
                "",
                "--only",
                "tests_fast,task_bugfix,task_logstats",
                "--max-hours",
                "1",
            ]
        )
        == 0
    )
    assert ran == [
        "tests_fast",
        "task_bugfix",
        "task_logstats",
    ]  # the pause file was cleared at the start, the finished job was not run again
    assert json.loads((out / "state.json").read_text(encoding="utf-8"))["finished"] is True


def test_a_job_cut_short_by_a_shutdown_runs_again_from_its_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[str] = []

    def fake_run_job(spec: Job, ctx: Ctx, deadline: float, entry: dict[str, object], save: object) -> None:
        ran.append(spec.id)
        entry.update(status="PASS", seconds=1, finding="ok", evidence=[])

    monkeypatch.setattr(run_overnight, "run_job", fake_run_job)
    monkeypatch.setattr(
        run_overnight, "preflight", lambda ctx: ({"pytest": True, "azure": True, "xdist": True}, "env")
    )
    base = {"title": "t", "group": "g", "seconds": 0, "finding": "", "evidence": []}
    states = [
        {"id": "preflight", "status": "PASS", **base},
        {"id": "task_bugfix", "status": "RUNNING", **base},
    ]  # the laptop was switched off while it ran
    (tmp_path / "state.json").write_text(
        json.dumps({"started": "x", "profile": "core", "finished": False, "jobs": states}), encoding="utf-8"
    )
    (tmp_path / "preflight.json").write_text(json.dumps({"caps": {"pytest": True}}), encoding="utf-8")
    (tmp_path / ".lock").write_text("999999")  # the dead process of the night before
    assert (
        run_overnight.main(
            ["--out", str(tmp_path), "--env-file", "", "--only", "task_bugfix", "--max-hours", "1"]
        )
        == 0
    )
    assert ran == ["task_bugfix"]


def test_remove_tree_deletes_read_only_files(tmp_path: Path) -> None:
    # The old `rmtree(..., ignore_errors=True)` left such a folder behind and the job's second run refused to start (D-450).
    import stat
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "overnight"))
    from fsutil import remove_tree

    folder = tmp_path / "ws" / ".forge" / "objects"
    folder.mkdir(parents=True)
    locked = folder / "pack.idx"
    locked.write_text("x", encoding="utf-8")
    locked.chmod(stat.S_IREAD)
    remove_tree(tmp_path / "ws")
    assert not (tmp_path / "ws").exists()
