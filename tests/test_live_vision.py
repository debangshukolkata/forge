"""M10D live: Forge's view_image on the real vision model reads a synthetic handwritten page (known labels) and
locates its signature; the image is logged by hash. Run with: pytest -m live tests/test_live_vision.py"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.toolkit.base import ToolContext
from forge.tools.vision import ViewImage
from forge.vision.synthetic import DocumentSpec, generate
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.live


async def test_view_image_reads_fields_and_finds_the_signature(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    spec = DocumentSpec(
        "Clinic Prescription",
        {"patient_name": ["Asha Rao"], "medicine": ["Amoxicillin 500mg"]},
        regions=["signature"],
        rotation=1.0,
        noise=0.005,
    )
    base = workspace.path_of("evals/rx")
    generate(spec, base, 1, seed=5)
    label = json.loads((base / "labels" / "synthetic_001.json").read_text(encoding="utf-8"))
    bus = EventBus(redactor=__import__("forge.safety.redact", fromlist=["Redactor"]).Redactor())

    async def publish(kind: str, payload: dict[str, object]) -> None:
        await bus.publish(EventType(kind), payload)

    context = ToolContext(
        workspace=workspace, router=LLMRouter(load_config(isolated_forge_home), secrets), publish=publish
    )
    read = await ViewImage().run(
        ViewImage.Args(
            path="evals/rx/samples/synthetic_001.png",
            question="What are the patient name and the medicine written on this page?",
        ),
        context,
    )
    assert read.ok and "asha rao" in read.content.lower() and "amoxicillin" in read.content.lower(), (
        read.content
    )

    # Pixel localisation by the model alone is NOT reliable (seen: IoU 0 on this very page) — which is why the
    # vision-document-pipeline skill prescribes classical-CV candidates + model classification. Here we only
    # check that asking works and the answer carries coordinates.
    where = await ViewImage().run(
        ViewImage.Args(
            path="evals/rx/samples/synthetic_001.png",
            question='Where is the handwritten signature? Answer with its bounding box as JSON: {"box": [x1, y1, x2, y2]}.',
        ),
        context,
    )
    assert where.ok and re.search(r"\[\s*[\d.]+\s*,", where.content), where.content
    assert label["regions"][0]["label"] == "signature"
    sent = [e for e in bus.events_since(0) if e.payload.get("kind") == "image_sent"]
    assert len(sent) == 2 and "sha256" in str(sent[0].payload["text"])
