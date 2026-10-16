"""The overnight job list: what runs, in which order, how long it may take and what it needs.

A job is one command run as its own process. `needs` names capabilities the preflight found (azure, azure_strong, gemini, image, pytest, node, edge): a job whose need is missing is
skipped with the reason written in the report, never started. Tier 1 is the core night (about ten hours); tier 2 is added with --profile extended."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Ctx:
    repo: Path
    out: Path
    env_file: str
    caps: dict[str, bool] = field(default_factory=dict)
    python: str = sys.executable

    @property
    def runs(self) -> Path:
        return self.out / "runs"

    def env_arg(self) -> list[str]:
        return ["--env", f"FORGE_ENV_FILE={self.env_file}"] if self.env_file else []

    def default_coder(self) -> str:
        """The builder model of the "A" arms: gpt-5.4 when the preflight found it answering (the default since D-446), else gpt-5.1."""
        return "gpt54" if self.caps.get("azure_strong") else "gpt51"

    def gemini_flags(self, model: str = "gemini31pro") -> list[str]:
        """The neutral critic and scorer for the design runs when Gemini answers; without it the runs use the Azure models (and say so in the report)."""
        return ["--critic-model", model, "--scorer-model", model] if self.caps.get("gemini") else []


@dataclass
class Job:
    id: str
    title: str
    group: str
    est_min: int
    timeout_min: int
    argv: Callable[[Ctx], list[str]]
    tier: int = 1
    needs: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    stall_min: int = 25
    run_root: str = ""  # a folder under out/runs where the job's own results are kept (watched for activity and searched for evidence)
    results_glob: str = ""  # results.md of a benchmark, relative to out/runs
    kind: str = "command"  # command, benchmark, tasks, pytest
    uses_env_file: bool = True  # a test job must NOT see FORGE_ENV_FILE: DebCraft's tests build their own isolated home and the override would replace it (found in the first night, D-443)


def script(ctx: Ctx, *parts: str) -> str:
    return str(ctx.repo.joinpath(*parts))


def benchmark(
    name: str,
    bench: str,
    root: str,
    run_name: str,
    extra: Callable[[Ctx], list[str]],
    est: int,
    timeout: int,
    **kw: object,
) -> Job:
    """One run of a benchmark script; its results land in out/runs/<root>/<run_name>."""
    return Job(
        id=name, title=kw.pop("title", f"{bench} {run_name}"), group=str(kw.pop("group", "benchmark")),  # type: ignore[arg-type]
        est_min=est, timeout_min=timeout, run_root=f"{root}/{run_name}", results_glob=f"{root}/{run_name}/results.md", kind="benchmark",
        argv=lambda ctx: [ctx.python, script(ctx, "scripts", "benchmark", bench), run_name, *extra(ctx), *ctx.env_arg()], **kw,  # type: ignore[arg-type]
    )  # fmt: skip


def task(task_id: str, est: int, timeout: int, needs: tuple[str, ...] = ()) -> Job:
    return Job(
        id=f"task_{task_id}", title=f"Forge task: {task_id}", group="tasks", est_min=est, timeout_min=timeout + 10, needs=needs, kind="tasks", run_root=f"tasks/{task_id}",
        argv=lambda ctx: [ctx.python, script(ctx, "scripts", "overnight", "tasks_runner.py"), task_id, "--out", str(ctx.runs / "tasks"), *(["--env-file", ctx.env_file] if ctx.env_file else []), "--default-coder", ctx.default_coder()],
    )  # fmt: skip


def pytest_job(
    job_id: str,
    title: str,
    args: list[str],
    est: int,
    timeout: int,
    needs: tuple[str, ...] = ("pytest",),
    env: dict[str, str] | None = None,
) -> Job:
    return Job(
        id=job_id, title=title, group="tests", est_min=est, timeout_min=timeout, needs=needs, env=env or {}, kind="pytest", uses_env_file=job_id == "tests_live",
        argv=lambda ctx: [ctx.python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
    )  # fmt: skip


def gallery(job_id: str, title: str, name: str, arms: list[str]) -> Job:
    return Job(
        id=job_id, title=title, group="design taste", est_min=2, timeout_min=10, needs=("gemini",), kind="command", run_root=f"designbench/gallery-{name}",
        argv=lambda ctx: [ctx.python, script(ctx, "scripts", "benchmark", "blind_gallery.py"), name, *arms],
    )  # fmt: skip


def catalogue() -> list[Job]:
    cheap = lambda ctx: []  # noqa: E731
    coder_gpt51 = lambda ctx: ["--coder-model", ctx.default_coder(), *ctx.gemini_flags()]  # noqa: E731  (the name is old: since D-446 the default builder is gpt-5.4 where it answers)
    jobs: list[Job] = [
        pytest_job(
            "tests_fast",
            "Test suite without the browser tests",
            ["-n", "4", "--dist", "loadfile", "-m", "not browser and not live"],
            10,
            45,
        ),
        Job(
            "smoke_gemini",
            "Gemini provider smoke test",
            "smoke",
            4,
            20,
            needs=("gemini",),
            argv=lambda ctx: [ctx.python, script(ctx, "scripts", "dev", "gemini_smoke.py")],
        ),
        Job(
            "smoke_image",
            "generate_image smoke test (Vertex AI)",
            "smoke",
            4,
            20,
            needs=("gemini",),
            argv=lambda ctx: [ctx.python, script(ctx, "scripts", "dev", "image_smoke.py")],
        ),
        # the Fernhill bakery page: three arms, the same brief; A is the default model (gpt-5.4 where it answers, else gpt-5.1) designing and building, C is Argon doing both, B is the default model building from Argon's DESIGN.md
        benchmark(
            "fernhill_a",
            "run_design_benchmark.py",
            "designbench",
            "fernhill-a",
            lambda ctx: ["--tasks", "d06_fernhill_full", *coder_gpt51(ctx)],
            30,
            90,
            group="design taste",
            title="Fernhill page, arm A (the default model designs and builds)",
        ),
        benchmark(
            "fernhill_c",
            "run_design_benchmark.py",
            "designbench",
            "fernhill-c",
            lambda ctx: [
                "--tasks",
                "d06_fernhill_full",
                "--coder-model",
                "gemini4argon",
                *ctx.gemini_flags(),
            ],
            30,
            90,
            needs=("gemini",),
            group="design taste",
            title="Fernhill page, arm C (Argon designs and builds)",
        ),
        benchmark(
            "fernhill_b",
            "run_design_benchmark.py",
            "designbench",
            "fernhill-b",
            lambda ctx: ["--tasks", "d06_fernhill_full", "--design-from", "fernhill-c", *coder_gpt51(ctx)],
            30,
            90,
            needs=("gemini",),
            group="design taste",
            title="Fernhill page, arm B (the default model builds from Argon's DESIGN.md)",
        ),
        gallery(
            "fernhill_gallery",
            "Blind gallery of the three Fernhill pages",
            "fernhill",
            ["A=fernhill-a", "B=fernhill-b", "C=fernhill-c"],
        ),
        task("bugfix", 10, 25),
        task("logstats", 12, 30),
        task("sigcrop", 20, 40),
        task("sigcrop_gemini", 20, 40, ("gemini",)),
        task("sigcrop_strong", 20, 40, ("azure_strong",)),
        task("research", 12, 25),
        # a quick look at four short briefs in the same three arms
        benchmark(
            "taste_mini_a",
            "run_design_benchmark.py",
            "designbench",
            "taste-mini-a",
            lambda ctx: ["--mini", *coder_gpt51(ctx)],
            25,
            75,
            group="design taste",
            title="Two small briefs, arm A",
        ),
        benchmark(
            "taste_mini_c",
            "run_design_benchmark.py",
            "designbench",
            "taste-mini-c",
            lambda ctx: ["--mini", "--coder-model", "gemini4argon", *ctx.gemini_flags()],
            25,
            75,
            needs=("gemini",),
            group="design taste",
            title="Two small briefs, arm C",
        ),
        benchmark(
            "taste_mini_b",
            "run_design_benchmark.py",
            "designbench",
            "taste-mini-b",
            lambda ctx: ["--mini", "--design-from", "taste-mini-c", *coder_gpt51(ctx)],
            25,
            75,
            needs=("gemini",),
            group="design taste",
            title="Two small briefs, arm B",
        ),
        gallery(
            "taste_mini_gallery",
            "Blind gallery of the small briefs",
            "taste-mini",
            ["A=taste-mini-a", "B=taste-mini-b", "C=taste-mini-c"],
        ),
        benchmark(
            "ab_mini_azure",
            "run_design_benchmark.py",
            "designbench",
            "ab-mini-azure",
            lambda ctx: ["--mini", "--scorer-model", "gemini4argon"],
            12,
            40,
            needs=("gemini",),
            group="gemini A/B",
            title="Critic A/B, the Azure models check the work",
        ),
        benchmark(
            "ab_mini_argon",
            "run_design_benchmark.py",
            "designbench",
            "ab-mini-argon",
            lambda ctx: ["--mini", "--critic-model", "gemini4argon", "--scorer-model", "gemini4argon"],
            12,
            40,
            needs=("gemini",),
            group="gemini A/B",
            title="Critic A/B, Gemini 4 Argon checks the work",
        ),
        pytest_job(
            "tests_browser",
            "Browser tests of the web app and the pages",
            ["-n", "3", "--dist", "loadfile", "-m", "browser"],
            15,
            70,
            needs=("pytest", "edge"),
        ),
        pytest_job(
            "tests_live",
            "Live model tests (real Azure and Gemini calls)",
            ["-m", "live"],
            20,
            75,
            needs=("pytest", "azure"),
        ),
        pytest_job(
            "tests_network",
            "Tests that need npm and the internet (shadcn, Magic UI)",
            ["tests/test_shadcn_setup.py", "tests/test_add_ui_component.py"],
            8,
            30,
            needs=("pytest", "node"),
            env={"FORGE_NETWORK_TESTS": "1"},
        ),
        task("invoice_app", 90, 150),
        benchmark(
            "code_bench",
            "run_code_benchmark.py",
            "codebench",
            "code",
            lambda ctx: ["--parallel", "3"],
            60,
            150,
            needs=("azure",),
            group="coding",
            title="Fourteen coding tasks scored with hidden tests",
        ),
        benchmark(
            "challenges",
            "run_challenges.py",
            "challenges",
            "challenges",
            cheap,
            45,
            100,
            needs=("azure",),
            group="coding",
            title="Ten approach challenges (how it tackles a trap)",
        ),
        benchmark(
            "docs_bench",
            "run_document_benchmark.py",
            "docbench",
            "docs",
            cheap,
            30,
            90,
            needs=("azure",),
            group="documents",
            title="Word report, Excel workbook and PDF handout",
        ),
        benchmark(
            "decks_bench",
            "run_deck_benchmark.py",
            "deckbench",
            "decks",
            lambda ctx: [
                "--tasks",
                "d01_status_update,d02_investor_pitch,d03_training,d07_edit_deck,d13_corporate_template",
                "--parallel",
                "2",
            ],
            40,
            120,
            needs=("azure",),
            group="presentations",
            title="Five presentation requests",
        ),
    ]
    extended = [
        benchmark(
            "taste_full_a",
            "run_design_benchmark.py",
            "designbench",
            "taste-a",
            lambda ctx: [
                "--tasks",
                "d01_science_museum,d03_ops_dashboard,d04_member_table,d05_booking_wizard",
                *coder_gpt51(ctx),
            ],
            90,
            200,
            group="design taste",
            title="Four briefs, arm A",
        ),
        benchmark(
            "taste_full_c",
            "run_design_benchmark.py",
            "designbench",
            "taste-c",
            lambda ctx: [
                "--tasks",
                "d01_science_museum,d03_ops_dashboard,d04_member_table,d05_booking_wizard",
                "--coder-model",
                "gemini4argon",
                *ctx.gemini_flags(),
            ],
            90,
            200,
            needs=("gemini",),
            group="design taste",
            title="Four briefs, arm C",
        ),
        benchmark(
            "taste_full_b",
            "run_design_benchmark.py",
            "designbench",
            "taste-b",
            lambda ctx: [
                "--tasks",
                "d01_science_museum,d03_ops_dashboard,d04_member_table,d05_booking_wizard",
                "--design-from",
                "taste-c",
                *coder_gpt51(ctx),
            ],
            90,
            200,
            needs=("gemini",),
            group="design taste",
            title="Four briefs, arm B",
        ),
        gallery(
            "taste_full_gallery",
            "Blind gallery of the four briefs",
            "taste",
            ["A=taste-a", "B=taste-b", "C=taste-c"],
        ),
        benchmark(
            "ab_full_azure",
            "run_design_benchmark.py",
            "designbench",
            "ab-azure",
            lambda ctx: [
                "--tasks",
                "d01_science_museum,d03_ops_dashboard,d04_member_table,d05_booking_wizard",
                "--scorer-model",
                "gemini4argon",
            ],
            90,
            200,
            needs=("gemini",),
            group="gemini A/B",
            title="Critic A/B on four briefs, Azure checks",
        ),
        benchmark(
            "ab_full_argon",
            "run_design_benchmark.py",
            "designbench",
            "ab-argon",
            lambda ctx: [
                "--tasks",
                "d01_science_museum,d03_ops_dashboard,d04_member_table,d05_booking_wizard",
                "--critic-model",
                "gemini4argon",
                "--scorer-model",
                "gemini4argon",
            ],
            90,
            200,
            needs=("gemini",),
            group="gemini A/B",
            title="Critic A/B on four briefs, Argon checks",
        ),
        benchmark(
            "speed_bench",
            "run_speed_benchmark.py",
            "speedbench",
            "speed",
            cheap,
            40,
            100,
            needs=("azure",),
            group="speed",
            title="Speed benchmark on this machine (nothing else runs beside it)",
        ),
    ]
    for job in extended:
        job.tier = 2
    return [*jobs, *extended]
