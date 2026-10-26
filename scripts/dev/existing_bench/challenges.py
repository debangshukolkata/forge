"""The ten existing-codebase challenges (TODO C22). Documentation: docs/CODE_BENCHMARK_EXISTING.md.

Six on pallets/click 8.1.8 (commit d4ecb8a), four on fastapi/full-stack-fastapi-template (commit f4bcfab).
Each challenge names real files, a model-independent pass check under checks/, and, where it helps, a known solution
(`reference`) so `selftest` can prove the check passes on a correct change and fails before the work."""

from __future__ import annotations

from .harness import Challenge, Edit
from .template_references import T02_REFERENCE, T03_REFERENCE, T03_REFERENCE_FILES, T04_REFERENCE

APPROVAL = "\n\nYou may install packages with `python -m pip install ...` in this project's environment: that is approved."

# ---------------------------------------------------------------- click

E01_REFERENCE = (
    Edit(
        "src/click/types.py",
        'if norm in {"1", "true", "t", "yes", "y", "on"}:',
        'if norm in {"1", "true", "t", "yes", "y", "on", "enable", "enabled"}:',
    ),
    Edit(
        "src/click/types.py",
        'if norm in {"0", "false", "f", "no", "n", "off"}:',
        'if norm in {"0", "false", "f", "no", "n", "off", "disable", "disabled"}:',
    ),
)

E02_SEED = Edit(
    "src/click/utils.py",
    "        if total_length > max_length:  # too long, truncate",
    "        if total_length >= max_length:  # too long, truncate",
)

E03_MUTANTS = (
    Edit("src/click/formatting.py", "rv.sort(key=lambda x: x[0])", "rv.sort(key=lambda x: -x[0])"),
    Edit("src/click/formatting.py", 'if prefix == "/":', 'if prefix == "-":'),
    Edit(
        "src/click/formatting.py",
        'return ", ".join(x[1] for x in rv), any_prefix_is_slash',
        'return " ".join(x[1] for x in rv), any_prefix_is_slash',
    ),
    Edit(
        "src/click/formatting.py",
        "widths[idx] = max(widths.get(idx, 0), term_len(col))",
        "widths[idx] = min(widths.get(idx, 0), term_len(col))",
    ),
    Edit(
        "src/click/formatting.py",
        "return tuple(y for x, y in sorted(widths.items()))",
        "return tuple(y for x, y in sorted(widths.items(), reverse=True))",
    ),
    Edit(
        "src/click/formatting.py",
        'yield row + ("",) * (col_count - len(row))',
        'yield row + ("",) * (col_count - len(row) - 1)',
    ),
)

E03_REFERENCE_TEST = """from click.formatting import iter_rows, join_options, measure_table


def test_join_options_orders_by_prefix_length():
    assert join_options(["--long", "-l"]) == ("-l, --long", False)


def test_join_options_reports_slash_prefix():
    assert join_options(["/debug", "--debug"]) == ("/debug, --debug", True)


def test_join_options_single_dash_is_not_slash():
    assert join_options(["-x"]) == ("-x", False)


def test_measure_table_takes_widest_cell_per_column():
    assert measure_table([("a", "bbb"), ("cc", "d")]) == (2, 3)


def test_measure_table_ignores_ansi_codes():
    assert measure_table([("\\x1b[31mred\\x1b[0m", "x")]) == (3, 1)


def test_iter_rows_pads_short_rows():
    assert list(iter_rows([("a",), ("b", "c")], 2)) == [("a", ""), ("b", "c")]


def test_iter_rows_leaves_full_rows():
    assert list(iter_rows([("a", "b")], 2)) == [("a", "b")]
"""

E04_REFERENCE = (
    Edit(
        "src/click/termui.py",
        "def _build_prompt(",
        '''def _read_line(read_func: t.Callable[[str], str], text: str, err: bool, hide_input: bool = False) -> str:
    """Write the prompt, read one line, turn Ctrl-C and end of input into Abort."""
    try:
        # Write the prompt separately so that we get nice
        # coloring through colorama on Windows
        echo(text.rstrip(" "), nl=False, err=err)
        # Echo a space to stdout to work around an issue where
        # readline causes backspace to clear the whole line.
        return read_func(" ")
    except (KeyboardInterrupt, EOFError):
        # getpass doesn't print a newline if the user aborts input with ^C.
        if hide_input:
            echo(None, err=err)
        raise Abort() from None


def _build_prompt(''',
    ),
    Edit(
        "src/click/termui.py",
        """        f = hidden_prompt_func if hide_input else visible_prompt_func
        try:
            # Write the prompt separately so that we get nice
            # coloring through colorama on Windows
            echo(text.rstrip(" "), nl=False, err=err)
            # Echo a space to stdout to work around an issue where
            # readline causes backspace to clear the whole line.
            return f(" ")
        except (KeyboardInterrupt, EOFError):
            # getpass doesn't print a newline if the user aborts input with ^C.
            # Allegedly this behavior is inherited from getpass(3).
            # A doc bug has been filed at https://bugs.python.org/issue24711
            if hide_input:
                echo(None, err=err)
            raise Abort() from None
""",
        """        f = hidden_prompt_func if hide_input else visible_prompt_func
        return _read_line(f, text, err, hide_input)
""",
    ),
    Edit(
        "src/click/termui.py",
        """        try:
            # Write the prompt separately so that we get nice
            # coloring through colorama on Windows
            echo(prompt.rstrip(" "), nl=False, err=err)
            # Echo a space to stdout to work around an issue where
            # readline causes backspace to clear the whole line.
            value = visible_prompt_func(" ").lower().strip()
        except (KeyboardInterrupt, EOFError):
            raise Abort() from None
""",
        """        value = _read_line(visible_prompt_func, prompt, err).lower().strip()
""",
    ),
)

