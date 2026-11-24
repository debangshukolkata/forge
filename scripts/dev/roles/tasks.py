"""The tasks of the role challenge that are one call to a model, and how each answer is scored (D-655).

Everything here is made up for this test: no project, file or data of the user is in it. A score is 0 to 100."""

from __future__ import annotations

import json
import re
from typing import Any

Result = tuple[float, str]  # the score and one line for the report


def json_in(text: str) -> dict[str, Any] | None:
    """The last JSON object in an answer, also when it stands in a code block or between sentences."""
    decoder = json.JSONDecoder()
    best: dict[str, Any] | None = None
    at = 0
    while (start := text.find("{", at)) >= 0:
        try:
            data, length = decoder.raw_decode(text[start:])
        except ValueError:
            at = start + 1
            continue
        if isinstance(data, dict):
            best = data
        at = start + length
    return best


# --- planner: graded blind against this checklist by two models

PLANNER = (
    "You are the planner. Plan the work; do not write code. The builder sees only your plan.\n\n"
    "Request of the user: Make an agent for recordings. I give it a recording (like the video of a one hour event) and "
    "ask questions about it, and it should answer and tell me from which moment to play. First the recording is indexed: "
    "its parts are found and stored with descriptions and times, so that it is fast when the screen is opened again. "
    "After indexing, later questions should use the stored data and not analyse the full recording every time. When the "
    "recording does not say it, found is false. The part to play must be short.\n\n"
    "What exists: a small Python service (standard library HTTP server, SQLite). `recordings.load(id)` gives the moments "
    "of a recording in order: seconds, speech (what is said) and screen (what is seen), about 250 per hour. "
    "`model.complete(prompt, json_answer=False)` asks a language model (128,000 tokens of input, about 3 seconds). "
    "`store.connect()` opens the database. Wanted: POST /recordings/<id>/index, GET /recordings/<id>/sections, "
    'POST /recordings/<id>/ask {"question"} -> {"found", "answer", "start_seconds", "end_seconds"}.\n\n'
    "Write the plan in at most 600 words: the approach and why, what is stored, the steps of each call, the tasks with a "
    "check for each, the assumptions and the risks."
)
PLANNER_CHECKS = [
    "The answer to a question is worked out by the language model, not by shared words, keywords or fixed patterns",
    "The original speech and screen text of every moment is kept in storage, not only summaries or descriptions",
    "A detail that no description mentions can still be answered, because the original moments are read for the answer",
    "What is SEEN (screen) is used as well as what is said",
    "It says how a question finds the right place without sending everything each time, or argues with the given sizes that the stored moments fit in one call",
    "Only stored data is used after indexing: the recording file is not analysed again for each question",
    "Not found: the model is told to say so, and the code returns found false without an answer it made up",
    "The moment returned is taken from or checked against the stored moments by the code, not simply believed",
    "The part to play has a short maximum length that the code enforces",
    "It handles a question asked before indexing and an unknown recording with clear errors",
    "An answer of the model that is not valid JSON, and a failing model call, are errors and not a weaker answer",
    "Indexing the same recording again replaces the old data and leaves nothing half written when it fails",
    "The tables are named with their columns",
    "It is proven with questions not used while building: reworded, a detail seen for one moment, and one nothing answers",
    "It names at least two real risks or assumptions specific to this request (not general phrases)",
]


def grader_prompt(answer: str) -> str:
    listing = "\n".join(f"{n}. {text}" for n, text in enumerate(PLANNER_CHECKS, 1))
    return (
        "Grade a plan against criteria. A criterion is met only when the plan really says it; be strict, do not reward "
        f"length or good style.\n\nThe task was:\n{PLANNER}\n\nThe plan:\n{answer}\n\nCriteria:\n{listing}\n\n"
        'Answer with JSON only: {"met": [numbers of the criteria that are met]}'
    )


def planner_score(text: str) -> float | None:
    """The grader's verdict; None when it cannot be read."""
    data = json_in(text)
    if data is None or not isinstance(data.get("met"), list):
        return None
    met = {n for n in data["met"] if isinstance(n, int) and 1 <= n <= len(PLANNER_CHECKS)}
    return 100 * len(met) / len(PLANNER_CHECKS)


# --- reviewer: planted faults, and correct code that looks wrong (cached, file_id, month_end, chunks)

