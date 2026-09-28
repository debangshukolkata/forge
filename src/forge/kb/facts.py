"""Collects every deterministic fact about a repository's Python app (spec §11.3, "deterministic first")."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from forge.kb.data_facts import (
    BootstrapFact,
    ModelFact,
    SqlScripts,
    SqlUsage,
    extract_env_keys,
    extract_models,
    extract_sql_usage,
    parse_sql_scripts,
)
from forge.kb.flask_smorest import BlueprintFact, Endpoint, extract_blueprints, extract_endpoints
from forge.kb.langgraph_index import GraphFact, extract_graphs
from forge.kb.project_facts import CommandFacts, StackFacts, command_facts, stack_facts
from forge.kb.python_index import ModuleFacts, parse_module
from forge.workspace.copy_repo import iter_source_files
from forge.workspace.ignore import IgnoreRules


@dataclass
class RepoFacts:
    repo_path: str
    app_subfolder: str
    file_hashes: dict[str, str]  # every non-ignored, non-secret file -> sha256
    modules: list[ModuleFacts]
    blueprints: list[BlueprintFact]
    endpoints: list[Endpoint]
    models: list[ModelFact]
    sql_usage: list[SqlUsage]
    bootstraps: list[BootstrapFact]
    env_keys: dict[str, list[str]]
    sql_scripts: SqlScripts
    graphs: list[GraphFact]
    stack: StackFacts
    commands: CommandFacts
    unparsable: list[str] = field(default_factory=list)

    def packages(self) -> dict[str, list[ModuleFacts]]:
        """Dotted package -> its modules (a module's package is its parent; a package's is itself)."""
        grouped: dict[str, list[ModuleFacts]] = {}
        for facts in self.modules:
            package = facts.module if facts.path.endswith("__init__.py") else facts.module.rpartition(".")[0]
            grouped.setdefault(package or "(top level)", []).append(facts)
        return dict(sorted(grouped.items()))

    def package_of(self, path: str) -> str | None:
        for package, modules in self.packages().items():
            if any(m.path == path for m in modules):
                return package
        return None


def collect_facts(repo_path: Path, app_subfolder: str) -> RepoFacts:
    """Reads the ORIGINAL repository (read-only). Secret files are neither hashed for content nor parsed."""
    rules = IgnoreRules(repo_path)
    hashes: dict[str, str] = {}
    modules: list[ModuleFacts] = []
    unparsable: list[str] = []
    for relative, source, is_link in iter_source_files(repo_path, app_subfolder, rules):
        if is_link or rules.is_secret(relative):
            continue
        hashes[relative] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
        if relative.endswith(".py"):
            parsed = parse_module(repo_path, relative, app_subfolder)
            if parsed is None:
                unparsable.append(relative)
            else:
                modules.append(parsed)
    blueprints = extract_blueprints(modules)
    usage, bootstraps = extract_sql_usage(modules)
    stack = stack_facts(repo_path, repo_path / app_subfolder, app_subfolder)
    return RepoFacts(
        repo_path=str(repo_path),
        app_subfolder=app_subfolder,
        file_hashes=hashes,
        modules=modules,
        blueprints=blueprints,
        endpoints=extract_endpoints(modules, blueprints),
        models=extract_models(modules),
        sql_usage=usage,
        bootstraps=bootstraps,
        env_keys=extract_env_keys(modules),
        sql_scripts=parse_sql_scripts(repo_path, app_subfolder),
        graphs=extract_graphs(modules),
        stack=stack,
        commands=command_facts(repo_path, app_subfolder, stack),
        unparsable=unparsable,
    )


def layout_rules(facts: RepoFacts) -> list[str]:
    """Where each kind of code lives, derived from where the facts were found."""

    def folders(paths: list[str]) -> str:
        unique = sorted({str(PurePosixPath(p).parent) for p in paths})
        return ", ".join(f"`{u}/`" for u in unique[:4]) + (" …" if len(unique) > 4 else "")

    rules = []
    if facts.blueprints:
        rules.append(f"Blueprints/routes: {folders([b.path for b in facts.blueprints])}")
    schema_files = [
        m.path for m in facts.modules if any(s.bases and "Schema" in " ".join(s.bases) for s in m.symbols)
    ]
    if schema_files:
        rules.append(f"Marshmallow schemas: {folders(schema_files)}")
    service_files = [
        m.path for m in facts.modules if "service" in m.path.lower() and "test" not in m.path.lower()
    ]
    if service_files:
        rules.append(f"Services: {folders(service_files)}")
    repo_files = [u.path for u in facts.sql_usage if not u.in_tests]
    if repo_files:
        rules.append(f"Raw SQL / repositories: {folders(repo_files)}")
    if facts.models:
        rules.append(f"SQLAlchemy models: {folders([m.path for m in facts.models])}")
    if facts.graphs:
        rules.append(f"LangGraph graphs: {folders([g.path for g in facts.graphs])}")
    if facts.sql_scripts.folder:
        rules.append(
            f"SQL scripts: `{facts.sql_scripts.folder}/` named {facts.sql_scripts.naming or 'freely'}"
            + (
                f" (next: {facts.sql_scripts.next_name_example})"
                if facts.sql_scripts.next_name_example
                else ""
            )
        )
    test_files = [m.path for m in facts.modules if m.path.split("/")[-1].startswith("test_")]
    if test_files:
        rules.append(f"Tests: {folders(test_files)}")
    return rules
