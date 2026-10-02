"""M10D deterministic gate (spec M10D): vision tools, PDF rendering, synthetic generator, metrics (IoU, field
match), eval runner with overlays and the target-miss rule, labelling helper, sensitive-path rules.
The model-driven parts (view_image, the judge) are in test_live_vision.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from forge.errors import ForgeError
from forge.safety.server_security import ServerSecurity
from forge.toolkit.base import ToolContext
from forge.toolkit.shell import ShellSession
from forge.tools.vision import DrawBoxes, ImageInfo, ImageOps, PdfRender, RunEval, SynthSamples, image_path
from forge.vision import images, pdf
from forge.vision.labeler import create_label_app
from forge.vision.metrics import aggregate, check_targets, normalise, score_sample
from forge.vision.synthetic import DocumentSpec, generate
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace

SPEC = {
    "title": "Clinic Note",
    "fields": {
        "patient_name": ["Asha Rao", "Vikram Sen"],
        "medicine": ["Amoxicillin 500mg", "Cetirizine 10mg"],
    },
    "regions": ["signature", "diagram"],
}


def _text_image(path: Path, angle: float = 0.0) -> Path:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=28)
    for row in range(8):
        draw.text(
            (40, 40 + row * 60), "The quick brown fox jumps over the lazy dog " * 2, fill="black", font=font
        )
    image.rotate(angle, expand=True, fillcolor="white").save(path)
    return path


def test_image_ops_info_and_deskew(tmp_path: Path) -> None:
    skewed = _text_image(tmp_path / "skewed.png", angle=4)
    info = images.info(skewed)
    assert info["size"][0] > 900 and info["sha256"]
    assert abs(images.estimate_skew(images.open_image(skewed)) + 4) <= 1.0  # recovers the rotation
    cropped = images.apply_ops(
        images.open_image(skewed),
        [{"op": "crop", "box": [0, 0, 100, 50]}, {"op": "grayscale"}, {"op": "pad", "pixels": 5}],
    )
    assert cropped.size == (110, 60) and cropped.mode == "L"
    with pytest.raises(ValueError):
        images.apply_ops(images.open_image(skewed), [{"op": "explode"}])


def test_iou_and_compare(tmp_path: Path) -> None:
    assert images.iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert images.iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1 / 3)
    assert images.iou((0, 0, 1, 1), (5, 5, 6, 6)) == 0.0
    a = images.open_image(_text_image(tmp_path / "a.png"))
    composite, overlap = images.compare(a, a)
    assert overlap == pytest.approx(1.0) and composite.width > a.width


def test_pdf_render_and_text_layer(tmp_path: Path) -> None:
    source = _text_image(tmp_path / "page.png")
    pdf_path = tmp_path / "scan.pdf"
    Image.open(source).convert("RGB").save(pdf_path, "PDF", resolution=100)
    assert pdf.page_count(pdf_path) == 1 and pdf.has_text_layer(pdf_path) is False  # an image-only PDF
    pages = pdf.render(pdf_path, tmp_path / "out", dpi=200)
    assert len(pages) == 1 and Image.open(pages[0]).width == pytest.approx(1800, abs=4)  # 9in at 200 dpi
    with pytest.raises(ValueError):
        pdf.render(pdf_path, tmp_path / "out", pages=[5])


def test_synthetic_labels_match_what_was_drawn(tmp_path: Path) -> None:
    paths = generate(
        DocumentSpec.from_dict({**SPEC, "unreadable_chance": 0.0, "noise": 0.0}), tmp_path, 3, seed=3
    )
    assert len(paths) == 3
    label = json.loads((tmp_path / "labels" / "synthetic_001.json").read_text(encoding="utf-8"))
    assert label["synthetic"] is True and set(label["fields"]) == {"patient_name", "medicine"}
    image = Image.open(paths[0]).convert("L")
    for region in label["regions"]:
        inside = image.crop(tuple(int(v) for v in region["box"]))
        dark_inside = sum(inside.histogram()[:100]) / (inside.width * inside.height)
        assert dark_inside > 0.005, region  # the box really contains the drawing


def test_metrics_fields_regions_unreadable_and_targets() -> None:
    label = {
        "fields": {"patient": "Asha Rao", "meds": [{"name": "Amoxicillin", "dose": "500 mg"}]},
        "regions": [{"label": "signature", "page": 1, "box": [100, 100, 300, 160]}],
        "unreadable": ["doctor_name"],
    }
    prediction = {
        "fields": {
            "patient": "asha  rao",
            "meds": [{"name": "Amoxicillin", "dose": "500mg"}],
            "doctor_name": None,
        },
        "regions": [{"label": "signature", "page": 1, "box": [110, 105, 305, 165]}],
    }
    score = score_sample("s1", label, prediction)
    assert score.fields_total == 3 and score.fields_normalised == 3 and score.fields_exact == 1
    assert score.regions_found == 1 and score.unreadable_respected == 1
    guessing = score_sample("s2", label, {"fields": {"doctor_name": "Dr. Guess"}, "regions": []})
    assert guessing.unreadable_respected == 0 and guessing.regions_found == 0
    metrics = aggregate([score, guessing])
    assert metrics["field_normalised"] == 0.5 and metrics["region_recall"] == 0.5
    assert check_targets(metrics, {"field_normalised": 0.9, "max_errors": 0}) == [
        "field_normalised = 0.5 < 0.9"
    ]
    assert normalise("Amoxicillin  500 MG") == normalise("amoxicillin 500mg")


PREDICTOR = """import json, sys
from pathlib import Path
sample = Path(sys.argv[1])
label = json.loads((sample.parent.parent / "labels" / (sample.stem + ".json")).read_text())
fields = dict(label["fields"])
if MODE == "wrong":
    fields = {k: "wrong" for k in fields}