REVIEW_CODE = '''
import hashlib, json, os, subprocess, threading, time
from datetime import datetime, timedelta, timezone

CACHE = {}
LOCK = threading.Lock()


def page(items, number, size):
    """Page `number` (the first is 1) of the items."""
    start = number * size
    return items[start:start + size]


def find_user(db, name):
    return db.execute("SELECT id, name FROM users WHERE name = '%s'" % name).fetchone()


def add_tag(tag, tags=[]):
    tags.append(tag.strip().lower())
    return tags


def transfer(db, source, target, amount):
    """Moves money in one transaction; a lock around the call makes sure only one runs at a time."""
    with db:
        row = db.execute("SELECT balance FROM accounts WHERE id = ?", (source,)).fetchone()
        if row["balance"] < amount:
            raise ValueError("not enough money")
        db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, source))
    db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, target))
    db.commit()


def read_report(folder, name):
    """Reports live in `folder`; `name` comes from the web page."""
    with open(os.path.join(folder, name), encoding="utf-8") as handle:
        return handle.read()


def is_expired(created_at, hours):
    """created_at is an aware UTC datetime."""
    return datetime.now() - created_at > timedelta(hours=hours)


def load_settings(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def save_settings(path, changes):
    settings = load_settings(path)
    settings.update(changes)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle)


def cached(key, make):
    """`make` is pure and may run twice; every caller gets the same object."""
    with LOCK:
        if key in CACHE:
            return CACHE[key]
    value = make()
    with LOCK:
        return CACHE.setdefault(key, value)


def file_id(data):
    """A short name for a file in the cache; nobody relies on it for security."""
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


def thumbnail(source, target):
    subprocess.run(["convert", "--", source, "-resize", "200x200", target], timeout=30)
    return target


def average(values):
    """0.0 when there are no values."""
    return sum(values) / len(values) if values is not None else 0.0


def newest(versions):
    """versions such as "1.9.2" or "1.10.0"."""
    return max(versions)


def remove_inactive(users):
    for user in users:
        if not user["active"]:
            users.remove(user)
    return users


def retry(call, times=3):
    for attempt in range(times):
        try:
            return call()
        except Exception:
            time.sleep(2 ** attempt)


def month_end(day):
    """The last day of the month of `day` (a date)."""
    following = day.replace(day=28) + timedelta(days=4)
    return following - timedelta(days=following.day)


def next_month(day):
    """The same day one month later."""
    return day.replace(month=day.month % 12 + 1)


def chunks(items, size):
    return [items[start:start + size] for start in range(0, len(items), size)]
'''.strip()
REVIEWER = (
    "Review this module of a web service. Report every real defect: a wrong result, a security hole, lost data, a crash "
    "on ordinary input, or an error nobody notices. No style, naming, typing, missing tests or wishes. A false alarm "
    "costs as much as a missed defect, so leave out what is correct.\n\n```python\n"
    + REVIEW_CODE
    + "\n```\n\n"
    'Answer with JSON only: {"defects": [{"function": "name", "problem": "one sentence"}]}'
)
# function -> what the problem must mention
REVIEW_FAULTS: dict[str, str] = {
    "page": r"first|off.?by|number|start|page 1|1-based|skip",
    "find_user": r"inject|sql|parameter|format|quot",
    "add_tag": r"mutable|default|shared|between calls|persist",
    "transfer": r"transaction|atomic|credit|outside|second update|rollback",
    "read_report": r"travers|path|\.\.|absolute|outside",
    "is_expired": r"naive|aware|timezone|utc|\btz|typeerror",
    "save_settings": r"lost|lose|overwrit|empty|swallow|corrupt|wipe|erase|discard|truncat|atomic|partial",
    "load_settings": r"swallow|except|silent|hide|empty|corrupt|mask|invalid|error",
    "thumbnail": r"return ?code|check|exit|fail|ignor|result",
    "average": r"empty|zero|division",
    "newest": r"string|lexic|alphab|1\.10|compar|numer|text",
    "remove_inactive": r"iterat|skip|while loop|during|mutat|modif",
    "retry": r"swallow|None|silent|last|raise|hide|lost|exhaust",
    "next_month": r"year|december|valueerror|31|30|29|invalid|crash|exist",
}


