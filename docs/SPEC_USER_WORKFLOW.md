# Work order: the user's own workflow (WF1 to WF4)

Written 2026-11-16 from a discussion with the user (D-620) and a reading of the code named below.
The items are in TODO.md section 0q; this file says exactly what to build for each.
**Who does what:** a smaller model builds from this file; the analysis model reviews the result and runs the
live measurements afterwards (`WF5`).

## 1. Why

The user (tech lead of WisdomNext) described how they fix a bug and build a similar part by hand. DebCraft
already does most of it (skill `solve-against-running-system`, TODO 0h to 0p). Four things are missing:

| Item | The user does by hand | DebCraft today |
|---|---|---|
| `WF2` | Comments out or stubs a dependency that is not the cause, adds logs, and takes both out before committing | Edits the application to get past the failure (`RS8`: the copy tools used in 0 of 6 runs); nothing keeps such edits or added logging out of `output/` |
| `WF1` | Runs the same call on dev when the local run disagrees, and compares | Can call the dev host (`http_request`, D-603) but never compares |
| `WF4` | Knows how the application is run | Run notes are kept per project (`.forge/run_notes.json`, D-597); a second project on the same repository starts without them |
| `WF3` | Builds a Confluence agent by studying the SharePoint agent | No procedure |

What the code does today (read 2026-11-16):

- `output/` is built by `build_output` in `src/forge/workspace/output.py`. `compute_changes` compares every
  file of the copy with the manifest; `build_output` copies each changed file with `shutil.copy2`;
  `file_texts` gives the before and after text for `changes.patch` and `CHANGES.md`. Callers: `cli.py`
  (`_export`), `engine/slash_commands.py`, `workflow/orchestrator.py` (`_export`).
- `edit_file`, `multi_edit` and `write_file` (`src/forge/tools/files.py`) all save through `_save`, which
  already takes a `reason`.
- A turn ends in `src/forge/agent/loop.py` through a chain of checks, each of which may add one system
  message and continue (to-do items, risks, `knowledge_finish_note`, the proof call, the stop hook).
- A second model already reviews hand-offs: `src/forge/tools/handoff_review.py` (`context.ask_model("reviewer", ...)`,
  a JSON verdict, any failure means "no objection"). Use it as the pattern.
- `http_request` (`src/forge/tools/http_request.py`) may call this machine and
  any other http(s) address without a question (D-621). A token goes only to this machine and to the
  hosts of `<DebCraft Home>/app_logins.yaml` (`_token_may_go_to`); a token of such a host comes from
  `ensure_token`.
- `RunNotes` (`src/forge/workspace/run_notes.py`) is written by `start_background`
  (`toolkit/background.py`) and `http_request`, and pinned under the key `run_notes`
  (`context/pinned.py`, `engine/session_host.py`).
- The repository's shared folder is `knowledge_store(workspace)` in `src/forge/tools/code_map_tool.py`.

**Not in this work order** (each needs the user or the analysis model): the live measurements (`WF5`); anything for Mode B; a tool that stubs a function without editing the source
(option A of D-620, not chosen).

## 2. Rules for the builder

1. Read `CLAUDE.md` first. Before changing a module read its `MODULE.md` (`src/forge/tools/`,
   `src/forge/workspace/`, `src/forge/agent/`, `src/forge/engine/`, `src/forge/context/`), and update it when
   you add something.
2. Build in this order: WF2, WF1, WF4, WF3. Finish and test one before starting the next.
3. **Do not commit and do not push.** Before you start, run `git status --short` and copy its output into
   your report (section 9).
4. Change nothing that an item does not name. Tool descriptions, the skill and the system prompt change
   **only with the exact words given here**. No new dependency. No change to the UI.
5. Tests: no fake model. Loop tests drive a real `SessionHost` with `mocked_router(handler)` from
   `tests/helpers.py` (see `tests/test_agent_loop.py`); pure functions are tested directly.
