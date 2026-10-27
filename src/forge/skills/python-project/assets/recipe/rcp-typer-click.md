---
id: rcp-typer-click
type: recipe
title: Command-line tools with Click and Typer
summary: "Commands, options, arguments, groups, exit codes, CliRunner tests and shell completion for Click and Typer."
moods: [robust, clean]
products: [cli tool, developer tool]
tags: [click, typer, cli, exit-codes, completion, testing]
density: any
dependencies: [click]
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: the Click example is executed by tests/test_python_recipes.py; the Typer snippet is not executed (typer is not installed in the build venv)
---

## Command-line tools with Click and Typer

Rules:
- Typer is Click with type hints; pick Typer for a small new tool, Click when you need custom parameter types or plugins.
  Both give `--help`, validation and completion for free, so never parse `sys.argv` by hand.
- The command function parses and prints; the work lives in a plain function you can test without the CLI layer.
- Arguments are required things the command acts on (a file); options are the knobs (`--format`, `--dry-run`). Give
  every option a help text and a default that is safe.
- Use a group (`tool db migrate`, `tool db reset`) once there are three or more commands that share setup.
- Exit codes: 0 success, 1 expected failure (bad input, not found), 2 usage error (Click does this itself). Raise
  `click.ClickException("message")` or `click.UsageError`, do not `print` and `sys.exit` in the middle of a function.
- Errors and diagnostics go to stderr (`click.echo(..., err=True)`), results to stdout so the tool can be piped.
- Test with `CliRunner`: invoke, then assert `exit_code` and `output`; use `runner.isolated_filesystem()` for files.

```python
# runnable
import json
import tempfile
from pathlib import Path

import click
from click.testing import CliRunner


def summarise(lines: list[str]) -> dict[str, int]:
    """The real work, free of any CLI code, so it can be tested on its own."""
    words = sum(len(line.split()) for line in lines)
    return {"lines": len(lines), "words": words}


@click.group()
def cli() -> None:
    """Small text statistics tool."""


@cli.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True
)
@click.option(
    "--min-words", type=click.IntRange(min=0), default=0, help="Fail when the file has fewer words."
)
def stats(path: Path, output_format: str, min_words: int) -> None:
    """Count lines and words in PATH."""
    result = summarise(path.read_text(encoding="utf-8").splitlines())
    if result["words"] < min_words:
        raise click.ClickException(f"only {result['words']} words, expected at least {min_words}")
    if output_format == "json":
        click.echo(json.dumps(result))
    else:
        click.echo(f"{result['lines']} lines, {result['words']} words")


runner = CliRunner()
with tempfile.TemporaryDirectory() as folder:
    sample = Path(folder) / "sample.txt"
    sample.write_text("one two\nthree\n", encoding="utf-8")

    ok = runner.invoke(cli, ["stats", str(sample), "--format", "json"])
    assert ok.exit_code == 0 and json.loads(ok.output) == {"lines": 2, "words": 3}

    too_short = runner.invoke(cli, ["stats", str(sample), "--min-words", "10"])
    assert too_short.exit_code == 1 and "only 3 words" in too_short.output

    missing = runner.invoke(cli, ["stats", str(Path(folder) / "nope.txt")])
    assert missing.exit_code == 2  # Click's usage error for a path that does not exist

    bad_choice = runner.invoke(cli, ["stats", str(sample), "--format", "xml"])
    assert bad_choice.exit_code == 2
```

The same command in Typer, where the signature is the interface (not executed here):

```python
import typer
from pathlib import Path

app = typer.Typer(help="Small text statistics tool.", no_args_is_help=True)


@app.command()
def stats(
    path: Path = typer.Argument(..., exists=True, dir_okay=False),
    as_json: bool = typer.Option(False, "--json", help="Print JSON."),
) -> None: ...


if __name__ == "__main__":
    app()
```

Completion: Typer adds `--install-completion` and `--show-completion`; Click 8 supports it through an environment
variable (`_TOOL_COMPLETE=bash_source tool`), so document the one line for the user's shell. Register the console script
in `pyproject.toml` under `[project.scripts]` so the tool is a real command.

Gotchas:
- A test that calls `main()` directly exits the interpreter; always go through `CliRunner.invoke`.
- `CliRunner` mixes stderr into `output` unless you read `result.stderr`; check which you mean.
- Do not do slow imports at module top-level in a CLI: `--help` should answer in well under a second.
- Boolean flags need an explicit off switch when the default is on (`--color/--no-color`).
- Prompting for secrets: `hide_input=True`, and never accept the secret as a plain option (it lands in shell history).
