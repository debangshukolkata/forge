The import job calls the two functions in `dedupe.py` with inputs of several hundred thousand numbers, and they take minutes. Make both fast (they should finish in well under a second for 300,000 items) without changing what they return or their signatures.

Keep the existing tests passing and add a test with a large input that would time out with the slow version. Use only the standard library.
