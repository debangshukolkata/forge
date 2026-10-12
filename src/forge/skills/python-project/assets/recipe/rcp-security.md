---
id: rcp-security
type: recipe
title: Security checklist for Python code
summary: "Input validation, injection, paths, subprocess, secrets, deserialisation, passwords, requests."
moods: [secure]
products: [any python code, web, cli]
tags: [security, injection, path traversal, secrets, owasp]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Security checklist for Python code

Go through this list before calling code that takes outside input done:
1. **Validate at the edge**: type, length, range, allowed characters; reject, do not "clean". Use pydantic models for requests.
2. **SQL**: parameters only (see `rcp-sql`). **Shell**: `subprocess.run([...], shell=False)` with a list; never join user text into a
   command string.
3. **Paths**: resolve and check that the result is inside the allowed folder (below). Never open a path built from user text unchecked.
4. **Secrets**: from the environment, never in code, logs, error text, URLs or git. Compare tokens with `hmac.compare_digest`.
5. **Deserialisation**: `json` yes; never `pickle`/`marshal` on outside data; `yaml.safe_load`, not `yaml.load`.
6. **Passwords**: store a salted slow hash (`hashlib.scrypt`, or bcrypt/argon2 packages), never the password; never roll your own crypto.
7. **Randomness for tokens**: `secrets.token_urlsafe()`, not `random`.
8. **Outgoing requests** with a user-supplied URL: allow only http/https, block private and loopback addresses, set a timeout.
9. **Errors**: show users a short message and a reference id; keep the traceback in the log.
10. **Dependencies**: pin versions in the lock/requirements file, run `pip-audit` now and then.

```python
# runnable
from pathlib import Path
import tempfile


def safe_join(base: Path, user_path: str) -> Path:
    """Return base/user_path, refusing anything that escapes base (../, absolute paths, symlinks out)."""
    candidate = (base / user_path).resolve()
    if base.resolve() not in candidate.parents and candidate != base.resolve():
        raise ValueError(f"path {user_path!r} is outside the allowed folder")
    return candidate


base = Path(tempfile.mkdtemp())
assert safe_join(base, "a/b.txt") == (base / "a" / "b.txt").resolve()
for hostile in ("../secret.txt", "/etc/passwd", "a/../../x"):
    try:
        safe_join(base, hostile)
    except ValueError:
        continue
    raise AssertionError(hostile)
```