def _settings_as_one(name: str) -> str:
    """load_settings and save_settings are one fault: naming either is enough."""
    return "settings" if name.endswith("_settings") else name


def reviewer_score(text: str) -> Result:
    """Found faults against false alarms (F1)."""
    data = json_in(text)
    if data is None or not isinstance(data.get("defects"), list):
        return 0.0, "no valid JSON"
    found: set[str] = set()
    alarms: set[str] = set()
    for item in data["defects"]:
        if not isinstance(item, dict):
            continue
        name = re.sub(r"\W.*", "", str(item.get("function", "")).strip(), flags=re.DOTALL)
        pattern = REVIEW_FAULTS.get(name)
        if pattern and re.search(pattern, str(item.get("problem", "")), re.IGNORECASE):
            found.add(_settings_as_one(name))
        else:
            alarms.add(name)
    alarms = {name for name in alarms if _settings_as_one(name) not in found}
    total = len({_settings_as_one(name) for name in REVIEW_FAULTS})
    score = 100 * 2 * len(found) / (total + len(found) + len(alarms))
    return score, f"{len(found)} of {total} defects found, {len(alarms)} false alarms"


# --- judge: answers whose quality is known

JUDGE_TASK = (
    "Write a function `first_free(taken, size)`: `taken` is a list of (start, end) intervals in minutes, in any order, "
    "possibly overlapping, end not included. Return the earliest start >= 0 where `size` minutes are free (size is at "
    "least 1). Do not change the list. Explain the idea in exactly one sentence before the code."
)
_IDEA = "Walk the sorted intervals and stop at the first gap that is long enough.\n\n"
_HEAD = "def first_free(taken, size):\n"
_LOOP = "    at = 0\n    for start, end in sorted(taken):\n        if start - at >= size:\n            return at\n"
_END = "        at = max(at, end)\n    return at"
# id: (answer, (correct for every input, does not change the list, exactly one sentence before the code))
JUDGE_ANSWERS: dict[str, tuple[str, tuple[bool, bool, bool]]] = {
    "A": (_IDEA + _HEAD + _LOOP + _END, (True, True, True)),
    "B": (_IDEA + _HEAD + _LOOP + "        at = end\n    return at", (False, True, True)),
    "C": (
        "Sort the intervals first, then walk them keeping the latest end seen so far.\n\n"
        + _HEAD
        + "    taken.sort()\n"
        + _LOOP.replace("sorted(taken)", "taken")
        + _END,
        (True, False, True),
    ),
    "D": (
        _HEAD
        + _LOOP
        + _END
        + "\n\nIt walks the sorted intervals and stops at the first gap that is long enough.",
        (True, True, False),
    ),
    "E": (
        "Collect every minute that is taken and try the starts one after the other.\n\n"
        + _HEAD
        + "    busy = {m for start, end in taken for m in range(start, end)}\n    at = 0\n"
        "    while any(m in busy for m in range(at, at + size)):\n        at += 1\n    return at",
        (True, True, True),
    ),
    "F": (
        "This robust, production-ready solution handles all edge cases with an optimal sweep. It has been carefully "
        "tested.\n\n" + _HEAD + _LOOP.replace("sorted(taken)", "taken") + _END,
        (False, True, False),
    ),
    "G": (_IDEA + _HEAD + _LOOP.replace(">= size", "> size") + _END, (False, True, True)),
    "H": (
        "Take the earliest interval of a copy again and again and remember the latest end.\n\n"
        + _HEAD
        + "    rest = list(taken)\n    at = 0\n    while rest:\n        start, end = min(rest)\n"
        "        rest.remove((start, end))\n        if start - at >= size:\n            return at\n" + _END,
        (True, True, True),
    ),
}
_FREE = "    for at in sorted([0] + [end for _, end in taken]):\n        if all({test} for start, end in taken):\n            return at"
JUDGE_ANSWERS |= {
    "I": (
        "Try zero and every end as the start and take the first that meets no interval.\n\n"
        + _HEAD
        + _FREE.format(test="end <= at or start >= at + size"),
        (True, True, True),
    ),
    "J": (
        "Try zero and every end as the start and take the first that meets no interval.\n\n"
        + _HEAD
        + _FREE.format(test="end <= at or start > at + size"),
        (False, True, True),
    ),
    "K": (
        "Add a last interval that never ends, then walk the sorted intervals.\n\n"
        + _HEAD
        + "    taken += [(10**9, 10**9)]\n"
        + _LOOP
        + _END,
        (True, False, True),
    ),
    "L": (
        "Add a last interval that never ends, then walk the sorted intervals.\n\n"
        + _HEAD
        + "    taken = taken + [(10**9, 10**9)]\n"
        + _LOOP
        + _END,
        (True, True, True),
    ),
    "M": (
        "Walk the sorted intervals and leave out those that begin before the place reached.\n\n"
        + _HEAD
        + "    at = 0\n    for start, end in sorted(taken):\n        if start < at:\n            continue\n"
        "        if start - at >= size:\n            return at\n        at = end\n    return at",
        (False, True, True),
    ),
    "N": (
        "Sort by the end of the intervals and keep the latest end. Then the first gap is the answer.\n\n"
        + _HEAD
        + _LOOP.replace("sorted(taken)", "sorted(taken, key=lambda pair: pair[1])")
        + _END,
        (False, True, False),
    ),
}
JUDGE = (
    f"Judge {len(JUDGE_ANSWERS)} answers to this task.\n\nTask: {JUDGE_TASK}\n\n"
    + "\n\n".join(f"--- Answer {name} ---\n{answer}" for name, (answer, _) in JUDGE_ANSWERS.items())
    + "\n\nFor each answer decide three things, true or false: `correct` (right for every valid input), `unchanged` (the "
    "caller's list is not changed) and `sentence` (exactly one sentence of explanation, and it stands before the code). "
    "Follow the code by hand; what an answer says about itself proves nothing.\n"
    'Answer with JSON only: {"A": {"correct": true, "unchanged": true, "sentence": true}, "B": {...}, ...}'
)
JUDGE_KEYS = ("correct", "unchanged", "sentence")


