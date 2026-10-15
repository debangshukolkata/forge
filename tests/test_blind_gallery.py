"""DIE8: the blind gallery shows neutral page numbers and keeps the model names in a separate key."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "benchmark"))
from blind_gallery import build


def make_run(root: Path, name: str) -> Path:
    shots = root / name / "d01_shots"
    shots.mkdir(parents=True)
    for kind in ("desktop", "phone"):
        (shots / f"{kind}.png").write_bytes(name.encode())
    return root / name


def test_the_gallery_hides_the_arms_and_the_key_names_them(tmp_path: Path) -> None:
    runs = {label: make_run(tmp_path, f"run-{label}") for label in ("A", "B", "C")}
    gallery, key = build("t", runs, tmp_path / "out", seed=3)
    page = gallery.read_text(encoding="utf-8")
    assert "Page 1" in page and "Page 3" in page
    assert "run-A" not in page and "gemini" not in page.lower() and ">A<" not in page
    text = key.read_text(encoding="utf-8")
    assert all(f"({name})" in text for name in ("run-A", "run-B", "run-C"))
    again = build("t", runs, tmp_path / "out2", seed=3)[1].read_text(encoding="utf-8")
    assert again == text  # the same seed keeps the same page numbers
    assert (tmp_path / "out" / "d01_2_desktop.png").is_file()
