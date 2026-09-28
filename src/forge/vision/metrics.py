"""Eval metrics (spec §13A.3), generic over document types:

- fields: exact and normalised match per leaf field; nested dicts are flattened to dotted paths, lists are
  matched item by item (list[i].key);
- regions: IoU per label (best predicted box of the same label), recall at an IoU threshold;
- unreadable: for fields the label marks unreadable, the prediction must say so (null / "unreadable") rather
  than guess — the "said unreadable instead of guessing" rate.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from forge.vision.images import iou

UNREADABLE = {"", "unreadable", "illegible", "unknown", "none", "null", "n/a"}


def normalise(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).lower().strip()
    text = re.sub(r"[\s_]+", " ", text)
    text = re.sub(r"[^\w .%/+-]", "", text)
    text = re.sub(r"(\d)\s+(mg|ml|mcg|g|kg|%)\b", r"\1\2", text)  # "500 mg" == "500mg"
    return text.strip()


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        items: dict[str, Any] = {}
        for key, inner in value.items():
            items.update(flatten(inner, f"{prefix}.{key}" if prefix else str(key)))
        return items
    if isinstance(value, list):
        items = {}
        for index, inner in enumerate(value):
            items.update(flatten(inner, f"{prefix}[{index}]"))
        return items
    return {prefix: value}


def said_unreadable(value: Any) -> bool:
    return value is None or normalise(value) in UNREADABLE


@dataclass
class SampleScore:
    sample: str
    fields_total: int = 0
    fields_exact: int = 0
    fields_normalised: int = 0
    field_errors: list[tuple[str, Any, Any]] = field(default_factory=list)  # (path, expected, predicted)
    regions_total: int = 0
    regions_found: int = 0
    region_ious: dict[str, float] = field(default_factory=dict)
    unreadable_total: int = 0
    unreadable_respected: int = 0
    error: str = ""


def score_sample(
    sample: str, label: dict[str, Any], prediction: dict[str, Any], iou_threshold: float = 0.5
) -> SampleScore:
    score = SampleScore(sample)
    unreadable = set(label.get("unreadable", []))
    expected = flatten(label.get("fields", {}))
    predicted = flatten(prediction.get("fields", {}))
    for path, want in expected.items():
        if path in unreadable or path.split("[")[0] in unreadable:
            continue
        got = predicted.get(path)
        score.fields_total += 1
        if got is not None and str(got).strip() == str(want).strip():
            score.fields_exact += 1
        if got is not None and normalise(got) == normalise(want):
            score.fields_normalised += 1
        else:
            score.field_errors.append((path, want, got))
    for name in unreadable:
        score.unreadable_total += 1
        got = prediction.get("fields", {}).get(name) if isinstance(prediction.get("fields"), dict) else None
        found_region = any(r.get("label") == name for r in prediction.get("regions", []))
        if said_unreadable(got) and not found_region:
            score.unreadable_respected += 1
    predicted_regions = prediction.get("regions", [])
    for region in label.get("regions", []):
        score.regions_total += 1
        candidates = [
            p
            for p in predicted_regions
            if p.get("label") == region.get("label") and p.get("page", 1) == region.get("page", 1)
        ]
        best = max((iou(tuple(region["box"]), tuple(p["box"])) for p in candidates), default=0.0)
        score.region_ious[str(region.get("label"))] = round(best, 3)
        if best >= iou_threshold:
            score.regions_found += 1
    return score


def aggregate(scores: list[SampleScore]) -> dict[str, float]:
    def rate(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 1.0

    ious = [v for s in scores for v in s.region_ious.values()]
    return {
        "samples": len(scores),
        "errors": sum(1 for s in scores if s.error),
        "field_exact": rate(sum(s.fields_exact for s in scores), sum(s.fields_total for s in scores)),
        "field_normalised": rate(
            sum(s.fields_normalised for s in scores), sum(s.fields_total for s in scores)
        ),
        "region_recall": rate(sum(s.regions_found for s in scores), sum(s.regions_total for s in scores)),
        "mean_iou": round(sum(ious) / len(ious), 4) if ious else 1.0,
        "unreadable_respected": rate(
            sum(s.unreadable_respected for s in scores), sum(s.unreadable_total for s in scores)
        ),
    }


def check_targets(metrics: dict[str, float], targets: dict[str, float]) -> list[str]:
    """The targets not met, as readable lines (lower-is-better metrics use a 'max_' prefix)."""
    misses = []
    for name, target in targets.items():
        if name.startswith("max_"):
            actual = metrics.get(name[4:])
            if actual is not None and actual > target:
                misses.append(f"{name[4:]} = {actual} > {target}")
        else:
            actual = metrics.get(name)
            if actual is None or actual < target:
                misses.append(f"{name} = {actual} < {target}")
    return misses
