The folder is a small billing program: `models.py`, `storage.py` (customers, plans, invoices in an optional JSON file), `invoicing.py` (one-off invoices), `report.py`, `cli.py` and two test files. Read it first, keep its style, and keep every existing test passing. Money is whole cents. Add **recurring subscriptions with proration**, across the models, the storage, a new `billing.py`, the report and the CLI.

**Models and storage**
- `models.Subscription(id, customer_id, plan_id, start: date, end: date | None = None)`; `end` is the last day of service, inclusive.
- `Storage.subscriptions: dict[int, Subscription]`; `Storage.subscription(id)` (KeyError if unknown); `Storage.add_subscription(customer_id, plan_id, start) -> Subscription` (KeyError for an unknown customer or plan). Ids start at 1 and grow by 1.
- Saved in the same JSON file under a new top-level key `"subscriptions"`: a list of `{"id", "customer_id", "plan_id", "start", "end"}` with dates as `YYYY-MM-DD` strings and `"end": null` while running. The existing keys and their format, including the `"next_id"` object (it must still hold exactly `customer`, `plan` and `invoice`), must not change; derive the next subscription id when loading instead. A file written by the old version (no `"subscriptions"` key) must load with no subscriptions.

**`billing.py`**
- `subscribe(storage, customer_id, plan_id, start) -> Subscription`. `ValueError` if that customer already has a subscription to the same plan that is still running on or after `start` (no `end`, or `end >= start`).
- `cancel(storage, subscription_id, end) -> Subscription` sets the last day of service. `ValueError` if it is already cancelled or `end` is before `start`; `KeyError` for an unknown id.
- `bill_month(storage, year, month, issued) -> list[Invoice]` creates the monthly invoices and returns only the ones it created, ordered by customer id. `ValueError` if `month` is not 1 to 12. For each customer, ordered by subscription id, a subscription gets one invoice line if it was running on at least one day of the month (both start and end day count as service days). A full month costs the plan's `monthly_cents`; a part month costs `monthly_cents * days / days_in_month` rounded to whole cents with halves rounded **up** (use integer arithmetic; Python's `round()` rounds halves to even, which is wrong here). Line descriptions: `"<plan name> <YYYY-MM>"` for a full month, `"<plan name> <YYYY-MM> (prorated <days>/<days_in_month> days)"` otherwise. The invoice has `issued` as given, `period_start` the first and `period_end` the last day of the month. A customer with no line gets no invoice. A customer who already has an invoice with that `period_start` is skipped, so running `bill_month` twice for the same month creates nothing the second time. A plan priced 0 still produces a line (and an invoice with total 0).

**Report (`report.py`)**
- `mrr(storage, on: date) -> int`: the sum of the plan prices of the subscriptions running on that day (`start <= on` and `end` is `None` or `on <= end`).
- `customer_statement` is unchanged for a customer without subscriptions. Otherwise, after the invoice lines, add a line `Subscriptions:` and then one line per subscription ordered by id: `"  #<id> <plan name> since <start>"` while running or `"  #<id> <plan name> <start>..<end>"` when cancelled.
- `revenue_by_month` needs no change.

**CLI (`cli.py`)**: new commands, same style (output through `out`, `error: ...` and exit code 1 for `KeyError`/`ValueError`, nothing saved on error; the usage text gets these appended in this order, each preceded by ` | `):
- `subscribe CUSTOMER PLAN START` prints `Subscription <id>: <customer name> on <plan name> from <start>`
- `cancel SUBSCRIPTION END` prints `Subscription <id> ends <end>`
- `bill YYYY-MM ISSUED` prints `Invoice <id> for <customer name>: <money>` for each created invoice, or `Nothing to bill.`
- `mrr DATE` prints `MRR on <date>: <money>`
Dates are `YYYY-MM-DD`; money is formatted with `format_money`.

Add tests for the new behaviour in a new file (for example `test_billing.py`).
