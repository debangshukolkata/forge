---
id: rcp-threat-model-review
type: recipe
title: Threat model and security code review
summary: "List assets, entry points and trust boundaries, ask STRIDE-style questions in plain words, check each entry point, rank by impact and likelihood."
moods: [secure, careful]
products: [security review, web, api, any python code]
tags: [threat model, stride, security review, trust boundary, entry points, risk]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Threat model and security code review

A review without a model of what matters turns into a random hunt. Spend the first ten minutes on a small model, then read code with it.

Procedure:
1. **Assets**: what would hurt to lose, leak or change? (user data, credentials, money, the ability to run code, the audit log, availability.)
2. **Entry points**: every way outside data or people reach the code: HTTP routes, forms, file uploads, CLI arguments,
   environment variables, queues, webhooks, scheduled jobs reading shared files, third-party responses.
3. **Trust boundaries**: where data moves from less trusted to more trusted (browser to server, server to database, user
   file to parser, our code to a shell). Checks belong *on* the boundary.
4. **Ask six plain questions** of each entry point (STRIDE in everyday words):
   - Can someone pretend to be another user or service? (spoofing)
   - Can they change data they should not, in transit or at rest? (tampering)
   - Can they deny doing something because nothing was recorded? (repudiation)
   - Can they read what they should not, including in errors and logs? (information disclosure)
   - Can they make it slow, big or crash? (denial of service)
   - Can an ordinary user reach an admin action? (elevation of privilege)
5. **Checklist per entry point**: authentication, authorisation on the object (not just "logged in"), input validation,
   output encoding, size and rate limits, safe parsing, error text, logging without secrets.
6. **Read the code along each path** from the entry point to the sink (database, shell, file, response) and note the checks it meets on the way.
7. **Rank** each finding by impact and likelihood (1 to 3 each); fix highest score first. Record accepted risks and who accepted them.
8. **Write the result**: the finding, the path to reproduce, the fix, and a test that would catch a return.

```python
# runnable
ENTRY_POINTS = [
    {"name": "POST /login", "impact": 3, "likelihood": 3, "note": "no rate limit"},
    {"name": "GET /files/<name>", "impact": 3, "likelihood": 2, "note": "path built from user text"},
    {"name": "admin CLI --config", "impact": 2, "likelihood": 1, "note": "local operators only"},
    {"name": "webhook /hooks/pay", "impact": 3, "likelihood": 2, "note": "signature not checked"},
]


def rank(entry_points):
    scored = [dict(item, score=item["impact"] * item["likelihood"]) for item in entry_points]
    return sorted(scored, key=lambda item: (-item["score"], item["name"]))


def as_table(rows):
    lines = [f"{'entry point':<20} {'impact':>6} {'likely':>6} {'score':>5}  note"]
    for row in rows:
        lines.append(
            f"{row['name']:<20} {row['impact']:>6} {row['likelihood']:>6} {row['score']:>5}  {row['note']}"
        )
    return "\n".join(lines)


ranked = rank(ENTRY_POINTS)
print(as_table(ranked))
assert ranked[0]["name"] == "POST /login"
assert [row["score"] for row in ranked] == [9, 6, 6, 2]
assert ranked[-1]["name"] == "admin CLI --config"
```

Gotchas:
- "Logged in" is not "allowed": check that this user may touch this record (the classic object-level hole).
- Internal does not mean trusted; a queue or file another service writes is an entry point too.
- Client-side checks are hints for the user, not security.
- Security through hidden URLs fails; assume the attacker knows the routes.
- Errors and logs leak: stack traces, SQL, tokens in query strings.
- Keep the model short and alive: update it when an entry point is added, not once a year.
- Scores are for ordering, not precision; argue about the top three, not the decimals.
- For the checks at each sink (HTML escaping, link schemes, redirects, signed cookies, paths, SQL, shell, deserialising) add `rcp-security`
  too: this recipe finds where to look, that one says what a correct check looks like and has tested helpers.
