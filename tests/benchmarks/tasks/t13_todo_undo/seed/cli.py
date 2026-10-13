from __future__ import annotations

import argparse
import sys
from pathlib import Path

from store import TaskStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="todo")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="add a task")
    add.add_argument("title")
    done = commands.add_parser("done", help="mark a task as done")
    done.add_argument("id", type=int)
    remove = commands.add_parser("rm", help="remove a task")
    remove.add_argument("id", type=int)
    listing = commands.add_parser("list", help="show tasks")
    listing.add_argument("--all", action="store_true", help="include finished tasks")
    return parser


def main(argv: list[str] | None = None, store_path: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = TaskStore(store_path or Path("todo.json"))
    try:
        if args.command == "add":
            task = store.add(args.title)
            print(f"Added {task.id}: {task.title}")
        elif args.command == "done":
            task = store.complete(args.id)
            print(f"Done {task.id}: {task.title}")
        elif args.command == "rm":
            store.remove(args.id)
            print(f"Removed {args.id}")
        else:
            for task in store.list(include_done=args.all):
                print(f"{task.id} [{'x' if task.done else ' '}] {task.title}")
    except KeyError as error:
        print(f"No task {error.args[0]}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
