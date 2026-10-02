"""Tables the app reads its database credentials from (spec §9.5.1, D-160). Forge never reads their rows: they
join the database deny-list at session start. Found by reading the ORIGINAL repository (read-only) for code
that loads credentials from a table into environment variables."""

from __future__ import annotations

from pathlib import Path

from forge.db.data_facts import extract_sql_usage
from forge.db.python_index import ModuleFacts, parse_module
from forge.workspace.copy_repo import iter_source_files
from forge.workspace.ignore import IgnoreRules


def credential_tables(repo_path: Path | str, app_subfolder: str) -> list[str]:
    repo = Path(repo_path)
    if not repo.is_dir():
        return []
    rules = IgnoreRules(repo)
    modules: list[ModuleFacts] = []
    for relative, _source, is_link in iter_source_files(repo, app_subfolder, rules):
        if is_link or rules.is_secret(relative) or not relative.endswith(".py"):
            continue
        parsed = parse_module(repo, relative, app_subfolder)  # secret files are never parsed
        if parsed is not None:
            modules.append(parsed)
    _, bootstraps = extract_sql_usage(modules)
    return sorted({t.lower() for boot in bootstraps for t in boot.tables})
