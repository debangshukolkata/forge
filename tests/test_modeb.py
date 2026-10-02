"""M10B: standalone (Mode B) workspaces — layout and jail, harness on the import path, stricter shell scope,
export with revisions, the assumption register, sensitive-term web guard, session wiring, commands, CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from forge.cli import main
from forge.engine.session_host import SessionHost
from forge.modeb.assumptions import AssumptionRegister
from forge.modeb.output import build_modeb_output, write_document
from forge.modeb.profile import ProfileStore, host_identifying_terms
from forge.modeb.workspace import create_standalone_workspace
from forge.protocol.events import EventBus, EventType
from forge.safety.paths import JailViolationError
from forge.safety.redact import Redactor
from forge.safety.shell_classifier import classify
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.tools.web import WebSearch
from forge.workspace.workspace import Workspace
from tests.helpers import mocked_router, run_pytest

EXTEND_PATH = '__path__ = __import__("pkgutil").extend_path(__path__, __name__)\n'
STUB = "def get_rate(code: str) -> float:\n    return {'EUR': 0.9}.get(code, 1.0)\n"
FEATURE = "from hostapp.rates import get_rate\n\n\ndef convert(amount: float, code: str) -> float:\n    return round(amount * get_rate(code), 2)\n"
TEST = "from hostapp.fx.convert import convert\n\n\ndef test_convert() -> None:\n    assert convert(10, 'EUR') == 9.0\n"


@pytest.fixture
def workspace(tmp_path: Path, isolated_forge_home: Path) -> Workspace:
    profile = ProfileStore(isolated_forge_home).create("host", sensitive_terms=["Contoso"])
    workspace = create_standalone_workspace(tmp_path / "wsb", profile)
    # Tests below run pytest: use this interpreter (it has pytest) instead of the new, empty venv.
    assert workspace.info.python_env is not None
    workspace.info.python_env = workspace.info.python_env.model_copy(update={"python": sys.executable})
    workspace.save_info()
    return Workspace.open(workspace.root)


def test_layout_and_jail(workspace: Workspace) -> None:
    assert workspace.mode_b and workspace.info.repo_path == "" and workspace.repo_dir.name == "project"
    assert (workspace.root / "_harness" / "harness_conftest.py").exists()
    assert (workspace.root / ".venv").is_dir()
    assert (
        workspace.path_of("_harness/host_stubs/x.py")
        == (workspace.harness_dir / "host_stubs" / "x.py").resolve()
    )
    assert workspace.path_of("app/x.py") == (workspace.repo_dir / "app" / "x.py").resolve()
    workspace.jail.check(workspace.harness_dir / "a.py")  # writable
    with pytest.raises(JailViolationError):
        workspace.jail.check(workspace.root.parent / "elsewhere.py")
    env = workspace.info.python_env
    assert env is not None and env.command_env()["PYTHONPATH"].split(";" if sys.platform == "win32" else ":")[
        0
    ].endswith("project")


def test_mode_b_shell_blocks_paths_outside_the_workspace(workspace: Workspace) -> None:
    scope = ShellSession(workspace, sandbox="off").scope()
    assert scope.strict and scope.original_repo is None
    assert classify("Get-Content C:\\Windows\\win.ini", scope).level == "blocked"
    assert classify("Get-Content project\\app\\x.py", scope).level == "safe"


async def test_tests_run_against_harness_stubs(workspace: Workspace) -> None:
    workspace.write_text("_harness/host_stubs/hostapp/__init__.py", EXTEND_PATH)
    workspace.write_text("_harness/host_stubs/hostapp/rates.py", STUB)
    workspace.write_text("hostapp/fx/__init__.py", "")
    workspace.write_text("hostapp/fx/convert.py", FEATURE)
    workspace.write_text("tests/test_convert.py", TEST)
    context = ToolContext(workspace=workspace, shell=ShellSession(workspace, sandbox="off"))
    ok, summary, report = await run_pytest(context, "tests/test_convert.py")
    assert ok, summary
    assert report.counts.get("passed") == 1


def test_export_revisions_and_documents(workspace: Workspace) -> None:
    workspace.write_text("hostapp/fx/__init__.py", "")
    workspace.write_text("hostapp/fx/convert.py", FEATURE)
    workspace.write_text("_harness/host_stubs/hostapp/rates.py", STUB)
    write_document(
        workspace, "INTERFACE_CONTRACT", "# Interface contract\n\n- `hostapp.rates.get_rate(code) -> float`\n"
    )
    write_document(workspace, "INTEGRATION_NOTES", "- Register nothing: pure function.")
    AssumptionRegister(workspace).add(
        "get_rate returns a float multiplier",
        "medium",
        "high",
        "python -c 'from hostapp.rates import get_rate'",
    )
    build_modeb_output(workspace)
    out = workspace.output_dir
    assert (out / "hostapp/fx/convert.py").exists() and not (out / "_harness").exists()
    assert "rates.py" not in json.dumps([p.name for p in out.rglob("*")])  # stubs are never delivered
    guide = (out / "INTEGRATION_GUIDE.md").read_text(encoding="utf-8")
    assert (
        "copy `output/hostapp/fx/convert.py`" in guide and "A1: get_rate returns a float multiplier" in guide
    )
    assert "hostapp.rates.get_rate" in (out / "INTERFACE_CONTRACT.md").read_text(encoding="utf-8")
    assert "| A1 |" in (out / "ASSUMPTIONS.md").read_text(encoding="utf-8")
    assert "First delivery" in (out / "REVISION_NOTES.md").read_text(encoding="utf-8")

    workspace.write_text("hostapp/fx/convert.py", FEATURE.replace("2)", "4)"))
    build_modeb_output(workspace)
    notes = (out / "REVISION_NOTES.md").read_text(encoding="utf-8")
    assert "Revision 2" in notes and "changed: `hostapp/fx/convert.py`" in notes and "__init__" not in notes
    assert (workspace.forge_dir / "revisions" / "r1" / "INTEGRATION_GUIDE.md").exists()


async def test_web_search_never_sends_host_identifying_terms(workspace: Workspace) -> None:
    context = ToolContext(workspace=workspace, sensitive_terms=("Contoso", "claims_app"))
    refused = await WebSearch().run(WebSearch.Args(query="contoso claims_app pagination error"), context)
    assert not refused.ok and "host-identifying" in refused.content


def test_host_identifying_terms_come_from_the_profile(isolated_forge_home: Path) -> None:
    profile = ProfileStore(isolated_forge_home).create("h2", sensitive_terms=["Contoso"])
    profile.import_structure(
        {
            "format": "forge-structure-export",
            "version": 1,
            "tree": [],
            "packages": {},
            "sql_scripts": [],
            "not_exported": [],
            "modules": {
                "claims_app/models/claim.py": {
                    "imports": [],
                    "classes": [],
                    "functions": [],
                    "blueprints": [],
                    "models": [{"class": "Claim", "table": "claims", "columns": []}],
                    "graph": {"nodes": [], "edges": []},
                    "env_keys": [],
                }
            },
        }
    )
    assert set(host_identifying_terms(profile)) == {"Contoso", "claims_app", "claims"}


async def test_session_and_commands_in_mode_b(workspace: Workspace) -> None:
    def unreachable(request: object) -> object:
        raise AssertionError("no LLM call expected")

    host = SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    assert {"profile_search", "assumption_add", "modeb_document"} <= set(host.agent.tools.names())
    assert "Host profile 'host'" in (host.context_manager.pinned.get("kb_essentials") or "")
    assert "STANDALONE mode" in host.system_prompt and "Contoso" in host.agent.context.sensitive_terms
    for command in (
        "/diagnose",
        "/assumptions",
        "/profile",
        "/revision",
        "/forget-snippet E001",
    ):
        await host._commands.handle(command)
    texts = [str(e.payload.get("text")) for e in host.bus.events_since(0) if e.type == EventType.NOTICE]
    assert any("paste the error" in t for t in texts)
    assert any("Assumptions" in t for t in texts) and any("nothing exported yet" in t for t in texts)


def test_cli_profile_and_standalone_workspace(
    tmp_path: Path, isolated_forge_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["profile", "new", "cli-host", "--terms", "Contoso,Fabrikam"]) == 0
    script = tmp_path / "forge_structure_export.py"
    assert main(["profile", "export-script", "--out", str(script)]) == 0 and script.exists()
    export = tmp_path / "structure_export.json"
    export.write_text(
        json.dumps(
            {
                "format": "forge-structure-export",
                "version": 1,
                "tree": [],
                "packages": {},
                "modules": {},
                "sql_scripts": [],
                "not_exported": [],
            }
        ),
        encoding="utf-8",
    )
    assert main(["profile", "import", "cli-host", str(export)]) == 0
    assert main(["new", "--standalone", "--workspace", str(tmp_path / "ws"), "--profile", "cli-host"]) == 0
    assert Workspace.open(tmp_path / "ws").mode_b
    assert main(["new", "--standalone", "--workspace", str(tmp_path / "ws2")]) == 2  # no profile
    assert "Imported" in capsys.readouterr().out


async def test_file_and_search_tools_stay_inside_the_mode_b_workspace(
    workspace: Workspace, tmp_path: Path
) -> None:
    from forge.tools.files import ReadFile, WriteFile
    from forge.tools.search import Glob, Grep

    outside = tmp_path / "host_repo_secret.py"
    outside.write_text("SECRET = 1\n", encoding="utf-8")
    context = ToolContext(workspace=workspace, shell=ShellSession(workspace, sandbox="off"))
    for tool, args in [
        (ReadFile(), ReadFile.Args(path="../host_repo_secret.py")),
        (ReadFile(), ReadFile.Args(path=str(outside))),
        (WriteFile(), WriteFile.Args(path="../../evil.py", content="x")),
        (Grep(), Grep.Args(pattern="SECRET", path="..")),
        (Glob(), Glob.Args(pattern="*.py", path="..")),
    ]:
        try:
            result = await tool.run(args, context)  # type: ignore[arg-type]
        except Exception as error:
            assert "outside" in str(error).lower() or "jail" in type(error).__name__.lower(), error
            continue
        assert not result.ok or "SECRET" not in result.content, (tool.name, result.content)


async def test_mode_b_commands_run_in_the_sandbox(workspace: Workspace) -> None:
    """The live run found this: labelling Mode B's .venv for the sandbox went through the write jail and failed."""
    workspace.write_text("_harness/host_stubs/hostapp/__init__.py", EXTEND_PATH)
    workspace.write_text("_harness/host_stubs/hostapp/rates.py", STUB)
    workspace.write_text("hostapp/fx/__init__.py", "")
    workspace.write_text("hostapp/fx/convert.py", FEATURE)
    workspace.write_text("tests/test_convert.py", TEST)
    shell = ShellSession(workspace, sandbox="low_integrity")
    context = ToolContext(workspace=workspace, shell=shell)
    ok, summary, _ = await run_pytest(context, "tests/test_convert.py")
    assert ok, summary
    assert shell.sandbox_active is True


