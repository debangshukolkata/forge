"""Checks of what Forge delivered for the overnight tasks. Each verifier returns {"checks": [{"name", "ok", "detail"}], "evidence": [paths]}: the checks are plain pass or fail with a
reason a person can read in the morning, and the evidence is pictures and files worth looking at when a check failed. Nothing here calls a model."""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_signature_sample import make as make_signature_sample  # noqa: E402

Check = dict[str, Any]


def check(name: str, ok: bool, detail: str = "") -> Check:
    return {"name": name, "ok": bool(ok), "detail": detail[:600]}


def project_python(workspace: Path) -> str:
    """The python of the workspace's own environment when Forge made one, else the one running this script."""
    for candidate in (workspace / ".venv" / "Scripts" / "python.exe", workspace / ".venv" / "bin" / "python"):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def run(
    command: list[str], cwd: Path, timeout: int = 300, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        input=stdin,
    )


def find_file(workspace: Path, name: str) -> Path | None:
    for folder in (workspace / "project", workspace / "output", workspace):
        for path in sorted(folder.rglob(name)):
            if not {".venv", "node_modules", ".git", "__pycache__"} & set(path.parts):
                return path
    return None


def project_tests(workspace: Path, label: str = "the project's own tests pass") -> Check:
    project = workspace / "project"
    if not project.is_dir():
        return check(label, False, "no project folder")
    try:
        done = run(
            [project_python(workspace), "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], project, 600
        )
    except subprocess.TimeoutExpired:
        return check(label, False, "pytest took longer than 10 minutes")
    tail = (done.stdout + done.stderr).strip().splitlines()[-3:]
    return check(label, done.returncode == 0, " | ".join(tail))


# --- bug fix -------------------------------------------------------------------------------------------------------------------


def verify_bugfix(workspace: Path, run_dir: Path, task: dict[str, Any], repo: Path) -> dict[str, Any]:
    seed = repo / "tests" / "benchmarks" / "overnight" / "bugfix" / "seed" / "tests" / "test_pricing.py"
    delivered = workspace / "project" / "tests" / "test_pricing.py"
    same = (
        delivered.is_file()
        and hashlib.sha256(delivered.read_bytes()).hexdigest()
        == hashlib.sha256(seed.read_bytes()).hexdigest()
    )
    checks = [
        check(
            "the tests were not edited", same, "the test file differs from the original" if not same else ""
        )
    ]
    checks.append(project_tests(workspace, "all 6 tests pass"))
    return {"checks": checks, "evidence": []}


# --- log analyser --------------------------------------------------------------------------------------------------------------


def make_log() -> str:
    """24 valid lines: /home 9, /api/items 6, /about 4, /login 3, /x 2; statuses 200 x18, 404 x4, 500 x2; sizes 0 (a dash) and 100..2300; 10 of them in minute 13:55; 3 malformed."""
    paths = ["/home"] * 9 + ["/api/items"] * 6 + ["/about"] * 4 + ["/login"] * 3 + ["/x"] * 2
    statuses = [200] * 18 + [404] * 4 + [500] * 2
    sizes = ["-"] + [str(100 * k) for k in range(1, 24)]
    lines = []
    for index in range(24):
        minute = 55 if index < 10 else 56 + (index - 10) // 5
        lines.append(
            f'10.0.0.{index % 7 + 1} - - [10/Oct/2023:13:{minute:02d}:{index % 60:02d} +0000] "GET {paths[index]} HTTP/1.1" {statuses[index]} {sizes[index]}'
        )
    lines[5:5] = ["this is not a log line", "10.0.0.1 - - [bad date] GET /x"]
    lines.append('999.1 "broken')
    return "\n".join(lines) + "\n"


def verify_logstats(workspace: Path, run_dir: Path, task: dict[str, Any], repo: Path) -> dict[str, Any]:
    script = find_file(workspace, "logstats.py")
    checks = [check("logstats.py exists", script is not None)]
    if script is None:
        return {"checks": checks, "evidence": []}
    log = run_dir / "hidden.log"
    log.write_text(make_log(), encoding="utf-8")
    python = project_python(workspace)
    try:
        by_file = run([python, str(script), str(log)], script.parent, 60)
        by_stdin = run([python, str(script)], script.parent, 60, stdin=log.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired:
        return {
            "checks": [*checks, check("the tool answers within a minute", False, "timed out")],
            "evidence": [],
        }
    out = by_file.stdout
    (run_dir / "logstats_output.txt").write_text(out + "\n--- stderr\n" + by_file.stderr, encoding="utf-8")
    checks += [
        check(
            "runs without crashing on a file with malformed lines",
            by_file.returncode == 0,
            by_file.stderr[-300:],
        ),
        check("total requests 24", re.search(r"total[^\n]{0,40}\b24\b", out, re.I) is not None, out[:200]),
        check("3 malformed lines reported", re.search(r"malformed[^\n]{0,40}\b3\b", out, re.I) is not None),
        check(
            "top path /home with 9",
            out.find("/home") != -1
            and out.find("/home") < out.find("/api/items")
            and re.search(r"/home[^\n]{0,20}\b9\b", out) is not None,
        ),
        check(
            "status counts 200:18, 404:4, 500:2",
            all(
                re.search(rf"\b{code}\b[^\n]{{0,12}}\b{count}\b", out)
                for code, count in ((200, 18), (404, 4), (500, 2))
            ),
        ),
        check(
            "95th percentile of sizes between 2100 and 2300",
            any(2100 <= int(number) <= 2300 for number in re.findall(r"\b(\d{4})\b", out)),
        ),
        check("busiest minute 13:55 with 10", re.search(r"13:55[^\n]{0,30}\b10\b", out) is not None),
        check(
            "reads standard input as well",
            by_stdin.returncode == 0 and re.search(r"\b24\b", by_stdin.stdout) is not None,
        ),
        project_tests(workspace),
    ]
    return {"checks": checks, "evidence": [run_dir / "logstats_output.txt"]}


# --- signature -----------------------------------------------------------------------------------------------------------------


def score_signature(output: Path, truth: dict[str, Any]) -> list[Check]:
    from PIL import Image

    image = Image.open(output).convert("RGBA")
    alpha = image.getchannel("A")
    box = alpha.getbbox()
    ink = alpha.point(lambda value: 1 if value > 0 else 0).histogram()[1]
    page = truth["image"]
    checks = [
        check(
            "the output is a PNG with real transparency",
            image.format in (None, "PNG") and alpha.getextrema()[0] == 0,
            f"alpha range {alpha.getextrema()}",
        )
    ]
    if box is None:
        return [*checks, check("the output contains ink", False, "fully transparent")]
    width, height = box[2] - box[0], box[3] - box[1]
    checks += [
        check(
            "the canvas is a crop, not the page",
            image.size[0] * image.size[1] < 0.4 * page[0] * page[1],
            f"canvas {image.size}",
        ),
        check(
            "the signature ink is the right amount (0.5x to 3x the truth)",
            0.5 <= ink / truth["ink_pixels"] <= 3.0,
            f"{ink} opaque pixels against {truth['ink_pixels']} in the truth ({ink / truth['ink_pixels']:.2f}x)",
        ),
        check(
            "the signature is the right size (0.6x to 1.7x in both directions)",
            0.6 <= width / truth["width"] <= 1.7 and 0.6 <= height / truth["height"] <= 1.7,
            f"{width} x {height} against {truth['width']} x {truth['height']}",
        ),
    ]
    return checks


def on_white(source: Path, target: Path) -> None:
    from PIL import Image

    image = Image.open(source).convert("RGBA")
    base = Image.new("RGB", image.size, (255, 255, 255))
    base.paste(image, mask=image.getchannel("A"))
    scale = max(1, 400 // max(image.size))
    base.resize((image.width * scale, image.height * scale)).save(target)


def verify_sigcrop(workspace: Path, run_dir: Path, task: dict[str, Any], repo: Path) -> dict[str, Any]:
    script = find_file(workspace, "extract_signature.py")
    checks = [check("extract_signature.py exists", script is not None)]
    evidence: list[Path] = []
    if script is None:
        return {"checks": checks, "evidence": evidence}
    python = project_python(workspace)
    for seed in (
        7,
        11,
        23,
    ):  # the photo Forge saw (seed 7) and two others: the script must not be tuned to one picture
        folder = run_dir / f"eval-{seed}"
        truth = make_signature_sample(folder, seed)
        for item in script.parent.glob("*.py"):
            shutil.copy(item, folder / item.name)
        label = "the photo it was given" if seed == 7 else f"another photo (seed {seed})"
        try:
            done = run([python, "extract_signature.py", "prescription.jpg", "signature.png"], folder, 180)
        except subprocess.TimeoutExpired:
            checks.append(check(f"{label}: runs within 3 minutes", False, "timed out"))
            continue
        output = folder / "signature.png"
        if done.returncode != 0 or not output.is_file():
            checks.append(
                check(f"{label}: produces signature.png", False, (done.stderr or done.stdout)[-300:])
            )
            continue
        for item in score_signature(output, truth):
            checks.append({**item, "name": f"{label}: {item['name']}"})
        shown = run_dir / f"signature-seed{seed}-on-white.png"
        on_white(output, shown)
        evidence += [shown, folder / "prescription.jpg"]
    checks.append(project_tests(workspace))
    return {"checks": checks, "evidence": evidence}


# --- invoice application -------------------------------------------------------------------------------------------------------


def free_port_from_readme(project: Path) -> list[int]:
    ports: list[int] = []
    for name in ("README.md", "readme.md"):
        path = project / name
        if path.is_file():
            ports += [
                int(p)
                for p in re.findall(
                    r"(?:localhost|127\.0\.0\.1):(\d{2,5})",
                    path.read_text(encoding="utf-8", errors="replace"),
                )
            ]
    return [*dict.fromkeys(ports), 8000, 8080, 5000, 8765]


def http_get(url: str, timeout: int = 8) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return 0, ""


def kill_tree(process: subprocess.Popen[Any]) -> None:
    with contextlib.suppress(Exception):
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30
            )
        else:
            process.kill()


def verify_invoice_app(workspace: Path, run_dir: Path, task: dict[str, Any], repo: Path) -> dict[str, Any]:
    project = workspace / "project"
    checks = [
        check("README.md exists", (project / "README.md").is_file()),
        check("DESIGN.md exists", (project / "DESIGN.md").is_file()),
        project_tests(workspace),
    ]
    samples = [
        p
        for p in project.rglob("*")
        if p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg")
        and not {".venv", "node_modules", "static", ".forge", "uploads"} & set(p.parts)
    ]
    checks.append(
        check(
            "about ten sample invoices were generated",
            len(samples) >= 8,
            f"{len(samples)} pictures or PDFs found",
        )
    )
    evidence: list[Path] = []
    python = project_python(workspace)
    log = (run_dir / "server.log").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [python, "-m", "app"], cwd=project, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL
    )
    base = ""
    try:
        deadline = time.time() + 40
        while time.time() < deadline and not base and server.poll() is None:
            for port in free_port_from_readme(project):
                if http_get(f"http://127.0.0.1:{port}/")[0] == 200:
                    base = f"http://127.0.0.1:{port}"
                    break
            time.sleep(1.5)
        checks.append(
            check(
                "`python -m app` starts and answers on a local port",
                bool(base),
                base or "see server.log",
            )
        )
        if base:
            evidence += crawl(base, run_dir, checks)
    finally:
        kill_tree(server)
        log.close()
    evidence.append(run_dir / "server.log")
    return {"checks": checks, "evidence": evidence}


def crawl(base: str, run_dir: Path, checks: list[Check]) -> list[Path]:
    """Visit the start page and the pages it links to (same address, up to 10), photograph each at 1440 x 900 and look for the features the brief asked for."""
    _, home = http_get(base + "/")
    pages = {"/": home}
    for href in re.findall(r'href="(/[^"#?]*)"', home):
        if (
            href not in pages
            and not href.startswith(("/static", "/docs", "/openapi", "/files", "/download", "/api"))
            and len(pages) < 11
        ):
            code, body = http_get(base + href)
            if code == 200 and "<html" in body.lower():
                pages[href] = body
    text = " ".join(pages.values()).lower()
    wanted = {
        "an upload option": r"upload",
        "email (IMAP) as a source": r"imap|e-?mail",
        "SharePoint as a source": r"sharepoint",
        "batch processing": r"batch",
        "approve": r"approve",
        "unprocessed and processed lists": r"unprocessed",
        "a reporting page": r"report",
    }
    for name, pattern in wanted.items():
        checks.append(check(f"the pages mention {name}", re.search(pattern, text) is not None))
    checks.append(
        check(
            "at least three different pages are reachable from the start page",
            len(pages) >= 3,
            f"pages: {', '.join(pages)}",
        )
    )
    shots: list[Path] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
            except Exception:
                browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            for href in pages:
                with contextlib.suppress(Exception):
                    page.goto(base + href, wait_until="load", timeout=20000)
                    page.wait_for_timeout(700)
                    target = run_dir / (
                        "page-" + (re.sub(r"[^a-z0-9]+", "-", href.strip("/").lower()) or "home") + ".png"
                    )
                    page.screenshot(path=str(target), full_page=False)
                    shots.append(target)
            browser.close()
    except Exception as error:  # a missing browser is reported, never fatal
        checks.append(check("the pages can be photographed", False, str(error)[:200]))
    return shots


# --- research ------------------------------------------------------------------------------------------------------------------


def verify_research(workspace: Path, run_dir: Path, task: dict[str, Any], repo: Path) -> dict[str, Any]:
    report = find_file(workspace, "report.md")
    checks = [check("report.md exists", report is not None)]
    if report is None:
        return {"checks": checks, "evidence": []}
    text = report.read_text(encoding="utf-8", errors="replace")
    urls = set(re.findall(r"https?://[^\s)>\]]+", text))
    checks += [
        check("at least five different source addresses", len(urls) >= 5, f"{len(urls)} found"),
        check("Tesseract is covered", "tesseract" in text.lower()),
        check(
            "says what it could not confirm",
            re.search(
                r"could not (be )?confirm|not confirmed|unconfirmed|unable to confirm|could not verify",
                text,
                re.I,
            )
            is not None,
        ),
        check("long enough to be a report (1,500 characters)", len(text) >= 1500, f"{len(text)} characters"),
        check("gives a recommendation", re.search(r"recommend", text, re.I) is not None),
    ]
    return {"checks": checks, "evidence": [report]}


VERIFIERS = {
    "bugfix": verify_bugfix,
    "logstats": verify_logstats,
    "sigcrop": verify_sigcrop,
    "invoice_app": verify_invoice_app,
    "research": verify_research,
}


def verify(task: dict[str, Any], workspace: Path, run_dir: Path, repo: Path) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = VERIFIERS[task["verify"]](workspace, run_dir, task, repo)
    except Exception as error:  # a broken verifier must not hide the run
        result = {
            "checks": [check("the verifier itself ran", False, f"{type(error).__name__}: {error}")],
            "evidence": [],
        }
    result["passed"] = sum(1 for item in result["checks"] if item["ok"])
    result["total"] = len(result["checks"])
    result["evidence"] = [str(path) for path in result["evidence"] if Path(path).exists()]
    return result


if __name__ == "__main__":  # python verify_tasks.py <task-json> <workspace> <run-dir>
    task_file, workspace_arg, run_arg = (Path(arg) for arg in sys.argv[1:4])
    print(
        json.dumps(
            verify(
                json.loads(task_file.read_text(encoding="utf-8")), workspace_arg, run_arg, HERE.parents[1]
            ),
            indent=1,
        )
    )
