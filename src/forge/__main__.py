"""`python -m forge ...` does the same as the `forge` command."""

from __future__ import annotations

import sys

from forge.cli import main

if __name__ == "__main__":
    sys.exit(main())