6. While working run `.venv\Scripts\python scripts\dev\quick_check.py`. When all items are done run once:
   `.venv\Scripts\python -m pytest -q -n 6 --dist loadfile -m "not browser and not live"`, then
   `.venv\Scripts\python -m ruff check .`, `.venv\Scripts\python -m ruff format --check .`,
   `.venv\Scripts\python -m mypy`. Put the real last lines of each into the report.
7. **Run no live test.** The analysis model runs them (`WF5`).
8. Change Python source with the edit tool, never with a shell heredoc (see CLAUDE.md, "Patching source").
9. Imports may only go to earlier tiers (`tests/test_module_boundaries.py`). If an item cannot be built in
   the file named here without breaking that test, stop and report.
10. Stop and report, without guessing, when: the code is not as this file describes it; a test you did not
    write fails and the cause is not your change; the same failure happens three times.
11. Each item gets one entry in `docs/DECISIONS.md` (the next free number after D-620; same form as the
    entries above it) and its line in TODO.md section 0q is updated (`[~]` with what is built and what is
    not measured yet; never `[x]`: the reviewer closes items).

## 3. WF2: temporary changes are recorded, taken out of the delivery and reported

**Goal:** a change made only to investigate (a bypassed dependency, added logging) can stay in the copy
while the model works, never reaches `output/`, and is named in the delivery. A change the model did not
mark is found by a second model before the turn ends.

### 3.1 The record: new file `src/forge/workspace/temporary_edits.py`

Stored in `<project>/.forge/temporary_edits.json` (written through `workspace.jail.check`, a `.tmp` file
and `replace`, like `RunNotes._save`):

```json
{"version": 1, "next_id": 3, "entries": [
  {"id": 1, "path": "app/service.py", "kind": "bypass", "reason": "...", "op": "edit",
   "hunks": [{"old": "...", "new": "..."}], "state": "active", "at": "2026-11-16"}
]}
```

- `kind`: `"bypass"` or `"logging"`. `op`: `"edit"` or `"create"` (a whole new file; `hunks` is empty).
  `state`: `"active"` or `"removed"`.
- `hunks_between(before: str, after: str) -> list[dict[str, str]]`: split both texts with
  `splitlines(keepends=True)`, run `difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)`
  and take `get_grouped_opcodes(3)`. For each group: `old` = the before lines from the group's first `i1`
  to its last `i2`, joined; `new` = the after lines from the first `j1` to the last `j2`, joined. The three
  lines of context make both sides findable.
- `class TemporaryEdits(workspace)` with: `load()`, `add(path, kind, reason, op, hunks) -> int`,
  `active(path: str | None = None) -> list[dict]`, `mark_removed(ids)`, and
  `without(path, text) -> tuple[str, list[dict]]`: for the active entries of `path`, newest first, replace
  each hunk's `new` by its `old` when `new` occurs **exactly once** in the text. Hunks of one entry are
  all applied or none. Returns the text and the entries that could not be taken out.
- A broken or missing file loads as empty (like `RunNotes.load`).

### 3.2 Marking: `src/forge/tools/files.py`

Add to the `Args` of `edit_file`, `multi_edit` and `write_file`:

```python
temporary: Literal["", "bypass", "logging"] = Field(default="", description=TEMPORARY_HELP)
```

`TEMPORARY_HELP` (exact words): "Set it when this change is only there to investigate and must not be
delivered. `bypass`: a dependency is skipped, stubbed or pointed somewhere else so the code you are working
on can run. `logging`: added log or print lines. Give `reason` (for a bypass: what is bypassed and why it is
not the cause). The change stays in the copy, is taken out of the delivered files and is named in the report."

Behaviour when `temporary` is set:

1. `reason` empty: `ToolResult(ok=False, "A temporary change needs `reason`: what it bypasses or logs, and why.")`
2. `workspace.mode_b`: refused with "Temporary changes are for a project on an existing repository."
3. `write_file` on a file that exists: refused with "Use edit_file for a temporary change to an existing file."
4. Otherwise save as today. When `_save` returned `ok=True`: `add(...)` with `op="create"` for a new file,
   else `op="edit"` and `hunks_between(before, after)` (read the text before the save and the text passed to
   `_save`). Append to the result: "Recorded as temporary change #N (kind): it will not be delivered. Take it
   out with temporary_edits when you no longer need it."

