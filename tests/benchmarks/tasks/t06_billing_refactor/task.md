`billing.py` has three functions that repeat the same code. Refactor it so the shared logic exists once, without changing any behaviour:

- Add `calculate_total(lines, customer_type)` where `customer_type` is "retail", "wholesale" or "member" (any other value raises `ValueError`). It holds the shared logic.
- Keep `invoice_total_retail`, `invoice_total_wholesale` and `invoice_total_member` with the same signatures and results, but each becomes a thin wrapper of at most three statements (a docstring does not count) that calls `calculate_total`.
- The discount rules and the tax rate stay as they are, and each is defined in one place.

The existing tests must keep passing; add tests for `calculate_total` and for the unknown customer type.
