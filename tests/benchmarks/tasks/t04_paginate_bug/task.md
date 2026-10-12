The list screens use `paginate()` in `paginate.py`, and users report that it is wrong: page 1 seems to skip the first items, the last partly filled page is missing from the page count, and the "next page" flag is off.

Find the cause and fix it. Keep the function signature and the keys of the returned dictionary unchanged; the docstring describes the intended behaviour. `test_paginate.py` has one failing test that shows the first symptom; keep it, make it pass, and add tests that cover the other symptoms and the edge cases in the docstring.
