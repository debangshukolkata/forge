# Document benchmark (TODO W5, D-357)

`scripts/benchmark/run_document_benchmark.py <run-name>` runs three fixed tasks on the real model (`tests/benchmarks/documents`) and scores them with
deterministic checks and a blind vision judgement of the printed pages (strict anchored scale: 5 professional, 3 plain, 2 machine-made). The checks are proven by
`tests/test_document_benchmark_checks.py` on outputs made by DebCraft's own tools, so a failed check means the model's work.

| Run | What changed | Task | Checks | Wall | Cost | Judge (structure/readability/tables/polish) |
|---|---|---|---|---|---|---|
| doc-1 (2026-10-15) | first run, W0-W4 tools and skills | Word sales summary | 8/8 | 299 s | $0.37 | 4/4/4/3 |
| doc-1 | same | messy export to workbook | 8/8 | 170 s | $0.17 | 3/4/3/2 |
| doc-1 | same | PDF handout | 7/7 | 186 s | $0.22 | 4/4/5/4 |

## What the first run showed
- All 23 checks pass: the model uses the tools (build, clean, check, preview) correctly and the files are valid. Total $0.76 for three tasks, about 11 minutes.
- The judge finds craft problems the checks cannot: (1) the workbook had **two charts, one showing only one product**, instead of one coherent chart of amount by
  product; (2) the PDF handout showed its **title twice** (the builder prints the title and the model also wrote it as a heading); (3) the Word summary scored 3 on polish.
- Actions taken: the skills now say that the title is printed for you, that a chart is one per question and excludes the total row, and that every chart is
  looked at in a preview. A rerun after these notes is the next measurement.

## Limits
One run per task, a vision judge of the same model family, three tasks. Read the facts (which checks failed, what the judge names) rather than small score differences.
