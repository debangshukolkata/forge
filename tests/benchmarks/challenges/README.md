# Approach challenges (TODO part 4, agreed with the user 2026-10-15)

Small tasks, each with one deliberate trap. The run is time-boxed (about 5 minutes or the first 20 tool calls, whichever comes first) and stopped: only the **approach** is
judged, from `.forge/transcripts/events.jsonl` and the files as they stand. If the approach is right the task can be solved; if it is wrong, Forge is fixed and the same
challenge is run again, then new challenges are written until the approach is right.

Run: `python scripts/benchmark/run_challenges.py <run-name> [--tasks c01_month_boundary,...] [--max-seconds 300] [--max-tool-calls 20]`
(results and a readable timeline per challenge under `C:\Work\ForgeRuns\challenges\<run-name>`).

| id | trap | what a correct approach shows |
|---|---|---|
| c01_month_boundary | the symptom is in `report.py`, the cause is in `timeutil.py` (the timezone is ignored) | reads the code path to `to_report_date`; reproduces with a boundary timestamp; a failing test first; the fix is in `timeutil` (zoneinfo), not a patch in `report` |
| c02_loyalty_discount | "loyal" and "a discount" are not defined | notices it and states its assumptions (or asks) before coding; no silent magic numbers (named constants or parameters); how it interacts with the coupon and shipping is decided on purpose; tests |
| c03_event_buckets | the edge cases are not in the brief | lists them (empty input, unsorted events, zero or negative width, boundary values, gaps) before coding; validates `width_s`; tests cover them |
| c04_lost_counts | a race that a single-threaded test never shows | reproduces with threads first; names the read-modify-write race; fixes with a lock (or an atomic); a threaded regression test |
| c05_product_search | the existing `get_user_by_name` builds SQL with an f-string | parameterized `LIKE ?` (and the `%`/`_` of the term escaped); does not copy the f-string pattern; says the old function is injectable |
| c06_csv_export | the repository already has `Result`, `format_money`, `sample_orders` | reads `result.py`, `money.py`, `orders.py` and the tests before editing; returns a `Result`; uses `format_money`; the `csv` module (a customer name has a comma); tests use the existing fixtures |
| c07_settings_model | pydantic v2, not the v1 API from memory | installs or checks the installed version first (`library_api`, `pip show` or `help`) before writing code that imports pydantic; `field_validator`, `model_validate`, `model_dump`; no `@validator`, `parse_obj`, `class Config` |
| c08_price_refactor | quirks a tidy rewrite silently changes (coupon caps per tier, the food-share tax split, the "+1 cent when the total ends in 4 or 9" rule) | runs the existing tests, writes characterization tests covering every branch **before** the first edit, refactors in small steps and runs the tests after each |

The runner prints automatic signals (tool order, first edit, tests run before the first edit, a failing test before the fix, library check before pydantic code, assumptions
stated), but the judgement is made by reading the timeline.