print(json.dumps({"fields": fields, "regions": label["regions"]}))
"""


@pytest.fixture
def eval_workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    base = workspace.path_of("evals/notes")
    generate(DocumentSpec.from_dict(SPEC), base, 4, seed=11)
    (base / "predict.py").write_text("MODE = 'right'\n" + PREDICTOR, encoding="utf-8")
    config = {
        "command": f"& '{sys.executable}' '{(base / 'predict.py').as_posix()}' {{sample}}",
        "targets": {"field_normalised": 0.95, "region_recall": 0.9},
        "sensitive": False,
    }
    (base / "eval.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return workspace


async def test_eval_runner_scores_reports_and_asks_after_repeated_misses(eval_workspace: Workspace) -> None:
    context = ToolContext(workspace=eval_workspace, shell=ShellSession(eval_workspace, sandbox="off"))
    first = await RunEval().run(RunEval.Args(name="notes"), context)
    assert (
        first.ok
        and "All targets met." in first.content
        and "synthetic" in (eval_workspace.forge_dir / "reports" / "eval-1.md").read_text(encoding="utf-8")
    )
    assert any((eval_workspace.forge_dir / "reports" / "eval-1").glob("*.png"))  # overlays

    predictor = eval_workspace.path_of("evals/notes/predict.py")
    predictor.write_text(
        predictor.read_text(encoding="utf-8").replace("MODE = 'right'", "MODE = 'wrong'"), encoding="utf-8"
    )
    results = [await RunEval().run(RunEval.Args(name="notes", subset=2), context) for _ in range(3)]
    assert all(not r.ok for r in results)
    assert "STOP iterating and discuss" not in results[1].content
    assert "STOP iterating and discuss" in results[2].content and "expected" in results[2].content
    history = (
        (eval_workspace.forge_dir / "reports" / "eval-history.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(history) == 4


async def test_vision_tools_paths_and_operations(eval_workspace: Workspace) -> None:
    context = ToolContext(workspace=eval_workspace)
    sample = "evals/notes/samples/synthetic_001.png"
    info = await ImageInfo().run(ImageInfo.Args(path=sample), context)
    assert info.ok and '"size"' in info.content
    ops = await ImageOps().run(
        ImageOps.Args(path=sample, ops=[{"op": "crop", "box": [0, 0, 200, 200]}]), context
    )
    assert ops.ok and ".forge/scratch_images/" in ops.content
    boxes = await DrawBoxes().run(
        DrawBoxes.Args(path=sample, boxes=[{"box": [10, 10, 50, 50], "label": "x"}]), context
    )
    assert boxes.ok
    with pytest.raises(ForgeError):
        image_path(context, ".forge/state.json")
    with pytest.raises(ForgeError):
        image_path(context, "backend/.env")
    synth = await SynthSamples().run(SynthSamples.Args(name="more", spec=SPEC, count=2), context)
    assert synth.ok and len(list(eval_workspace.path_of("evals/more/labels").glob("*.json"))) == 2
    pdf_path = eval_workspace.path_of("evals/notes/scan.pdf")
    Image.open(eval_workspace.path_of(sample)).convert("RGB").save(pdf_path, "PDF", resolution=100)
    rendered = await PdfRender().run(PdfRender.Args(path="evals/notes/scan.pdf", dpi=100), context)
    assert rendered.ok and "image-only" in rendered.content


def test_labelling_helper_is_secure_and_saves_labels(tmp_path: Path) -> None:
    generate(DocumentSpec.from_dict(SPEC), tmp_path / "set", 2)
    security = ServerSecurity(port=8797, token="label-token-0123456789")  # check_secrets: fake
    client = TestClient(create_label_app(tmp_path / "set", security), base_url="http://127.0.0.1:8797")
    assert client.get("/api/samples").status_code == 403
    assert client.get(f"/?t={security.token}", follow_redirects=False).status_code == 303
    samples = client.get("/api/samples").json()
    assert [s["name"] for s in samples] == ["synthetic_001.png", "synthetic_002.png"]
    assert client.get("/sample/synthetic_001.png").status_code == 200
    assert client.get("/sample/..%2F..%2Fsecret.txt").status_code == 404
    body = {
        "fields": {"patient_name": "Asha Rao"},
        "regions": [{"label": "signature", "box": [1, 2, 3, 4]}],
        "unreadable": ["doctor"],
    }
    assert client.post("/api/labels/synthetic_001.png", json=body).json() == {"ok": True}
    saved = json.loads((tmp_path / "set" / "labels" / "synthetic_001.json").read_text(encoding="utf-8"))
    assert saved["verified"] is True and saved["regions"][0]["box"] == [1.0, 2.0, 3.0, 4.0]
    assert "script-src 'self'" in client.get("/").headers["content-security-policy"]


async def test_eval_targets_must_be_numbers(eval_workspace: Workspace) -> None:
    # Seen live: `targets: {fields: []}` crashed run_eval with a TypeError that ended the session.
    config_path = eval_workspace.path_of("evals/notes/eval.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_path.write_text(yaml.safe_dump({**config, "targets": {"fields": []}}), encoding="utf-8")
    context = ToolContext(workspace=eval_workspace, shell=ShellSession(eval_workspace, sandbox="off"))
    result = await RunEval().run(RunEval.Args(name="notes"), context)
    assert not result.ok and "must map metric names to numbers" in result.content
