import json
import subprocess
import sys
from pathlib import Path

import wordstat

SCRIPT = Path(wordstat.__file__)
TEXT = "the cat and the hat. The cat's hat, the CAT! and 'quoted' words 42 42 42\n"


def run(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def test_file_input_default_output(tmp_path: Path) -> None:
    source = tmp_path / "in.txt"
    source.write_text(TEXT, encoding="utf-8")
    result = run([str(source), "--top", "3"])
    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert lines == ["42 3", "the 3", "and 2"]  # case sensitive: "The" and "CAT" are separate words


def test_case_sensitivity_and_ignore_case() -> None:
    sensitive = run(["--json"], stdin="Cat cat CAT cat").stdout
    assert json.loads(sensitive)["unique_words"] == 3
    folded = json.loads(run(["--json", "--ignore-case"], stdin="Cat cat CAT cat").stdout)
    assert folded == {"total_words": 4, "unique_words": 1, "top": [{"word": "cat", "count": 4}]}


def test_stdin_dash_and_apostrophes() -> None:
    result = json.loads(run(["-", "--json", "--ignore-case"], stdin="'quoted' cat's don't ''").stdout)
    words = {entry["word"] for entry in result["top"]}
    assert words == {"quoted", "cat's", "don't"}
    assert result["total_words"] == 3


def test_ties_are_alphabetical_and_top_limits() -> None:
    result = json.loads(run(["--json", "--top", "2"], stdin="b a c b a c d").stdout)
    assert result["top"] == [{"word": "a", "count": 2}, {"word": "b", "count": 2}]
    assert result["total_words"] == 7 and result["unique_words"] == 4


def test_min_length_applies_to_totals() -> None:
    result = json.loads(run(["--json", "--min-length", "3"], stdin="a an the them them").stdout)
    assert result["total_words"] == 3 and result["unique_words"] == 2
    assert result["top"][0] == {"word": "them", "count": 2}


def test_default_top_is_ten() -> None:
    words = " ".join(f"w{index:02d}" for index in range(15))
    assert len(run([], stdin=words).stdout.strip().splitlines()) == 10


def test_plain_output_format() -> None:
    assert run([], stdin="x x y").stdout.splitlines() == ["x 2", "y 1"]


def test_missing_file_exits_2_with_message() -> None:
    result = run(["definitely-not-here.txt"])
    assert result.returncode == 2 and result.stderr.strip() and not result.stdout.strip()


def test_bad_numbers_exit_2() -> None:
    assert run(["--top", "0"], stdin="a").returncode == 2
    assert run(["--min-length", "0"], stdin="a").returncode == 2


def test_main_function_returns_codes(capsys, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import io

    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"hi hi"), encoding="utf-8"))  # has .buffer too
    assert wordstat.main(["--top", "1"]) == 0
    assert capsys.readouterr().out.strip() == "hi 2"
    assert wordstat.main(["nope-nope.txt"]) == 2


def test_empty_input() -> None:
    assert json.loads(run(["--json"], stdin="").stdout) == {"total_words": 0, "unique_words": 0, "top": []}
