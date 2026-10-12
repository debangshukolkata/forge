import argparse
import json
import re
import sys
from collections import Counter

WORD = re.compile(r"[A-Za-z0-9']+")


def count_words(text: str, min_length: int, ignore_case: bool) -> Counter[str]:
    counter: Counter[str] = Counter()
    for raw in WORD.findall(text):
        word = raw.strip("'")
        if ignore_case:
            word = word.lower()
        if word and len(word) >= min_length:
            counter[word] += 1
    return counter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wordstat")
    parser.add_argument("file", nargs="?", default="-")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--min-length", type=int, default=1)
    parser.add_argument("--ignore-case", action="store_true")
    parser.add_argument("--json", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return int(stop.code) if isinstance(stop.code, int) else 2
    if args.top < 1 or args.min_length < 1:
        print("--top and --min-length must be at least 1", file=sys.stderr)
        return 2
    try:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            with open(args.file, encoding="utf-8") as handle:
                text = handle.read()
    except OSError as error:
        print(f"cannot read {args.file}: {error}", file=sys.stderr)
        return 2
    counter = count_words(text, args.min_length, args.ignore_case)
    ranked = sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))[: args.top]
    if args.json:
        payload = {
            "total_words": sum(counter.values()),
            "unique_words": len(counter),
            "top": [{"word": word, "count": count} for word, count in ranked],
        }
        print(json.dumps(payload))
    else:
        for word, count in ranked:
            print(f"{word} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
