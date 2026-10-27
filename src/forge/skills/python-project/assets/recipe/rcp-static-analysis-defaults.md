---
id: rcp-static-analysis-defaults
type: recipe
title: Static checks and insecure defaults
summary: "Configure ruff, mypy and a bandit-style scan, and know the insecure defaults to remove: debug on, open CORS, weak hashes, shell=True, yaml.load, mktemp, verify=False."
moods: [secure, clean]
products: [any python code, web, ci]
tags: [static analysis, ruff, mypy, bandit, insecure defaults, lint, security]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Static checks and insecure defaults

Tools read the code without running it and find a class of mistakes cheaply. Set them up once, run them on every change.

Procedure:
1. **Linter** (`ruff`): in `pyproject.toml` under `[tool.ruff.lint]` select rule families, not just the default: `E`, `F`, `B` (bugbear),
   `S` (security, bandit-style), `UP`, `I`, `SIM`. Disable single rules with a reason, per file where possible.
2. **Types** (`mypy`): start with `strict = false` plus `warn_unused_ignores`, `no_implicit_optional`; turn on `strict` for new
   packages. Types find `None` mistakes a test might miss.
3. **Security scan**: ruff's `S` rules or `bandit -r src`. Triage each finding: fix, or mark `# noqa: S...` with a one-line reason.
4. **Dependencies**: `pip-audit` against the lock file.
5. **Run all of them in CI and as a pre-commit hook**; a check that is not enforced decays.
6. **Fix the defaults below first**; they are the most common real findings.

| Insecure default | Safer choice |
|---|---|
| web app `debug=True` in production | read from env, default off |
| CORS `allow_origins=["*"]` with credentials | list exact origins |
| `hashlib.md5/sha1` for passwords or tokens | `hashlib.scrypt`, bcrypt or argon2; `secrets` for tokens |
| `subprocess(..., shell=True)` with variables | list of arguments, `shell=False` |
| `yaml.load(text)` | `yaml.safe_load(text)` |
| `tempfile.mktemp()` | `tempfile.mkstemp()` or `TemporaryDirectory()` |
| `requests.get(url, verify=False)` | keep verification, supply a CA bundle if needed |
| `pickle.loads` of outside data, `eval`, `exec` | `json`, `ast.literal_eval` |
| `assert` for access checks | explicit `if` and raise |
| binding `0.0.0.0` by default | `127.0.0.1` unless deployed on purpose |

```python
# runnable
import ast

SOURCE = """
import subprocess, requests

def run(user_text):
    subprocess.run("ls " + user_text, shell=True)

def fetch(url):
    return requests.get(url, verify=False)

def ok(url):
    subprocess.run(["ls", "-l"], shell=False)
    return requests.get(url, timeout=5)
"""


def find_issues(source):
    issues = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if isinstance(keyword.value, ast.Constant):
                if keyword.arg == "shell" and keyword.value.value is True:
                    issues.append((node.lineno, "shell=True"))
                if keyword.arg == "verify" and keyword.value.value is False:
                    issues.append((node.lineno, "verify=False"))
    return sorted(issues)


found = find_issues(SOURCE)
print(found)
assert [kind for _, kind in found] == ["shell=True", "verify=False"]
assert find_issues("subprocess.run(['ls'], shell=False)") == []
```

Gotchas:
- A clean run means "none of the patterns it knows", not "secure"; keep reviewing logic and access control.
- Do not silence a rule project-wide because of one hit; ignore per line with a reason.
- `shell=True` with a fixed literal string is low risk but still easy to break later; prefer the list form.
- Tests may legitimately use `assert` or fake secrets; exclude the tests folder from those rules only.
- Pin tool versions so a new release does not turn CI red overnight; upgrade deliberately.
- Type-checker `# type: ignore` hides real problems; give each a code and a reason.