def test_existing_host_files_become_merge_instructions(
    workspace: Workspace, isolated_forge_home: Path
) -> None:
    profile = ProfileStore(isolated_forge_home).open("host")
    profile.import_structure(
        {
            "format": "forge-structure-export",
            "version": 1,
            "tree": ["hostapp/api/__init__.py"],
            "packages": {},
            "modules": {},
            "sql_scripts": [],
            "not_exported": [],
        }
    )
    workspace.write_text("hostapp/api/__init__.py", "from hostapp.api.fx import blp as fx_blp\n")
    workspace.write_text("hostapp/api/fx.py", "blp = object()\n")
    build_modeb_output(workspace)
    out = workspace.output_dir
    assert not (out / "hostapp/api/__init__.py").exists()  # never overwrite a host file Forge hasn't seen
    assert (out / "_merge" / "hostapp/api/__init__.py.proposed").exists() and (
        out / "hostapp/api/fx.py"
    ).exists()
    assert "NOT delivered as files" in (out / "INTEGRATION_GUIDE.md").read_text(encoding="utf-8")


async def test_search_tools_work_on_the_harness_folder(workspace: Workspace) -> None:
    # _harness/ sits beside project/; paths there are workspace-relative (seen live: list_dir crashed).
    from forge.tools.search import Glob, Grep, ListDir

    stub = workspace.path_of("_harness/host_stubs/demo_pkg/models.py")
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text("class DemoModel:\n    pass\n", encoding="utf-8")
    context = ToolContext(workspace=workspace)
    listed = await ListDir().run(ListDir.Args(path="_harness/host_stubs/demo_pkg"), context)
    assert listed.ok and "models.py" in listed.content, listed.content
    found = await Glob().run(Glob.Args(pattern="*.py", path="_harness/host_stubs"), context)
    assert "_harness/host_stubs/demo_pkg/models.py" in found.content, found.content
    matched = await Grep().run(Grep.Args(pattern="DemoModel", path="_harness"), context)
    assert "demo_pkg/models.py" in matched.content, matched.content