### 3.3 The tool: new file `src/forge/tools/temporary.py`, tool `temporary_edits`

Put it into a group in `src/forge/tools/deferred.py` named `investigation` (it is loaded when called).
Description (exact words): "Lists, removes or records the temporary changes of this project (a bypassed
dependency, added logging). `list`: what is recorded. `remove`: takes the changes with these `ids` (or all)
out of the copy again. `mark`: records a change you already made without `temporary`: give `path`, `text`
(the lines as they are in the file now), `original` (what stood there before; empty when the lines were only
added), `kind` and `reason`."

- `list`: one line per entry: `#id kind path (state): reason`.
- `remove`: for each file, `without(path, current text)`, then save through the same function the edit
  tools use (`_save` in `files.py`, reason "temporary change #N taken out"; if the linter objects to the
  private name, add a public wrapper in `files.py`). An entry with `op="create"`: delete the file the way
  `delete_file` does, without asking. Mark removed. Entries that could not be taken out are listed with
  "change the file by hand, then call remove again".
- `mark`: `text` must occur exactly once in the file, else refuse with the count. `after` = the current
  text, `before` = the current text with `text` replaced by `original`; record `hunks_between(before, after)`.
  The file is not changed.

### 3.4 The delivery: `src/forge/workspace/output.py`

1. New function `delivered_bytes(workspace, relative) -> tuple[bytes, list[dict]]`: when the file has no
   active entry, the file's bytes and `[]`. Otherwise decode as `workspace.read_text` does, apply
   `TemporaryEdits.without`, encode with the same format `workspace.write_text` would use (find the encoder
   in `workspace/text_format.py`; BOM and line endings must be kept), and return the entries that could not
   be taken out.
2. `compute_changes`: use `delivered_bytes` for the hash. A file whose active entry has `op="create"` is
   not a change. A file whose delivered bytes equal the manifest's hash is not a change. `FileChange` gets
   `temporary_left: list[str] = []` (the reasons of entries that could not be taken out).
3. `build_output`: write `delivered_bytes` for files with active entries (`target.write_bytes`), `copy2`
   for the others as today.
4. `file_texts`: the "after" text is the delivered text.
5. `OutputManifest` gets `temporary: list[dict[str, str]] = []` (kind, path, reason, state of every entry,
   active or removed).
6. `build_changes_md`: when there are entries, a first section:

   ```
   ## Temporary changes (not in these files)

   - bypass, app/service.py: <reason>. The solution was proved with this in place; it was not exercised.
   - logging, app/agent.py: <reason>.
   ```

   and under a file with `temporary_left`: "**This file still holds a temporary change DebCraft could not
   take out: <reason>. Remove it by hand before you copy the file.**" The same sentence goes into the
   file's row in `build_copy_instructions`.

### 3.5 Before the turn ends: `src/forge/agent/loop.py`

Add two checks after the proof-call check and before the stop hook, each at most once per turn, main agent
only (`self.keep_full_output`), not in plan mode.

**(a) Active temporary changes.** When the set of active ids differs from the set this check last reported
(keep it on the `ToolContext`), add the system message (exact words):

"Temporary changes are still in the copy:\n{one line per entry: #id kind path: reason}\nFor each: if you no
longer need it, take it out (temporary_edits, action remove) and run your check again. If the check cannot
run without it, leave it and write in your report: 'Proved with <what> bypassed; <what> was not exercised.'
They are taken out of the delivered files either way."

Notice: kind `temporary_changes`, text "Naming the temporary changes before finishing."

