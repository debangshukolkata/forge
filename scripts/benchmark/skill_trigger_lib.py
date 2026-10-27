"""Pure logic of the skill trigger evaluation (TODO C14): no model call, no network, no file written except in `set_description_in_text`'s caller.

The idea (the method of Anthropic's skill-creator, built here on our own code): for each skill a set of queries that SHOULD make the model load it and a set of
hard near-miss queries that should NOT. The model sees exactly the skills index the agent sees and names the one skill it would load first. A description is good
when the right skill is named for the `should` queries and not named for the `should_not` ones. To avoid fitting the wording of a few queries, each skill's queries
are split 60/40 into train (shown to the rewriting model) and test (only used to choose between candidates)."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
TRIGGERS_FILE = REPO / "tests" / "benchmarks" / "skills" / "triggers.json"
KINDS = ("should", "should_not")
TRAIN_SHARE = 0.6
MAX_QUERY_CHARS = 300
MAX_DESCRIPTION_CHARS = 400

QUESTION = (
    "A user writes: {query}. Which ONE skill from the list, if any, would you load first? "
    "Answer with only the skill name or NONE."
)
SYSTEM = (
    "You are an assistant that can load skills (instruction packs) with load_skill(name). Only each skill's one-line description is visible to you.\n\n"
    "{index}"
)


# ---------- queries ----------


def load_triggers(path: Path = TRIGGERS_FILE) -> dict[str, dict[str, list[str]]]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def check_triggers(triggers: dict[str, dict[str, list[str]]], skill_names: Iterable[str]) -> list[str]:
    """Every problem found in a triggers file, as readable lines (empty list: the file is fine)."""
    known = set(skill_names)
    problems: list[str] = []
    seen: dict[str, str] = {}
    for skill, groups in triggers.items():
        if skill not in known:
            problems.append(f"{skill}: no such skill")
        for kind in KINDS:
            queries = groups.get(kind, [])
            if len(queries) != 10:
                problems.append(f"{skill}.{kind}: {len(queries)} queries, expected 10")
            for query in queries:
                key = query.strip().lower()
                if key in seen:
                    problems.append(f"{skill}.{kind}: duplicate of {seen[key]}: {query[:50]}")
                seen[key] = f"{skill}.{kind}"
                if len(query) >= MAX_QUERY_CHARS:
                    problems.append(f"{skill}.{kind}: {len(query)} characters: {query[:50]}")
                lowered = query.lower()
                for form in {skill, skill.replace("-", " ")}:
                    if form in lowered:
                        problems.append(f"{skill}.{kind}: contains the skill name: {query[:50]}")
    return problems


def split_queries(skill: str, kind: str, queries: list[str]) -> tuple[list[str], list[str]]:
    """Deterministic 60/40 train/test split of one group.

    Each query gets a stable key, the SHA-1 of "skill|kind|query" (not Python's salted `hash`), and the group is ordered by that key: the first 60% (rounded)
    are train, the rest test. So the split does not depend on the order in the file, and adding a query moves few others; with 10 queries it is always 6/4.
    Both kinds are split on their own, so train and test each contain should and should_not queries."""
    ordered = sorted(queries, key=lambda q: hashlib.sha1(f"{skill}|{kind}|{q}".encode()).hexdigest())
    cut = round(len(ordered) * TRAIN_SHARE)
    return ordered[:cut], ordered[cut:]


@dataclass(frozen=True)
class Case:
    skill: str
    kind: str  # "should" | "should_not"
    query: str


def cases_for(triggers: dict[str, dict[str, list[str]]], skill: str, part: str = "all") -> list[Case]:
    """part: "all", "train" or "test"."""
    out: list[Case] = []
    for kind in KINDS:
        queries = triggers[skill].get(kind, [])
        train, test = split_queries(skill, kind, queries)
        chosen = {"all": queries, "train": train, "test": test}[part]
        out += [Case(skill, kind, q) for q in chosen]
    return out


# ---------- the index the model sees ----------


def build_index(skills: dict[str, Any]) -> str:
    """The same text the agent has pinned as `skills` (parity.skills.index_text), nothing re-implemented."""
    from forge.parity.skills import index_text

    return index_text(skills) or ""


def swap_description(skills: dict[str, Any], name: str, description: str) -> dict[str, Any]:
    """A copy of the skills with one description replaced, in memory only: no file is touched."""
    copy = dict(skills)
    copy[name] = replace(skills[name], description=description)
    return copy


def system_prompt(index: str) -> str:
    return SYSTEM.format(index=index)


def question(query: str) -> str:
    return QUESTION.format(query=query)


# ---------- the answer ----------


def parse_answer(text: str, names: Iterable[str]) -> str | None:
    """The skill name the model chose, or None for NONE, an unknown name or no answer.

    Accepts "test-first", "`test-first`.", "Skill: test-first", "I would load test-first first". When several known names appear the earliest wins.
    A reply that starts with NONE is no trigger even if it later mentions a skill ("None. Closest is debugging.")."""
    cleaned = (text or "").strip().strip("`*\"'. \n\t")
    if not cleaned:
        return None
    first_word = re.split(r"[\s.,;:!]+", cleaned.lower(), maxsplit=1)[0].strip("`*\"'")
    if first_word == "none":
        return None
    lowered = cleaned.lower()
    best: tuple[int, int, str] | None = None
    for name in names:
        match = re.search(r"(?<![\w-])" + re.escape(name.lower()) + r"(?![\w-])", lowered)
        if match and (best is None or (match.start(), -len(name)) < (best[0], best[1])):
            best = (match.start(), -len(name), name)
    return best[2] if best else None


def majority(answers: list[str | None]) -> str | None:
    """The answer more than half of the repeats gave; no strict majority counts as no trigger."""
    if not answers:
        return None
    answer, count = Counter(answers).most_common(1)[0]
    return answer if count * 2 > len(answers) else None


# ---------- scoring ----------


@dataclass
class Score:
    should_total: int = 0
    should_hit: int = 0
    not_total: int = 0
    not_false: int = 0  # should_not queries where the skill under test was chosen
    missed: list[tuple[str, str | None]] = field(default_factory=list)  # (query, what was chosen instead)
    false_triggers: list[str] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.should_hit / self.should_total if self.should_total else 0.0

    @property
    def false_rate(self) -> float:
        return self.not_false / self.not_total if self.not_total else 0.0

    @property
    def accuracy(self) -> float:
        total = self.should_total + self.not_total
        return (self.should_hit + self.not_total - self.not_false) / total if total else 0.0


def score_cases(rows: Iterable[tuple[Case, str | None]]) -> Score:
    """rows: (case, the skill the model chose or None). A should query is a hit when the case's skill was chosen;
    a should_not query is a false trigger when the case's skill was chosen (choosing a sibling or NONE is fine there)."""
    score = Score()
    for case, chosen in rows:
        if case.kind == "should":
            score.should_total += 1
            if chosen == case.skill:
                score.should_hit += 1
            else:
                score.missed.append((case.query, chosen))
        else:
            score.not_total += 1
            if chosen == case.skill:
                score.not_false += 1
                score.false_triggers.append(case.query)
    return score


def format_score(score: Score) -> str:
    return f"recall {score.should_hit}/{score.should_total}, false triggers {score.not_false}/{score.not_total}, accuracy {score.accuracy:.0%}"


def confusions(rows: Iterable[tuple[Case, str | None]]) -> Counter[str]:
    """What was chosen instead on missed should queries: a skill name or NONE."""
    return Counter(
        (chosen or "NONE") for case, chosen in rows if case.kind == "should" and chosen != case.skill
    )


def recommend(
    current: tuple[Score, Score], candidates: list[tuple[str, Score, Score]]
) -> tuple[int | None, str]:
    """Pick a candidate from (current train, current test) and [(description, train, test)].

    The best test accuracy among candidates that do not lose on train; ties go to the higher train accuracy, then the earlier one. A candidate must beat the
    current description on test accuracy to be recommended, otherwise the answer is None (keep the current one)."""
    cur_train, cur_test = current
    best: int | None = None
    for index, (_description, train, test) in enumerate(candidates):
        if train.accuracy < cur_train.accuracy:
            continue
        if best is None or (test.accuracy, train.accuracy) > (
            candidates[best][2].accuracy,
            candidates[best][1].accuracy,
        ):
            best = index
    if best is None:
        return None, "every candidate loses on train: keep the current description"
    if candidates[best][2].accuracy <= cur_test.accuracy:
        return None, "no candidate beats the current description on the held-out test queries: keep it"
    return (
        best,
        f"candidate {best + 1} has the best test accuracy ({candidates[best][2].accuracy:.0%} against {cur_test.accuracy:.0%}) without losing on train",
    )


# ---------- rewriting ----------

REWRITE_RULES = (
    "Rules for each description:\n"
    "- start with 'Use when'\n"
    "- be a little pushy: models under-trigger skills, so name the situations and the words people use, and say to load it even when the task looks small\n"
    "- say briefly what it is NOT for, naming the sibling skill when there is one\n"
    f"- under {MAX_DESCRIPTION_CHARS} characters, one line, plain text, no quotes, no shouting (no words in capitals)\n"
)


def rewrite_prompt(
    skill: str,
    current: str,
    failures: list[str],
    false_triggers: list[str],
    count: int,
    siblings: dict[str, str],
) -> str:
    lines = [
        f"The skill `{skill}` has this description:\n{current}\n",
        "Other skills in the list (do not steal their work):",
        *[f"- {name}: {desc}" for name, desc in siblings.items()],
        "",
    ]
    if failures:
        lines += [
            "User messages that SHOULD have made the model load this skill but did not:",
            *[f"- {q}" for q in failures],
            "",
        ]
    if false_triggers:
        lines += [
            "User messages that should NOT load this skill but did:",
            *[f"- {q}" for q in false_triggers],
            "",
        ]
    lines += [
        f"Write {count} different rewritten descriptions for `{skill}`.",
        REWRITE_RULES,
        f"Answer with a JSON list of {count} strings and nothing else.",
    ]
    return "\n".join(lines)


def parse_candidates(text: str) -> list[str]:
    """A JSON list of strings, tolerant of a code fence or a plain bulleted list."""
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(body)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", body, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            return [str(item).strip() for item in data if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [
        re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip() for line in body.splitlines() if line.strip()
    ]