def test_guide_lists_unregistered_blueprints(workspace: Workspace) -> None:
    # Seen live: the agent wired its blueprint only in the harness; the host got a 404.
    from forge.modeb.output import integration_guide, write_document

    route = workspace.output_dir / "claims_app/api/stats/routes.py"
    route.parent.mkdir(parents=True, exist_ok=True)
    route.write_text('blp = Blueprint("stats", __name__)\n', encoding="utf-8")
    guide = integration_guide(workspace, ["claims_app/api/stats/routes.py"], has_sql=False)
    assert "register the new Blueprint `blp` from `claims_app.api.stats.routes`" in guide
    write_document(
        workspace, "INTEGRATION_NOTES", "Register claims_app.api.stats.routes blp in api/__init__.py"
    )
    guide = integration_guide(workspace, ["claims_app/api/stats/routes.py"], has_sql=False)
    assert "register the new Blueprint" not in guide


def test_stub_packages_are_shared_with_project(workspace: Workspace) -> None:
    # Seen live: a stub services/__init__.py without extend_path hid project/'s new service module.
    import os
    import subprocess
    import sys

    from forge.workspace.stub_packages import ensure_shared_stub_packages

    workspace.write_text("demo_host/services/new_service.py", "VALUE = 'new'\n")
    workspace.write_text("_harness/host_stubs/demo_host/__init__.py", "")
    workspace.write_text("_harness/host_stubs/demo_host/services/__init__.py", "")
    workspace.write_text("_harness/host_stubs/demo_host/services/old_service.py", "VALUE = 'stub'\n")
    code = (
        "from demo_host.services import new_service, old_service; print(new_service.VALUE, old_service.VALUE)"
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(workspace.repo_dir), str(workspace.harness_dir / "host_stubs")]),
    }

    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)

    assert run().returncode != 0  # the stub package hides project/'s module
    assert ensure_shared_stub_packages(workspace) == ["demo_host", "demo_host/services"]
    assert run().stdout.split() == ["new", "stub"]
    assert ensure_shared_stub_packages(workspace) == []  # idempotent