E05_REFERENCE = (
    Edit(
        "src/click/decorators.py",
        """            metadata: t.Optional[types.ModuleType]

            try:
                from importlib import metadata
            except ImportError:
                # Python < 3.8
                import importlib_metadata as metadata  # type: ignore

            try:
                version = metadata.version(package_name)  # type: ignore
            except metadata.PackageNotFoundError:  # type: ignore
""",
        """            from importlib import metadata

            try:
                version = metadata.version(package_name)
            except metadata.PackageNotFoundError:
""",
    ),
    Edit("pyproject.toml", 'requires-python = ">=3.7"', 'requires-python = ">=3.8"'),
    Edit("pyproject.toml", "    \"importlib-metadata; python_version < '3.8'\",\n", ""),
)

E06_REFERENCE = (
    Edit(
        "src/click/types.py",
        "        self.choices = choices\n        self.case_sensitive = case_sensitive\n",
        "        self.choices = choices\n        self.case_sensitive = case_sensitive\n"
        "        self._exact = {choice: choice for choice in choices}\n"
        "        self._folded = {choice.casefold(): choice for choice in choices}\n",
    ),
    Edit(
        "src/click/types.py",
        "        normed_value = value\n        normed_choices = {choice: choice for choice in self.choices}\n",
        "        if ctx is None or ctx.token_normalize_func is None:\n"
        "            # Fast path: the lookup tables were built once in __init__.\n"
        "            if self.case_sensitive:\n"
        "                if value in self._exact:\n"
        "                    return self._exact[value]\n"
        "            elif isinstance(value, str) and value.casefold() in self._folded:\n"
        "                return self._folded[value.casefold()]\n\n"
        "        normed_value = value\n        normed_choices = {choice: choice for choice in self.choices}\n",
    ),
)

# ---------------------------------------------------------------- fastapi template

T01_SEED = Edit(
    "backend/app/api/routes/items.py",
    """    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item
""",
    """    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
""",
)