def judge_score(text: str) -> Result:
    data = json_in(text)
    if data is None:
        return 0.0, "no valid JSON"
    right = passed_wrongly = 0
    for name, (_, truth) in JUDGE_ANSWERS.items():
        given = data.get(name)
        for key, wanted in zip(JUDGE_KEYS, truth, strict=True):
            value = given.get(key) if isinstance(given, dict) else None
            right += value is wanted
            passed_wrongly += value is True and not wanted
    total = len(JUDGE_KEYS) * len(JUDGE_ANSWERS)
    return 100 * right / total, f"{right} of {total} verdicts right, {passed_wrongly} passed although wrong"


# --- summariser: facts that must survive

_NOISE = (
    "Tool read_file {file}: 180 lines shown. Nothing in it concerns this task.\n"
    "Assistant: That file only formats the output, I leave it alone.\n"
    "Tool run_command: python -m pytest -q {file}: 14 passed in 2.31 s"
)
_STEPS = [
    "User: The export of invoices must be ready by 14 January. Never touch the folder legacy_tax, the auditors have "
    "signed it off.",
    "Assistant: I found the export in billing/export_job.py, function build_rows.",
    "Tool run_command: ERROR KeyError: 'vat_code' in build_rows line 212 for invoice 88317",
    "Assistant: Cause: credit notes have no vat_code. Only type CN is affected.",
    "User: For credit notes use the code Z9, finance confirmed that.",
    "Assistant: I set the default code to Z0 in build_rows.",
    "User: No, I said Z9.",
    "Assistant: Corrected: the code is Z9, with the test test_credit_note_code.",
    "Tool http_request POST /exports -> 504 after 60 s",
    "Assistant: The request runs out of time because every invoice is read with its own query (about 4,100 queries).",
    "User: Use one query, but keep the batch size at 500, the database team demands it.",
    "Assistant: Now one query per batch of 500; the export takes 7.4 s.",
    "Tool run_command: FAILED test_export_order: rows are sorted by id, expected by issue_date",
    "User: The order by issue_date matters, the bank's program depends on it.",
    "Assistant: Sorted by issue_date, then id. test_export_order passes.",
    "User: The file name must be INV_<year><month>_v3.csv, separated by semicolons.",
    "Assistant: Done in billing/naming.py.",
    "User: Do not add pandas, it is not allowed on the server.",
    "Assistant: Open: the download button on the page Invoices still calls the old address /export_old.",
    "User: Change that button next, and afterwards tell Meera the new address /exports.",
    "Tool run_command: 1 test is still red: test_empty_month (an empty month gives a file without a header line)",
]
SUMMARY_FACTS: dict[str, str] = {
    "deadline": r"14(th)? (of )?Jan|January 14|Jan\.? 14",
    "legacy_tax is not touched": r"legacy_tax",
    "the file of the export": r"export_job",
    "the function": r"build_rows",
    "the error": r"KeyError|vat_code",
    "only credit notes": r"credit.?note|\bCN\b",
    "the code Z9": r"\bZ9\b",
    "its test": r"test_credit_note_code",
    "the time-out": r"504|60 ?s|time.?out|timed out",
    "its cause": r"4,?100|own query|(per|each|every|one) invoice|N\+1",
    "the batch size": r"\b500\b",
    "the time now": r"7\.4",
    "order by issue_date": r"issue_date",
    "who depends on it": r"bank",
    "the file name": r"INV_.{0,30}v3",
    "semicolons": r"semi-?colon|[`'\"];[`'\"]",
    "no pandas": r"pandas",
    "the button still to change": r"export_old",
    "tell Meera": r"Meera",
    "the red test": r"test_empty_month",
}
SUMMARY_WORDS = 130


