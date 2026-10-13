---
name: eval-harness
description: Use when you build or change an ML or LLM feature and need to measure it: set up an eval set (labelled samples), metrics with targets, a per-sample report and a regression gate
---
# Eval harness

1. Eval set: a folder of samples + `labels.json` (expected fields, boxes, answers). Start small (10–30),
   cover the hard cases, keep sensitive samples out unless the user approved them.
2. Metrics that match the requirement: exact / normalised match for fields, IoU for boxes, answer
   correctness judged against a reference (an LLM judge only with a rubric and spot checks).
3. Targets agreed with the user (e.g. field accuracy >= 0.9). A task isn't done until the targets are met or
   the user accepts the gap.
4. Runner: runs the pipeline on every sample, writes a per-sample report (prediction vs expected, overlays
   for boxes) and an aggregate table; deterministic where possible (temperature 0, fixed seeds).
5. Use it as a regression gate: run before/after each change and compare.
