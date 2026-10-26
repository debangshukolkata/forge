"""C8: imports that do not resolve are found before a task closes; guarded and local imports are left alone."""

from __future__ import annotations

import sys
from pathlib import Path

from forge.tools.import_check import import_note, import_problems


def _project(tmp_path: Path, **files: str) -> Path:
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_a_clean_project_has_no_findings(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        **{
            "app.py": "import json\nfrom pathlib import Path\nfrom helpers import double\nimport os.path\n",
            "helpers.py": "def double(x):\n    return x * 2\n",
        },
    )
    assert import_problems(root, sys.executable) == []


def test_an_invented_package_is_reported_with_its_line(tmp_path: Path) -> None:
    root = _project(tmp_path, **{"app.py": "import json\nimport flask_magic_forms\n"})
    assert import_problems(root, sys.executable) == ["app.py:2: no module named 'flask_magic_forms'"]


def test_an_invented_name_in_a_real_library_is_reported(tmp_path: Path) -> None:
    root = _project(
        tmp_path, **{"app.py": "from pathlib import Path, PathMagic\nfrom os import path, getcwd\n"}
    )
    assert import_problems(root, sys.executable) == ["app.py:1: 'pathlib' has no name 'PathMagic'"]


def test_submodules_imported_by_name_are_fine(tmp_path: Path) -> None:
    root = _project(tmp_path, **{"app.py": "from xml import etree\nfrom importlib import util\n"})
    assert import_problems(root, sys.executable) == []


def test_optional_and_type_checking_imports_are_skipped(tmp_path: Path) -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        "try:\n    import fancy_speedups\nexcept ImportError:\n    fancy_speedups = None\n"
        "if TYPE_CHECKING:\n    from nowhere import Thing\n"
    )
    assert import_problems(_project(tmp_path, **{"app.py": source}), sys.executable) == []


def test_missing_local_module_is_reported_but_local_names_are_not_executed(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        **{
            "app.py": "import helpers\nimport missing_local\n",
            "helpers.py": "raise RuntimeError('must not run during the check')\n",
        },
    )
    assert import_problems(root, sys.executable) == ["app.py:2: no module named 'missing_local'"]


def test_virtualenv_and_unparseable_files_are_ignored(tmp_path: Path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "junk.py").write_text("import not_a_real_thing\n", encoding="utf-8")
    root = _project(tmp_path, **{"broken.py": "def (:\n", "ok.py": "import json\n"})
    assert import_problems(root, sys.executable) == []


def test_a_python_that_cannot_run_gives_no_findings(tmp_path: Path) -> None:
    root = _project(tmp_path, **{"app.py": "import flask_magic_forms\n"})
    assert import_problems(root, str(tmp_path / "no-such-python.exe")) == []


def test_note_lists_findings_and_caps_them() -> None:
    note = import_note([f"a.py:{n}: no module named 'x{n}'" for n in range(1, 12)])
    assert "Not accepted" in note and "x1'" in note and "and 3 more" in note


def test_names_found_anywhere_in_the_project_are_treated_as_local(tmp_path: Path) -> None:
    (tmp_path / "src" / "shop").mkdir(parents=True)
    (tmp_path / "src" / "shop" / "cart.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_cart.py").write_text(
        "import json, shop\nfrom shop.cart import X\nimport shop.cart\n", encoding="utf-8"
    )
    assert import_problems(tmp_path, sys.executable) == []


def test_only_the_named_files_are_read_for_imports(tmp_path: Path) -> None:
    (tmp_path / "old.py").write_text("import long_standing_host_dependency\n", encoding="utf-8")
    (tmp_path / "new.py").write_text("import json\nimport invented_by_the_model\n", encoding="utf-8")
    problems = import_problems(tmp_path, sys.executable, only={(tmp_path / "new.py").resolve()})
    assert problems == ["new.py:2: no module named 'invented_by_the_model'"]
    assert import_problems(tmp_path, sys.executable, only=set()) == []


def test_an_invented_attribute_of_a_real_module_is_reported_with_its_line(tmp_path: Path) -> None:
    source = (
        "import os\nimport json as js\nfrom os import path\nfrom xml import etree\n"
        "a = os.getcwd()\nb = js.dumps({})\nc = os.pathh.join('a')\nd = js.loadz('{}')\n"
        "e = path.joinn('a', 'b')\nf = etree.ElementTree.parse\ng = os.path.exists('x')\n"
    )
    root = _project(tmp_path, **{"app.py": source})
    assert import_problems(root, sys.executable) == [
        "app.py:7: 'os' has no attribute 'pathh'",
        "app.py:8: 'json' has no attribute 'loadz'",
        "app.py:9: 'os.path' has no attribute 'joinn'",
    ]


def test_attribute_checks_leave_shadowed_names_classes_and_submodules_alone(tmp_path: Path) -> None:
    source = (
        "import datetime\nimport os\nimport logging\n"
        "def run(os):\n    return os.anything_at_all\n"
        "x = datetime.datetime.now().whatever\n"  # a class and an instance: not checked
        "y = logging.handlers\n"  # a submodule that is only importable, not yet loaded
    )
    root = _project(tmp_path, **{"app.py": source})
    assert import_problems(root, sys.executable) == []
