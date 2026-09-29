"""D-137/D-138 phase 1: detecting an existing Node/React app in a Mode A app folder."""

from __future__ import annotations

import json
from pathlib import Path

from forge.workspace.nodeenv import detect_node_environment, find_node_app_candidates


def _write_package_json(app_dir: Path, scripts: dict[str, str] | None = None, **extra: object) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {"name": "app", "version": "1.0.0", "scripts": scripts or {}}
    data.update(extra)
    (app_dir / "package.json").write_text(json.dumps(data), encoding="utf-8")


def test_no_package_json_means_no_node_environment(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    assert detect_node_environment(app_dir) is None


def test_detects_npm_by_default_and_reads_real_script_names(tmp_path: Path, monkeypatch) -> None:
    app_dir = tmp_path / "app"
    _write_package_json(
        app_dir,
        scripts={"build": "vite build", "test": "vitest run", "lint": "eslint src", "start": "vite"},
    )
    monkeypatch.setattr("forge.workspace.nodeenv.shutil.which", lambda name: "C:\\node\\node.exe")

    env = detect_node_environment(app_dir)

    assert env is not None
    assert env.package_manager == "npm"
    assert env.node == "C:\\node\\node.exe"
    assert env.install_command == "npm install"
    assert env.build_command == "npm run build"
    assert env.test_command == "npm run test"
    assert env.lint_command == "npm run lint"
    assert env.typecheck_command is None  # the repo defines no typecheck/type-check script


def test_package_manager_follows_the_lockfile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("forge.workspace.nodeenv.shutil.which", lambda name: "/usr/bin/node")
    yarn_app = tmp_path / "yarn_app"
    _write_package_json(yarn_app, scripts={"build": "webpack"})
    (yarn_app / "yarn.lock").write_text("", encoding="utf-8")
    pnpm_app = tmp_path / "pnpm_app"
    _write_package_json(pnpm_app, scripts={"build": "webpack"})
    (pnpm_app / "pnpm-lock.yaml").write_text("", encoding="utf-8")
    npm_app = tmp_path / "npm_app"
    _write_package_json(npm_app, scripts={"build": "webpack"})
    (npm_app / "package-lock.json").write_text("", encoding="utf-8")

    assert detect_node_environment(yarn_app).package_manager == "yarn"  # type: ignore[union-attr]
    assert detect_node_environment(yarn_app).build_command == "yarn build"  # type: ignore[union-attr]
    assert detect_node_environment(pnpm_app).package_manager == "pnpm"  # type: ignore[union-attr]
    assert detect_node_environment(pnpm_app).build_command == "pnpm run build"  # type: ignore[union-attr]
    assert detect_node_environment(npm_app).package_manager == "npm"  # type: ignore[union-attr]


def test_no_node_binary_means_no_environment(tmp_path: Path, monkeypatch) -> None:
    app_dir = tmp_path / "app"
    _write_package_json(app_dir, scripts={"build": "vite build"})
    monkeypatch.setattr("forge.workspace.nodeenv.shutil.which", lambda name: None)

    assert detect_node_environment(app_dir) is None


def test_typecheck_command_accepts_either_conventional_script_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("forge.workspace.nodeenv.shutil.which", lambda name: "/usr/bin/node")
    app_dir = tmp_path / "app"
    _write_package_json(app_dir, scripts={"type-check": "tsc --noEmit"})

    env = detect_node_environment(app_dir)

    assert env is not None and env.typecheck_command == "npm run type-check"


def test_find_node_app_candidates_ranks_folders_with_build_or_start_scripts_first(tmp_path: Path) -> None:
    _write_package_json(tmp_path / "tooling", scripts={"lint": "eslint ."})
    _write_package_json(tmp_path / "frontend", scripts={"build": "vite build", "start": "vite"})

    candidates = find_node_app_candidates(tmp_path)

    assert candidates[0] == "frontend"
    assert "tooling" in candidates


def test_find_node_app_candidates_ignores_node_modules(tmp_path: Path) -> None:
    _write_package_json(tmp_path / "frontend", scripts={"build": "vite build"})
    _write_package_json(tmp_path / "frontend" / "node_modules" / "some-dep", scripts={})

    candidates = find_node_app_candidates(tmp_path)

    assert candidates == ["frontend"]