**(b) Leftovers nobody marked.** New file `src/forge/tools/leftover_review.py`, function
`async review_leftovers(context) -> str | None`, built like `review_hand_off`. It runs only when a file was
changed in this turn (use the record `_calls_to_repeat_after_change` uses), the project has a repository and
is not Mode B, and the diff differs from the one reviewed last (keep a hash on the `ToolContext`).

- The diff: the paths of `workspace.changes()`, without secret files (`workspace.is_secret`), each as a
  unified diff of `file_texts` (so marked changes are already out). Run in `asyncio.to_thread`. Pass it
  through `default_redactor.redact`. Over 60,000 characters: cut the largest files' diffs and say so in a line.
- The question: the user's last messages (`context.recent_user_messages()`), then the diff.
- The system text (exact words):

  "You check code changes before they are handed to the user. DebCraft is a coding agent that fixed or
  extended something in a copy of the user's repository. While investigating, such an agent often changes
  code only to get the application running or to see what happens, and forgets to take it out. Find those
  leftovers in the diff.\n\nA leftover is: a call, a check or a block that was commented out or deleted
  although the requirement does not ask for it; a function made to return a fixed value or to return early;
  an exception swallowed so that a failing dependency is ignored; a setting, an address or a credential name
  hard-coded or pointed at another environment; print or log lines that only trace the investigation; a
  skipped or weakened test.\nNot a leftover: anything the requirement asks for; logging that is part of the
  feature; error handling the fix needs and that still reports the error.\nWhen unsure, do not list it.\n\n
  Answer with JSON only: {\"leftovers\": [{\"path\": \"...\", \"lines\": \"the changed lines, at most 3\",
  \"why\": \"one sentence\"}]} with an empty list when there is none."

- No leftovers, a failed call or an answer that is not this JSON: return `None`.
- Otherwise return (exact words): "Before you finish: a second model read your changes and found what may
  be leftovers of the investigation:\n{- path: lines (why)}\nFor each one: if it is part of the solution,
  say so in one line in your report. If it was only there to investigate, take it out now, or, when your
  check cannot run without it, record it with temporary_edits (action mark): it then stays in the copy, is
  taken out of the delivered files and is reported."
- Notice: kind `leftover_review`, text "A second model is reading the changes for investigation leftovers."

### 3.6 Tests (new file `tests/test_temporary_edits.py`, and additions where the edit tools and `build_output` are tested)

1. `hunks_between` and `without`: an added line, a replaced block, a deleted block, two hunks in one file;
   an entry whose `new` text was changed afterwards is returned as not taken out and the text is unchanged.
2. `edit_file` with `temporary="logging"`: the copy holds the line, `output/` does not, `CHANGES.md` names it.
3. A file whose only change is temporary is not in `output/` at all.
4. A file with a real fix and a bypass: `output/` holds the fix and the original dependency call;
   `changes.patch` shows only the fix; `MANIFEST.json` lists the entry.
5. `write_file` with `temporary` on a new file: not delivered; `remove` deletes it.
6. `temporary` without `reason`, in Mode B, and `write_file` on an existing file: each refused.
7. `temporary_edits`: `list`, `remove` (the copy is back to the text before), `mark` (then not delivered).
8. A CRLF file and a file with a BOM keep both in `output/` after a temporary change is taken out.
9. Loop (mocked router): with an active entry the turn gets the message of (a) once, and not again in the
   next turn while the set is unchanged.
10. Loop (mocked router, the reviewer role answering through the handler): a leftover verdict adds the
    message of (b); an empty list, an exception and a non-JSON answer add nothing; an unchanged diff is
    not reviewed twice.

**Done when:** the tests pass and a project that never uses `temporary` builds byte-identical `output/`
files as before (test 4's fixture without the bypass).

## 4. WF1: compare a local call with the same call on another environment

**Goal:** when the local run disagrees, one call shows what differs from dev. Agreed with the user: no
forced dev run. **No card of any kind** (the user, 2026-11-16, D-621: every HTTP call goes out when it is
needed; `http_request` no longer asks before calling a host).

**Files:** `src/forge/tools/http_request.py`; new `src/forge/tools/http_compare.py` (the pure comparison).
Read first: `src/forge/toolkit/app_logins.py` (`EnvLogin`, `login_for_token`, `ensure_token`).

1. New arguments: `compare_with: str = ""` (the name of an environment in `app_logins.yaml`) and
   `compare_path: str = ""` (the path on that environment when it differs from the local one).
2. Refuse before sending when `compare_with` is set and: the URL's host is not local ("compare_with
   compares a call on this machine with the same call on an environment"); the name is not in the file
   (list the names that are); `stream` or `keep_secret` is also set.
3. Make the local call exactly as today. If it raised (`TimeoutException`, `HTTPError`), return as today.
4. Then the second call: `https://<the environment's host>` + `compare_path` or the local path, with the
   local query string, the same method, body and headers, and the environment's own token placed the way
   `token_in`, `token_header` and `token_prefix` say (`ensure_token`; never the local token).
5. No card, whatever the method. When the second call fails or times out, the local result is returned
   with the line "Not compared: <the reason>."
6. The result is the local result as today, followed by:

   ```
   Compared with <environment> (<url>):
   - status: here 500, <environment> 200
   - size: here 312 characters, <environment> 4,881
   - only in the answer of <environment>: result.items, result.total
   - only in the answer here: error
   - different values (first 10): <path>: here <value> | <environment> <value>
   The answer of <environment> is kept whole in <file>.
   ```

   `compare_answers(here_status, here_text, there_status, there_text, name) -> list[str]` in
   `http_compare.py`: both JSON: flatten to dotted paths (list items by index, the first 20 of a list, at
   most 400 paths), values cut at 120 characters. Otherwise: status, size, and the first line that differs.
   When nothing differs: "- no difference in status or content". Every value passes the redactor and both
   tokens are replaced by "[token hidden]". The second answer is kept with `context.cap_output`.
7. The second call is **not** written to the run notes and does not touch `context.api_calls`.
8. A hint: when a local call answers 500 or higher, `compare_with` is empty and the file names at least one
   environment, append (at most twice per session; a counter on the `ToolContext`): "If the same call works
   on <names>, call again with compare_with=\"<first name>\" to see what differs."
9. Add to the tool description, after the sentence about `stream` (exact words): "`compare_with`: the name
   of an environment from the user's app_logins.yaml: after the call here, the same call is made there and
   the result lists what differs (status, size, fields). Use it when the application here fails or answers
   differently from what was reported. The call runs there for real, so compare only the call you are working on."
10. Add to `src/forge/skills/solve-against-running-system/SKILL.md`, as the last bullet of section 5 (exact
    words): "- **When the run here fails for a reason that may be this machine** (a setting, missing data),
    or does not show the reported problem at all: make the same call with `compare_with` = the environment
    the report came from. What differs tells you whether you are looking at the problem or at your setup.
    When the run here already shows the reported problem, you do not need it."
11. Field log (`src/forge/toolkit/field_log.py`): one line per comparison: environment name, method, both
    statuses, the number of differing fields, seconds. Never a value. Give `WF1` a verdict in `src/forge/engine/laptop_report.py` (PASS when at least one comparison
    with two statuses is in the log, NOT RUN otherwise), in the form of the verdicts already there.

**Tests** (in the file that tests `http_request` with a remote host, see `tests/test_app_logins.py`):
`compare_answers` directly (JSON with differences, equal answers, non-JSON, a token inside a value is
hidden); a GET and a POST are both compared with nobody asked; a second call that fails gives
"Not compared"; each refusal of step 2; the hint appears on a 500 and at most twice; the second call is not in `run_notes.json`.

**Done when:** the tests pass and a call without `compare_with` returns exactly what it returned before.

## 5. WF4: how the repository was run, shared by its projects

**Goal:** a new project on the same repository sees how an earlier project started the application and
called it. Names only, never values.

**Files:** `src/forge/workspace/run_notes.py` (the shared file), `src/forge/engine/session_host.py` (when it
is written and pinned), `src/forge/context/pinned.py` (the new block).

1. In `run_notes.py` add `class RepositoryRunNotes(folder: Path)`, file `<folder>/run.json`:

   ```json
   {"version": 1,
    "starts": [{"name": "", "command": "", "cwd": "", "settings": [], "project": "", "at": ""}],
    "calls": [{"method": "", "path": "", "body": "", "token_env": "", "stream": false, "project": "", "at": ""}],
    "bypasses": [{"path": "", "reason": "", "project": "", "at": ""}]}
   ```

   `merge(workspace)`: read the project's `RunNotes` and `TemporaryEdits` and take over:
   - starts: without the port; `cwd` made relative to `workspace.repo_dir` (empty when it is the root or
     outside it); in `command`, the text of `workspace.repo_dir` replaced by `<repo>`. Same `name` replaces.
   - calls: only calls to a local host; `path` is the URL's path. Same method and path replaces.
   - bypasses: every entry of kind `bypass`, active or removed. Same path and reason replaces.
   - `project` is the project's name (`workspace.info.name`). Keep the newest 6 starts, 8 calls, 10 bypasses.
   - Write only when the content changed; `.tmp` then `replace`. The folder is under DebCraft Home, not in
     the workspace: create it the way the topic notes do (`src/forge/knowledge/`, find where a topic file
     is written) and do not send the path through the workspace jail.
   `render(leave_out_project: str) -> str | None`: the entries of other projects, as lines like
   `RunNotes.render`, with `(project <name>, <date>)` at the end, and for a bypass: "- Bypassed in <path>:
   <reason>". Before the lines (exact words): "Recorded by DebCraft in other projects on this repository
   (names only, never values). Try this way first; it may be out of date, so check the first result before
   you rely on it."
2. `session_host.py`: after every turn, where the after-turn notices are posted (the relay's report of
   D-610 is one), call `RepositoryRunNotes(knowledge_store(workspace)).merge(workspace)` in
   `asyncio.to_thread`; not in Mode B and not in a project without a repository. At session start, where
   `run_notes` is pinned, pin `repo_run_notes` with `render(workspace.info.name)`.
3. `pinned.py`: the key `repo_run_notes` directly after `run_notes`, title "How this repository was run in
   another project (check before relying on it)".
4. Field log: at session start one line with the number of starts, calls and bypasses shown from other
   projects. Verdict `WF4` in `laptop_report.py` (PASS when a session showed at least one, NOT RUN otherwise).

**Tests** (`tests/test_run_notes*.py`, or a new `tests/test_repository_run_notes.py`): two workspaces made
from the same repository folder: after `merge` in the first, `render` in the second shows its start and
call; the port and the absolute folder are not in the file; a call to a remote host is not taken over; a
value that the redactor masks in the project's notes is masked in `run.json`; the project's own entries are
left out of its own block; an unchanged merge does not rewrite the file (compare the modified time).

**Done when:** the tests pass and the time to open a project is not longer (time `SessionHost(...)` on the
fixture repository before and after, three times each; put the six numbers into the report).

## 6. WF3: skill `build-similar-part`

**Goal:** a procedure for "build X like the existing Y". No new tool.

1. New file `src/forge/skills/build-similar-part/SKILL.md` with exactly the text in section 7. If shipped
   skills carry a `tools:` line in their header (`grep -l "^tools:" src/forge/skills/*/SKILL.md`), add one
   in the same form naming `http_request`, `code_map`, `knowledge_search`, `knowledge_write`; if none does,
   leave it out.
2. In `src/forge/agent/prompts/system.md`, directly after the sentence that names
   `solve-against-running-system` (line 152), add (exact words): "When the user asks for a part that is
   like one the system already has (an agent, a connector, an endpoint, a tool: 'like the existing ...',
   'similar to ...', 'the same for ...'), load the skill `build-similar-part` and follow it." If a second
   system prompt names `solve-against-running-system` too, add the same sentence there.
3. Run the tests that check the shipped skills (`pytest tests/test_skill*.py -q`) and fix what they ask
   of a new skill (a description, a registry entry).

**Done when:** those tests pass and `load_skill("build-similar-part")` returns the text in a session test.

## 7. The text of `build-similar-part/SKILL.md`

```markdown
---
name: build-similar-part
description: Builds a new part of an existing system that is like one it already has, by studying the existing one while it runs. Use when the user asks for an agent, a connector, an endpoint, a tool or a job "like the existing ...", "similar to ...", "the same for ..." (for example a Confluence agent beside the SharePoint agent), and whenever a new part must fit the way the system already extends itself.
---

# Building a part that is like an existing one

The existing part (the reference) is the specification. Copying its files is not: half of what makes it
work is outside them (rows in tables, a registration, settings, a permission), and half of what is inside
them is true only of the service it talks to. Work in this order.

## 1. See the reference work

- `knowledge_search` first: an earlier project may have described how such parts are built.
- Find its door with `code_map` (`endpoints`, `endpoint`) and call it with `http_request` the way its users
  do. Where the reference needs real configuration that this machine lacks, call it on the environment
  where it works (a host from the user's app_logins.yaml). Keep the request and the answer: the new part
  must answer in the same shape.
- If it cannot be run anywhere, say so in your report and go on from the code and its tests.

## 2. Write down how it is wired

Follow the reference from its door to the outside service (`code_map` `callees`, `tables`, `env`) and list,
with file and line or table and row:

- the route or command that starts it, and where that is registered;
- the rows that define it (agents, tools, connectors are often data): read them with `db_query`;
- the shared code it uses (file handling, the model gateway, authentication helpers): the new part uses the
  same, it does not get its own copy;
- its settings and secrets, by name;
- its tests.

## 3. Same and different, before any code

Write a two-column list (todo_write or a note) and show it in your report:

| | The reference | The new part |
|---|---|---|
| How it signs in to the outside service | | |
| How results are paged | | |
| Limits (rate, size) and what happens when they are hit | | |
| What a unit of content is, and its identifiers | | |
| Permissions: who may see what | | |
| Errors the service returns and how they are told apart | | |

Fill the right column from the outside service's own documentation or by calling it, not from the
reference. Every row where the two differ is code you must write new; every row where they agree is code
you must reuse.

## 4. Build it the way the system extends itself

- Add the new part where the reference lives, in the same form (a module beside it, a row beside its row).
- Use the shared code from step 2. If a piece of the reference is needed by both and sits inside the
  reference, move it to a shared place only when that is a small change; otherwise say so in the report
  and leave the decision to the user.
- If it needs rows, write them in your copy of the database and deliver them as a migration or seed
  statement.
- Add tests in the form of the reference's tests.

## 5. Run the new part through the same door

- Start the copy and call the new part with `http_request`, in the shape you kept in step 1.
- Run the reference once more: it must answer as before.
- Credentials for the new outside service: the user puts them into `app.env`; ask once, by name, and never
  for a value in the chat.

## 6. Report and remember

The same/different list; what was reused; what was written new; what the user has to apply (files, the
data statement, settings by name); what you could not run and why. Write how such a part is built with
`knowledge_write`, so the next one starts from step 3.
```

## 8. Answered by the user, and a limit (not for the builder)

1. **Answered 2026-11-16 and built (D-621):** every HTTP call goes out when it is needed, to any address,
   without a question. The red card is only for a direct INSERT or UPDATE on the Development DB.
2. The comparison shows the answers only. The commit and the settings of the other environment are not
   visible to DebCraft unless the application has an endpoint that reports them.

## 9. Report (the builder fills this in)

- `git status --short` before the first change:
- Per item (WF2, WF1, WF4, WF3): files changed; tests added (names); what differs from this file and why;
  what was not built.
- The six open times of WF4:
- Last lines of the full test run, `ruff check`, `ruff format --check`, `mypy`:
- Anything that made you stop:
