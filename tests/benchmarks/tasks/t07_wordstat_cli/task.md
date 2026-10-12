Build a command line tool in one file, `wordstat.py`, that counts words in a text.

Usage: `python wordstat.py [FILE] [--top N] [--min-length L] [--ignore-case] [--json]`

- Input is the file `FILE`, or standard input when `FILE` is missing or is `-`. Read it as UTF-8.
- A word is a run of letters, digits and apostrophes (`[A-Za-z0-9']+`); apostrophes at the start or the end of a run are dropped. Words shorter than `--min-length` (default 1) are ignored.
- Counting is case sensitive unless `--ignore-case` is given (then everything is lower-cased).
- Default output: one line per word, `<word> <count>`, for the `--top N` most frequent words (default 10), most frequent first, ties in alphabetical order.
- With `--json` print one JSON object instead: `{"total_words": <int>, "unique_words": <int>, "top": [{"word": "...", "count": <int>}, ...]}`; the totals count all words that pass `--min-length`, not only the top ones.
- Exit code 0 on success. A file that does not exist or cannot be read: print a short message to standard error and exit with 2. `--top` below 1 or `--min-length` below 1: also exit with 2 (an error message on standard error).
- Put the work in a function `main(argv: list[str] | None = None) -> int` so it can be tested, and call it with `sys.exit(main())` under `if __name__ == "__main__"`.

Write tests for it too. Use only the standard library.
