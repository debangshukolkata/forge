---
id: rcp-security
type: recipe
title: Security checklist for Python code
summary: "Input validation, injection, paths, subprocess, secrets, deserialisation, passwords, requests; web output, links, redirects, signed cookies; one hostile test per function and sink."
moods: [secure]
products: [any python code, web, cli]
tags: [security, injection, path traversal, secrets, owasp, xss, open redirect, cookies, security review]
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

## Web output, links, redirects and cookies (C1b: the sinks a security review missed)

A review is done when **every function that takes outside input has one hostile test per sink it reaches** (HTML, link, redirect, file,
SQL, shell, deserialiser, evaluator), not when the existing tests pass. List the functions first, write down each one's sinks, then
go down the list. A fix that blocks a few example strings (`if "javascript" in url`) is not a fix: parse, then allow a short list.
11. **HTML**: escape every value with `html.escape(value, quote=True)`, also inside attributes.
12. **Links from users** (`href`, `src`): strip whitespace, refuse control characters (browsers drop a tab inside `java\tscript:`),
    then allow only `http` and `https` with a host. Everything else (javascript, data, vbscript, ftp, `//host`, a bare path) gets no link.
13. **Redirects to a user-given target**: only a local path: one leading `/`, then not `/` or `\`, no backslash or control character
    anywhere (`//evil`, `/\evil` and `\\evil` all leave the site in some browser). Anything else goes to the default.
14. **Signed cookies and tokens**: `hmac.new(key, payload, hashlib.sha256)` and `hmac.compare_digest`; split on the last separator; after
    decoding, check the type you expect (a signed list is not a session dict). Never `pickle`.
15. **Evaluating user arithmetic**: parse with `ast` and allow only number literals and a few operators; `True` is an `int` in Python, so
    check `type(value) in (int, float)`, and cap exponents and lengths.

```python
# runnable
import base64
import hashlib
import hmac
import html
import json
from urllib.parse import urlsplit

CONTROL = {chr(c) for c in range(32)} | {chr(127)}


def safe_link(url: str) -> str | None:
    """The URL when it is a plain http(s) link with a host, else None (render the text without a link)."""
    url = url.strip()
    if not url or CONTROL.intersection(url) or "\\" in url:
        return None
    parts = urlsplit(url)
    return url if parts.scheme.lower() in ("http", "https") and parts.netloc else None


def safe_redirect(target: str, default: str = "/") -> str:
    """Only a path on this site; anything that could leave it goes to the default."""
    if (
        not target.startswith("/")
        or target[1:2] in ("/", "\\")
        or "\\" in target
        or CONTROL.intersection(target)
    ):
        return default
    return target


def sign(key: bytes, data: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(data, sort_keys=True).encode()).decode()
    mac = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{mac}"


def verify(key: bytes, cookie: str) -> dict:
    payload, _, mac = cookie.rpartition(".")
    expected = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    if not payload or not hmac.compare_digest(mac, expected):
        raise ValueError("bad signature")
    data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    if not isinstance(data, dict):
        raise ValueError("not a session")
    return data


for hostile in ("javascript:alert(1)", " JaVaScRiPt:x", "java\tscript:x", "data:text/html,x", "//evil.example", "/relative", "https://"):
    assert safe_link(hostile) is None, hostile
assert safe_link("https://example.org/a?b=1") == "https://example.org/a?b=1"
for hostile in ("//evil.example", "/\\evil.example", "\\\\evil.example", "https://evil.example", "evil.example", "/x\x00"):
    assert safe_redirect(hostile) == "/", hostile
assert safe_redirect("/orders?page=2") == "/orders?page=2"
key = b"k" * 32
cookie = sign(key, {"user": "ana"})
assert verify(key, cookie) == {"user": "ana"}
for forged in (cookie[:-1] + ("0" if cookie[-1] != "0" else "1"), "x", sign(b"other" * 7, {"user": "admin"})):
    try:
        verify(key, forged)
    except ValueError:
        continue
    raise AssertionError(forged)
assert html.escape('"><script>', quote=True) == "&quot;&gt;&lt;script&gt;"
```