def session_text() -> str:
    noise = [f"billing/part_{n:02}.py" for n in range(1, 2 * len(_STEPS) + 1)]
    lines = []
    for index, step in enumerate(_STEPS):
        lines.append(step)
        lines += [_NOISE.format(file=file) for file in noise[2 * index : 2 * index + 2]]
    return "\n".join(lines)


SUMMARISER = (
    "Summarise this working session so that another engineer can go on without reading it: the goal, the user's "
    "decisions and prohibitions, what was found and changed (names, numbers, files), and what is still open. Only what "
    f"holds at the end. At most {SUMMARY_WORDS} words.\n\n" + session_text()
)


def summary_score(text: str) -> Result:
    kept = [name for name, pattern in SUMMARY_FACTS.items() if re.search(pattern, text, re.IGNORECASE)]
    words = len(text.split())
    score = 100 * len(kept) / len(SUMMARY_FACTS)
    limit = SUMMARY_WORDS * 1.1
    if words > limit:
        score *= limit / words  # the limit is part of the task
    missing = [name for name in SUMMARY_FACTS if name not in kept]
    lost = f"; lost: {', '.join(missing[:4])}" if missing else ""
    return score, f"{len(kept)} of {len(SUMMARY_FACTS)} facts, {words} words{lost}"


# --- pictures: vision and the design critic (made by make_pictures.py)

VISION: dict[str, tuple[str, dict[str, Any]]] = {
    "chart": (
        "Read the chart. The bars carry only their names; read the values from the axis. JSON only: "
        '{"highest": "name", "lowest": "name", "Q2": value, "Q4": value}',
        {"highest": "Q3", "lowest": "Q1", "Q2": 45, "Q4": 60},
    ),
    "scan": (
        "This is a scanned delivery note. JSON only: "
        '{"number": "...", "date": "YYYY-MM-DD", "quantity_of_bolts": n, "total": number, "signed_by": "surname"}',
        {
            "number": "DN-70418",
            "date": "2026-03-09",
            "quantity_of_bolts": 136,
            "total": 1874.6,
            "signed_by": "Okafor",
        },
    ),
    "screen": (
        "A settings page of an application. JSON only: "
        '{"switched_on": ["names of the settings that are on"], "selected_tab": "name", "disabled_button": "its text"}',
        {
            "switched_on": ["Daily summary", "Share with team"],
            "selected_tab": "Privacy",
            "disabled_button": "Save",
        },
    ),
    "flow": (
        "A flow diagram. JSON only: "
        '{"after_check_yes": "the box reached from Check when the answer is yes", "after_check_no": "...", '
        '"into_archive": ["the boxes with an arrow directly into Archive"]}',
        {"after_check_yes": "Publish", "after_check_no": "Repair", "into_archive": ["Publish", "Reject"]},
    ),
    "table": (
        "A photographed price list. JSON only: "
        '{"price_of_KX-304": number, "stock_of_KX-340": n, "articles_with_stock_0": ["codes"], "dearest": "code"}',
        {
            "price_of_KX-304": 18.65,
            "stock_of_KX-340": 73,
            "articles_with_stock_0": ["KX-403", "KX-430"],
            "dearest": "KX-433",
        },
    ),
    "gauge": (
        "Read the instruments. JSON only: "
        '{"pressure": number on the gauge, "clock": "HH:MM as the clock shows it, 12 hours"}',
        {"pressure": 6.4, "clock": "08:37"},
    ),
    "shapes": (
        "Count in the picture. JSON only: "
        '{"red_triangles": n, "blue_circles": n, "shapes_inside_the_frame": n}',
        {"red_triangles": 7, "blue_circles": 9, "shapes_inside_the_frame": 11},
    ),
    "lines": (
        "Two curves: A is solid, B is dashed. Read the axes. JSON only: "
        '{"month_where_they_cross": "name of the month nearest to it", "A_in_June": value, "B_in_February": value}',
        {"month_where_they_cross": "Apr", "A_in_June": 85, "B_in_February": 60},
    ),
}
SLACK = {"chart": 2.0, "gauge": 0.2, "lines": 3.0}  # what reading from an axis cannot give exactly