CHALLENGES: tuple[Challenge, ...] = (
    Challenge(
        id="E01",
        repo="click",
        title="Boolean words enable/disable (small feature)",
        tier="1 small feature",
        brief=(
            "Boolean options and prompts accept yes/no style words today (true, yes, on and so on). Our users also write "
            "`enable`, `enabled`, `disable` and `disabled` on the command line. Make the boolean type accept those four words as well "
            "(any letter case, surrounding spaces ignored). Every word that works now must keep working and the error for an unknown word "
            "must stay exactly as it is. Add tests, and add a line to the changelog."
        ),
        expected_files=("src/click/types.py", "tests/test_types.py", "CHANGES.rst"),
        check="check_e01.py",
        reference=E01_REFERENCE,
    ),
    Challenge(
        id="E02",
        repo="click",
        title="Short help cut when it fits (seeded bug)",
        tier="2 seeded bug",
        brief=(
            "The short help that click builds from a command's help text is cut and ends in `...` when the text is exactly as long as the allowed "
            "length, although it fits. For example with a limit of 45, a 45 character text without a full stop is shortened. "
            "Find the cause and fix it, and make sure a test covers it."
        ),
        expected_files=("src/click/utils.py", "tests/test_utils.py"),
        check="check_e02.py",
        seeded=(E02_SEED,),
        reference=(Edit(E02_SEED.path, E02_SEED.new, E02_SEED.old),),
    ),
    Challenge(
        id="E03",
        repo="click",
        title="Missing tests for the help-table helpers",
        tier="3 missing test",
        brief=(
            "The helpers `join_options`, `measure_table` and `iter_rows` in the formatting module have no direct tests. Write tests "
            "that pin down what they do today (ordering, the slash flag, widths with colour codes, padding of short rows). "
            "Do not change any source file under src/."
        ),
        expected_files=("src/click/formatting.py", "tests/test_formatting.py"),
        check=None,
        mutants=E03_MUTANTS,
        min_killed=5,
        require_new_tests=True,
        forbid_source_changes=True,
        reference_files={"tests/test_formatting_helpers.py": E03_REFERENCE_TEST},
    ),
    Challenge(
        id="E04",
        repo="click",
        title="Share the prompt reading code (refactor, tests stay green)",
        tier="4 refactor",
        brief=(
            "`prompt()` and `confirm()` in the terminal UI module each contain their own copy of the code that writes the prompt, reads a line "
            "and turns Ctrl-C or end of input into `Abort`. Remove the duplication by sharing one helper. Behaviour must not change at all, "
            "including the extra newline when a hidden prompt is aborted. Every existing test must still pass."
        ),
        expected_files=("src/click/termui.py", "tests/test_termui.py"),
        check="check_e04.py",
        reference=E04_REFERENCE,
    ),
    Challenge(
        id="E05",
        repo="click",
        title="Drop Python 3.7 (dependency / API upgrade)",
        tier="5 upgrade",
        brief=(
            "We are dropping support for Python 3.7. Raise the minimum Python version to 3.8 and remove everything that only exists for 3.7: "
            "the backport import and the dependency that goes with it. `version_option` must keep working. Add a changelog line."
        ),
        expected_files=("src/click/decorators.py", "pyproject.toml", "CHANGES.rst"),
        check="check_e05.py",
        reference=E05_REFERENCE,
    ),
    Challenge(
        id="E06",
        repo="click",
        title="Choice conversion is slow with big lists (performance)",
        tier="6 performance",
        brief=(
            "Options with a very large `Choice` list are slow: converting 3000 values against a 20000-entry Choice takes several seconds. "
            "Make the conversion fast without changing any result, including case-insensitive choices and a context `token_normalize_func`. "
            "Add a test that would catch a regression."
        ),
        expected_files=("src/click/types.py", "tests/test_types.py"),
        check="check_e06.py",
        reference=E06_REFERENCE,
    ),
    Challenge(
        id="T01",
        repo="fastapi-template",
        title="Item readable by another user (security fix)",
        tier="7 security",
        brief=(
            "A tester reports that a normal user who changes the id in the address can open an item that belongs to someone else. "
            "Check the item endpoints, fix what is wrong and add a test that proves a normal user gets 403 for another user's item "
            "while the owner and a superuser still succeed."
        ),
        expected_files=("backend/app/api/routes/items.py", "backend/tests/api/routes/test_items.py"),
        check="check_t01.py",
        app_folder="backend",
        seeded=(T01_SEED,),
        reference=(Edit(T01_SEED.path, T01_SEED.new, T01_SEED.old),),
        run_existing_suite=False,
        needs_template_python=True,
    ),
    Challenge(
        id="T02",
        repo="fastapi-template",
        title="Type and docstring pass on crud and utils (type-hint / doc pass)",
        tier="8 type and doc pass",
        brief=(
            "Bring `app/crud.py` up to the standard of the rest of the backend, which runs `mypy --strict`: no function may return `Any` where a "
            "concrete type is known, and every public function needs a short docstring saying what it does and what it returns. "
            "Do not change behaviour. mypy must not report more errors on `app/crud.py` and `app/utils.py` than it does now."
        ),
        expected_files=("backend/app/crud.py", "backend/app/utils.py"),
        check="check_t02.py",
        app_folder="backend",
        reference=T02_REFERENCE,
        run_existing_suite=False,
        needs_template_python=True,
        mypy_paths=("app/crud.py", "app/utils.py"),
    ),
    Challenge(
        id="T03",
        repo="fastapi-template",
        title="Items remember when they were last changed (multi-file change)",
        tier="9 multi-file change",
        brief=(
            "Show when an item was last changed. Add an `updated_at` timestamp to items: set when the item is created, refreshed on every "
            "update made through the API, and returned in the item responses. The database schema is managed with migrations, so add the migration too. "
            "Add tests."
        ),
        expected_files=(
            "backend/app/models.py",
            "backend/app/api/routes/items.py",
            "backend/app/alembic/versions",
            "backend/tests/api/routes/test_items.py",
        ),
        check="check_t03.py",
        app_folder="backend",
        reference=T03_REFERENCE,
        reference_files=T03_REFERENCE_FILES,
        run_existing_suite=False,
        needs_template_python=True,
        require_new_tests=True,
    ),
    Challenge(
        id="T04",
        repo="fastapi-template",
        title="Duplicate accounts (vague brief, needs exploring)",
        tier="10 vague brief",
        brief=(
            "Support tells me the same person can end up with two accounts if they type their email differently. "
            "Look into it and fix whatever is wrong. Tell me what you found."
        ),
        expected_files=(
            "backend/app/crud.py",
            "backend/app/api/routes/users.py",
            "backend/app/api/routes/login.py",
        ),
        check="check_t04.py",
        app_folder="backend",
        reference=T04_REFERENCE,
        run_existing_suite=False,
        needs_template_python=True,
    ),
)

BY_ID = {c.id: c for c in CHALLENGES}
