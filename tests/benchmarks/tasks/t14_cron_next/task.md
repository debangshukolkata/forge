Create a module `cron.py` with `next_run(expression: str, after: datetime) -> datetime` that returns the first time a standard 5-field cron expression fires **strictly after** `after`. All datetimes are naive (no time zones). The result is always on a whole minute (seconds and microseconds 0). `after` may have seconds and microseconds: `10:00:30` with `* * * * *` gives `10:01:00`, and `10:00:00` gives `10:01:00` (strictly after).

**Fields**, separated by one or more spaces or tabs: `minute (0-59)  hour (0-23)  day-of-month (1-31)  month (1-12 or jan-dec)  day-of-week (0-7 or sun-sat; both 0 and 7 mean Sunday)`.

**Each field** is a comma separated list of items; each item is one of:
- `*` (every value in range), a number or a name (`5`, `jan`, `Mon`; names are case insensitive and only allowed in the month and day-of-week fields),
- a range `a-b` (inclusive, `a <= b`; names allowed: `mon-fri`),
- a step `*/n`, `a-b/n` or `a/n` (`a/n` means from `a` to the field's maximum, every `n`). `n` must be at least 1.
For day-of-week a range may end in 7 (`5-7` = Fri, Sat, Sun).

**Day rule (the classic one):** if both day-of-month and day-of-week are restricted (the field text does not start with `*`), a day matches when **either** of them matches. If at least one of them starts with `*` (`*`, `*/2`, ...), a day must match **both** (a plain `*` matches every day, so only the other field really restricts; `*/2` in day-of-month means days 1, 3, 5, ... and is combined with the day-of-week field by "and"). Month, hour and minute must always all match.

**Errors:** `ValueError` for: not exactly 5 fields, a value out of range (minute 60, hour 24, day 0 or 32, month 13, day-of-week 8), a reversed range (`5-2`), a step of 0 or not a number, an empty list item (`1,,2`), an unknown name, a name in a numeric-only field, or any other junk. Also `ValueError` when the expression is valid but can never fire, such as `0 0 30 2 *` or `0 0 31 4,6,9,11 *`: give up when no match is found within 8 years after `after` (it must still answer quickly: do not loop over every minute of 8 years).

Real calendars apply: leap years (`0 0 29 2 *` fires only in leap years), month lengths, year rollover.

Write tests for it too. Use only the standard library.