async def test_project_prefix_is_rejected_in_mode_b(workspace: Workspace) -> None:
    # Seen live: files written to project/project/<pkg>/ were delivered under output/project/.
    from forge.tools.files import WriteFile

    context = ToolContext(workspace=workspace)
    try:
        result = await WriteFile().run(WriteFile.Args(path="project/demo/x.py", content="X = 1\n"), context)
        ok, message = result.ok, result.content
    except Exception as error:  # the loop turns ForgeError into a failed tool result
        ok, message = False, str(error)
    assert not ok and "Drop the 'project/' prefix" in message
    assert not (workspace.repo_dir / "project").exists()


def test_tests_using_host_db_setup_must_request_a_host_fixture(workspace: Workspace) -> None:
    # Seen in every live Mode B run: contract tests called session_scope() with no fixture; the stub worked,
    # the real host (engine set up by the app fixture) did not.
    from forge.modeb.fixture_check import check_fixture_use

    workspace.write_text(
        "_harness/harness_conftest.py",
        "import pytest\n\n\n@pytest.fixture\ndef app():\n    return None\n\n\n"
        "@pytest.fixture\ndef client(app):\n    return None\n",
    )
    workspace.write_text(
        "demo_host/services/stats_service.py",
        "from demo_host.db import session_scope\n\n\ndef count():\n    with session_scope() as s:\n"
        "        return 1\n\n\ndef label(n):\n    return str(n)\n",
    )
    workspace.write_text(
        "tests/test_stats.py",
        "from demo_host.db import session_scope\nfrom demo_host.services.stats_service import count, label\n\n\n"
        "def test_direct():\n    with session_scope():\n        pass\n\n\n"
        "def test_through_service():\n    assert count() == 1\n\n\n"
        "def test_with_fixture(client):\n    assert count() == 1\n\n\n"
        "def test_pure():\n    assert label(1) == '1'\n",
    )
    findings = check_fixture_use(workspace)
    assert [f.test for f in findings] == ["test_direct", "test_through_service"]
    assert findings[0].blocking and "client" in findings[0].problem