def _same(given: Any, wanted: Any, slack: float) -> bool:
    if isinstance(wanted, list):
        return isinstance(given, list) and sorted(str(v).strip().lower() for v in given) == sorted(
            v.lower() for v in wanted
        )
    if isinstance(wanted, int | float):
        try:
            return abs(float(str(given).replace(",", "")) - wanted) <= slack
        except ValueError:
            return False
    return str(given).strip().lower() == str(wanted).lower()


def vision_score(name: str, text: str) -> Result:
    data, truth = json_in(text), VISION[name][1]
    if data is None:
        return 0.0, f"{name}: no valid JSON"
    wrong = [key for key in truth if not _same(data.get(key), truth[key], SLACK.get(name, 0.001))]
    note = (
        "all right" if not wrong else "wrong: " + ", ".join(f"{key}={data.get(key)!r}"[:50] for key in wrong)
    )
    return 100 * (len(truth) - len(wrong)) / len(truth), f"{name}: {note}"


CRITIC = (
    "You are a design critic. Look at this screenshot of a finished page and report what is visibly broken or would make "
    "a user fail or distrust the page. Only defects that can be seen; no matters of taste, no wishes, no new features. A "
    "false alarm costs as much as a missed defect. If the page is fine, the list is empty. At most 6. JSON only: "
    '{"defects": [{"element": "which", "problem": "one sentence"}]}'
)
CRITIC_FAULTS: dict[str, dict[str, str]] = {
    "form": {
        "pale text": r"contrast|pale|faint|light gr[ae]y|illegible|unreadable|hard to read|barely|too light",
        "button text cut off": r"button.*(cut|truncat|clip|overflow|incomplete)|(cut|truncat|clip).*button",
        "error at the wrong field": r"error|valid|message|invalid",
    },
    "dashboard": {
        "total does not add up": r"total|\bsum|add up|match|inconsisten|differ",
        "text runs over the card": r"overflow|overlap|run[s ]|outside|beyond|spill|cut|clip|bleed|collid",
        "legend has the wrong colour": r"legend|colou?r",
    },
    "phone": {
        "text over text": r"overlap|on top|collid|cover|obscur",
        "broken picture": r"image|picture|photo|broken",
        "cut off at the right": r"cut|clip|overflow|outside|right edge|truncat|off.?screen|beyond",
    },
    "good": {},
}


def critic_score(name: str, text: str) -> Result:
    data = json_in(text)
    if data is None or not isinstance(data.get("defects"), list):
        return 0.0, f"{name}: no valid JSON"
    faults = CRITIC_FAULTS[name]
    found: set[str] = set()
    alarms = 0
    for item in data["defects"]:
        if not isinstance(item, dict):
            continue
        words = f"{item.get('element', '')} {item.get('problem', '')}"
        hits = [fault for fault, pattern in faults.items() if re.search(pattern, words, re.IGNORECASE)]
        fresh = [fault for fault in hits if fault not in found]
        if fresh:
            found.add(fresh[0])
        elif not hits:
            alarms += 1
    if not faults:
        return max(0.0, 100 - 34.0 * alarms), f"{name}: {alarms} false alarms"
    score = 100 * 2 * len(found) / (len(faults) + len(found) + alarms)
    return score, f"{name}: {len(found)} of {len(faults)} found, {alarms} false alarms"