def description_problems(description: str) -> list[str]:
    problems: list[str] = []
    if not description.startswith("Use when"):
        problems.append("does not start with 'Use when'")
    if len(description) >= MAX_DESCRIPTION_CHARS:
        problems.append(f"{len(description)} characters")
    if "\n" in description:
        problems.append("more than one line")
    if re.search(r"\b[A-Z]{4,}\b", description):
        problems.append("shouts in capitals")
    return problems


# ---------- writing a description into SKILL.md (only `tune --apply` calls this) ----------

DESCRIPTION_LINE = re.compile(r"^description:[^\r\n]*", re.M)
FRONT = re.compile(r"\A---\s*\r?\n.*?\r?\n---", re.S)


def set_description_in_text(text: str, description: str) -> str:
    """Replace the `description:` line inside the front matter; the rest of the file stays byte for byte. Raises ValueError without front matter or line."""
    one_line = " ".join(description.split())
    front = FRONT.match(text)
    if front is None:
        raise ValueError("SKILL.md has no front matter")
    block = front.group(0)
    if not DESCRIPTION_LINE.search(block):
        raise ValueError("front matter has no description line")
    new_block = DESCRIPTION_LINE.sub(lambda _m: f"description: {one_line}", block, count=1)
    return new_block + text[len(block) :]