def test_new_standalone_venv_gets_the_test_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Seen live: the empty venv had no pytest, pip install needs approval, and a headless run blocked every task.
    import subprocess

    from forge.modeb import workspace as modeb_workspace

    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        failing = "pytest" in command and len(calls) > 1
        return subprocess.CompletedProcess(
            command, 1 if failing else 0, "", "network down" if failing else ""
        )

    monkeypatch.delenv("FORGE_SKIP_TEST_RUNNER_INSTALL")
    monkeypatch.setattr(modeb_workspace.subprocess, "run", fake_run)
    assert modeb_workspace.install_test_runner(Path("py.exe")) == "installed"
    assert calls[0][1:] == ["-m", "pip", "install", "--disable-pip-version-check", "-q", "pytest"]
    assert modeb_workspace.install_test_runner(Path("py.exe")) == "not installed: network down"


def test_contract_lists_the_host_symbols_the_code_imports(workspace: Workspace) -> None:
    # Seen live: no INTERFACE_CONTRACT written, and the default text claimed no host symbols were used.
    from forge.modeb.contract_scan import contract_with_host_symbols, host_symbols_used

    workspace.write_text("_harness/host_stubs/payments/__init__.py", "")
    workspace.write_text(
        "_harness/host_stubs/payments/audit.py", "def log_event(event: str, **fields: object) -> None: ...\n"
    )
    workspace.write_text(
        "payments/security/masking.py",
        "import json\nfrom payments.audit import log_event\nfrom payments.security.helpers import digits\n"
        "from payments.ledger import Ledger\n",
    )
    workspace.write_text("payments/security/helpers.py", "def digits(s): return s\n")
    symbols = host_symbols_used(workspace, ["payments/security/masking.py", "payments/security/helpers.py"])
    assert [(s.module, s.name) for s in symbols] == [
        ("payments.audit", "log_event"),
        ("payments.ledger", "Ledger"),
    ]
    contract = contract_with_host_symbols("", symbols)
    assert "def log_event(event: str, **fields: object) -> None" in contract
    assert "no stub: signature unknown" in contract
    written = contract_with_host_symbols("# Interface contract\n\nlog_event: audit helper\n", symbols)
    assert "Also used" in written and "Ledger" in written.split("Also used")[1]
    assert "log_event" not in written.split("Also used")[1]


async def test_a_missing_cwd_is_an_error_not_a_sandbox_failure(workspace: Workspace) -> None:
    from forge.toolkit.shell import execute

    shell = ShellSession(workspace, sandbox="off")
    context = ToolContext(workspace=workspace, shell=shell)
    result = await execute(
        context, "python --version", 30, "project"
    )  # the project/ prefix is already implied
    assert not result.ok and "No such folder" in result.content
    assert shell.pending_notice is None
    assert (await execute(context, "python --version", 30, None)).ok
