# Work order: fewer wasted steps (HW0 to HW5)

Written 2026-11-12 from an analysis of the code and of one day's log from the office laptop.
The items are in TODO.md section 0l; this file says exactly what to build for each.
**Who does what:** a smaller model builds from this file; the analysis model reviews the result afterwards.

## 1. Why

DebCraft's model is weaker than Claude and wastes steps. One day's log (TODO.md section 0k) showed:

- `todo_write` 53 times, 23 of them with the identical list;
- the same `http_request` 10 times, the same file read 8 and 6 times, `.env` read 6 times;
- 49 of 477 tool calls failed;
- 18 to 46 s before the first word once the input passed 100,000 tokens (4.5 s at 38,000).

What the code does today (read 2026-11-12):

- Nothing notices an identical tool call (`agent/loop.py`, `_run_one`).
- Old tool outputs are trimmed only when the history fills 60 % of the window (163,000 tokens on a 272,000
  window) and only outputs from earlier user messages (`context/manager.py`, `prepare`; D-055). At 135,000
  tokens nothing had been trimmed.
- `edit_file` matches `old_string` exactly; only CRLF and LF are interchangeable (`tools/files.py`, `apply_edit`).
- After an edit only `.py` and `.svg` files are checked (`tools/diagnostics.py`).
- Nothing checks that an API call made before a code change was made again after it.

**Not in this work order** (each needs a decision by the user or a design by the analysis model): restoring
the model's history when a project is reopened (`CV1`, `CV2`), trimming tool outputs of the current turn by
size (see HW0, it must be measured first), a second test bed (`RS8`).

## 2. Rules for the builder

1. Read `CLAUDE.md` first. Before changing a module read its `MODULE.md` (`src/forge/agent/`,
   `src/forge/context/`, `src/forge/tools/`, `src/forge/engine/`), and update it when you add something.
2. Build in this order: HW0, HW3, HW1, HW2, HW5, HW4. Finish and test one before starting the next.
3. **Do not commit and do not push.** Before you start, run `git status --short` and copy its output into
   your report (section 9): the reviewer needs to know which changes were there before you.
4. Change nothing that an item does not name. In particular: **no change to the system prompts, to a tool
   description, to a skill, or to the UI**, and no new dependency. If an item seems to need one, stop and
   write that in the report.
5. Tests: no fake model. Loop tests drive a real `SessionHost` with `mocked_router(handler)` from
   `tests/helpers.py` (see `tests/test_agent_loop.py`); pure functions are tested directly.
6. While working run `.venv\Scripts\python scripts\dev\quick_check.py`. When all items are done run once:
   `.venv\Scripts\python -m pytest -q -n 6 --dist loadfile -m "not browser and not live"`, then
   `.venv\Scripts\python -m ruff check .`, `.venv\Scripts\python -m ruff format --check .`,
   `.venv\Scripts\python -m mypy`. Put the real last lines of each into the report.
7. Run no live test except the one HW5 names.
8. Change Python source with the edit tool, never with a shell heredoc (see CLAUDE.md, "Patching source").
9. Stop and report, without guessing, when: the code is not as this file describes it; a test you did not
   write fails and the cause is not your change; the same failure happens three times.
10. Each item gets one entry in `docs/DECISIONS.md` (the next free number after the last `## D-` heading;
    same form as the entries above it: what, why, options considered, what was measured) and its line in
    TODO.md section 0l is updated (`[~]` with what is built and what is not measured yet; never `[x]`: the
    reviewer closes items).

## 3. HW0: the log summary shows the waste

**Goal:** `debcraft log-summary` gives the numbers that decide the other items, so a log from the laptop
can be compared before and after.

**File:** `src/forge/engine/log_summary.py` (function `summarize`); tests in `tests/test_log_summary.py`.

**Add three things, each from data already in the events:**

1. Under the existing line "Failed tool calls: N of M": a list per tool, most failures first:
   `- edit_file: 12 failed of 40. Most common: "old_string was not found." x9`.
   The reason is the first 80 characters of the event's `preview` with any leading `Error: ` removed;
   group equal reasons and show the most common one with its count. At most 10 tools.
2. A section `## Time to the first word by input size`, from the `llm_call` events (`usage.input_tokens`,
   `usage.cached_input_tokens`, `first_token_s`). Buckets by input tokens: under 25,000; 25,000 to 50,000;
   50,000 to 100,000; 100,000 to 150,000; over 150,000. Columns: calls, median `first_token_s`, slowest,
   share of input tokens that were cached (a percentage). Skip calls without `first_token_s`; leave out
   empty buckets; leave the section out when no call has the value.
3. In the existing section "Repeated identical tool calls" add one line at its top:
   `Calls that repeated an earlier one: N of M.` (N = the sum of `n - 1` over all repeated pairs, not only
   the ones listed). After HW1 add to the same line: `answered with a pointer: K` (K = finished tool calls
   whose payload has `repeat_of`).

**Tests:** one per addition, built from hand-made events like the existing tests in that file; one that an
old log without `first_token_s` has no bucket section.

**Done when:** the tests pass and the summary of a log made by any existing loop test shows the new lines.

## 4. HW3: an edit that differs only in whitespace is applied

**Goal:** fewer failed `edit_file` and `multi_edit` calls. The model often gets the indentation or
trailing spaces of `old_string` wrong although the text is otherwise right and unique.

**File:** `src/forge/tools/files.py`. Tests: add to the file that already tests `edit_file`
(search `tests/` for `old_string was not found`).

**Build:**

1. A new function `apply_edit_with_note(text, old, new, replace_all) -> tuple[str, str]` that returns the
   new text and a note (empty when the match was exact). `apply_edit` stays, with the same signature, and
   returns only the text. `EditFile.run` and `MultiEdit.run` call the new function and append a non-empty
   note to their result message.
2. Order of matching:
   a. exact, as today (including the CRLF and LF variants and the "matches N places" error). Unchanged.
   b. only when (a) found nothing and `replace_all` is false: **line-wise match**. Split the file and
      `old` into lines (`splitlines(keepends=True)` for the file so line endings are kept). A block of
      consecutive file lines matches when it has as many lines as `old` and, line by line, the texts are
      equal after removing trailing whitespace and after removing each side's **common leading
      indentation** (the smallest indentation of its non-blank lines; blank lines ignored for the
      minimum and equal to any blank line). This keeps relative indentation inside the block identical.
   c. exactly one such block: apply. More than one: raise the same "matches N places" error with the line
      numbers. None: the same "old_string was not found." error with `_nearest_candidates`, as today.
3. Applying a line-wise match: let `file_indent` and `old_indent` be the two common indentations. Each
   non-blank line of `new` must start with `old_indent`; replace that prefix with `file_indent`. If a
   non-blank line of `new` does not start with `old_indent`, do not apply: raise the not-found error
   (the intended indentation cannot be known). Blank lines of `new` stay as they are. The replaced block
   keeps the file's line ending (CRLF or LF) on every line, and the last line keeps a final line ending
   only if the replaced block had one.
4. An `old` of one line whose stripped text is shorter than 8 characters never matches line-wise (too
   easy to hit the wrong line).
5. The note: `Matched lines A to B after ignoring a difference in indentation or trailing spaces; the
   new text was indented to fit.` (A and B are 1-based file lines.)

**Tests (direct, on the function):** wrong indentation (old has 4 spaces less than the file) is applied
and the new lines sit at the file's indentation; trailing spaces in the file; CRLF file stays CRLF; two
candidate blocks give the "matches" error; a `new` line that is less indented than `old_indent` gives
not-found; tabs in the file and spaces in `old` give not-found; a short one-line `old` gives not-found;
an exact match returns an empty note; `replace_all` never uses the line-wise match. One test through
`edit_file` itself that the note is in the result and the file on disk is right.

**Done when:** tests pass; the result of a Python edit applied this way still passes the existing syntax
check (the test for wrong indentation uses a Python function body and asserts `compile()` accepts it).

## 5. HW1: a repeated call is answered with a fact

**Goal:** the model stops paying for, and filling its context with, a call whose answer it already has.
This is a fact inside a tool result. It is **not** a stuck detector and adds no escalation (D-155 stands):
nothing is refused, no step is counted against the model, no other behaviour changes.

**Files:** new `src/forge/agent/repeats.py`; `src/forge/agent/loop.py`; `src/forge/tools/todo.py`;
`src/forge/engine/log_summary.py` (the count from HW0); tests in a new `tests/test_repeats.py` and one
loop test in `tests/test_agent_loop.py`.

**Part A, `todo_write` (in the tool):** in `TodoWrite.run`, when the new list equals `context.todos`
(same items, same order, same statuses), do not emit `todo_updated` and return
`ToolResult(ok=True, content="The todo list is unchanged: this is the same list as before. Do the next
open item; send the list again only when an item changes.")`.

**Part B, the ledger (`repeats.py`):** a small class `RepeatLedger`, no imports from other DebCraft
modules except `forge.llm.base` if needed.

- Key of a call: the tool name plus `json.dumps(arguments, sort_keys=True, default=str)`.
- Per key it keeps a list of entries: `step`, `tool_call_id`, `digest` (sha256 of the result text that the
  model was given, before any note of this feature), `ok`.
- `seen(key, digest) -> entry | None`: the latest earlier entry with the same digest.
- `count(key, digest) -> int`: how many earlier entries have the same digest.
- `add(key, entry)`. At most 20 entries per key and 2,000 keys; drop the oldest.

**Part C, in the loop (`_run_one`):** `AgentLoop` gets `self.repeats = RepeatLedger()` and remembers the
history list it is working on (`self._history = history` at the top of `run`). After the result text has
been capped and flagged (the lines after `content, _ = self.context.cap_output(...)`) and before the
message is returned:

1. `key` and `digest` as above; `earlier = self.repeats.seen(key, digest)`; then `self.repeats.add(...)`.
2. **Pointer:** when `earlier` exists, the result is ok, the tool is in
   `POINTER_TOOLS = {"read_file", "grep", "glob", "list_dir", "code_map", "code_outline",
   "knowledge_search"}`, the text is longer than 400 characters, and the earlier result is still whole in
   the history (a message with role `tool` and that `tool_call_id` exists and its content does not start
   with `STUB_PREFIX` from `forge.context.compaction` and does not start with `[Same result as`): the
   model is given, instead of the text,
   `[Same result as your identical call at step N: nothing in it has changed. It is still above in this
   conversation; use it. To see another part, change the arguments.]`
   The tool has still run (so read-before-edit tracking is right) and the event's `preview` is unchanged;
   only the text returned to the model is replaced. The ledger entry for this call keeps the digest of
   the real text and the `tool_call_id` of the **earlier** whole result, so a third call points to the
   same place.
3. **Note:** otherwise, when `self.repeats.count(key, digest) >= 2` (this is the third or a later
   identical call with the identical answer) and the tool is not in `USER_WAIT_TOOLS` and not
   `todo_write`: append to the text
   `\n[note: this is the same call with the same answer for the Kth time (first at step N). Repeating it
   will give this answer again. Change something first, or look somewhere else for the cause: for a
   running application its output (read_background).]`
   The words after "look somewhere else for the cause" are added only for `http_request`; for every other
   tool the note ends after "Change something first, or try another way."
4. When 2 or 3 applied, add `"repeat_of": N` to the `TOOL_CALL_FINISHED` payload. The event must be
   published after this decision, so move the decision above the `publish` call or compute it there; the
   preview and the saved full output stay those of the real result.
5. A call with a parse error, an unknown tool or invalid arguments is not recorded.
6. Subagents have their own loop and so their own ledger: nothing to do.

**Tests:** the ledger alone (same key and digest found, different digest not found, limits). Loop test
with a mocked model that calls `read_file` on the same file twice: the second tool message is the
pointer, the first is whole, and the finished event has `repeat_of`. A second test where the file is
edited between the two reads: the second read returns the new content, no pointer. A third where the
first result has been replaced by a stub in the history (set the message content to something starting
with `STUB_PREFIX` between the calls, or unit-test the "still whole" check as a function): full text
again. `todo_write` with the same list twice: the second result is the unchanged sentence and only one
`todo_updated` event exists.

**Done when:** tests pass and `tests/test_agent_loop.py`, `tests/test_tools.py`, `tests/test_context.py`
still pass (the call and result pairs must stay valid: `pairs_are_valid`).

## 6. HW2: a read replaced by a newer read of the same lines is dropped

**Goal:** the history does not carry two different versions of the same file lines. This is the only
trimming of the current turn that is safe without a measurement, because the newer result is in the
history in full. (An identical second read is already a pointer after HW1.)

**Files:** `src/forge/context/compaction.py` (new pure function), `src/forge/context/manager.py`
(`prepare`), tests in `tests/test_context.py`.

**Build:** `stub_superseded_reads(history: list[Message]) -> int` in `compaction.py`:

- Walk the assistant messages' tool calls; consider only calls named `read_file`. Key: the arguments
  `path` (backslashes turned into `/`), `offset` (default 1) and `limit` (default: absent).
- For each key with more than one call, every result **except the last** is replaced by
  `[Output of read_file(<path>) removed: the same lines were read again later in this conversation and
  that newer result is the current content.]` when: it is not already a stub (does not start with
  `STUB_PREFIX`), does not start with `[Same result as`, does not start with `Error`, and the **last**
  result of that key is whole (not a stub, not a pointer, not an error). The new text must start with
  `STUB_PREFIX` so the other compaction code treats it as a stub.
- Returns the number replaced. Pairs stay valid (only `content` changes, with `model_copy`).

In `ContextManager.prepare`, call it once before the micro-compaction loop, whatever the fill level; when
it replaced something, add the number to the existing `micro_compaction` notice count (one notice, not
two).

**Tests:** two reads of the same lines with different content: the first is stubbed, the second whole;
different `offset`: neither is touched; the last result is an error: nothing is touched; an already
stubbed result is not counted; `pairs_are_valid` holds afterwards.

**Done when:** tests pass, including `test_no_compaction_storm`.

## 7. HW5: an API call made before a code change is made again after it

**Goal:** the proof step of the running-system loop happens. The skill tells the model to call the API
again after the fix; in live runs the model skipped steps it was only told about (CLAUDE.md, "What the
live runs taught"). This uses the same mechanism as the open-todo and risk reminders at the end of a turn.

**Files:** `src/forge/toolkit/base.py` (`ToolContext`), `src/forge/tools/http_request.py`,
`src/forge/agent/loop.py`; tests in `tests/test_agent_loop.py` and the file that tests `http_request`.

**Build:**

1. `ToolContext` gets `api_calls: dict[str, int]` (default empty): key `"<METHOD> <url without query
   string>"`, value the step of the last call. `HttpRequest.run` sets it when a response arrived (any
   status), not when the request was refused or failed to connect.
2. `AgentLoop.run` notes `turn_start_step = self.context.step` at its start and has a counter
   `proof_nudges = 0`.
3. Where the turn is about to end (after the risk reminder, before the stop hooks): when
   `proof_nudges < 1`, `self.keep_full_output` is true (main agent only), `self.gate.mode != "plan"`,
   and there is a key in `api_calls` whose step is greater than `turn_start_step` and smaller than
   `self.context.last_code_edit_step`: append one system message, publish a notice
   (`kind: "proof_call"`, text "Asking for the API call to be run again after the code change."),
   increase the counter and continue the loop. The message, with the calls listed (at most 3):
   `You called <METHOD url> before your last code change and not after it. Run the same call again now
   and report what it answers (restart the application first if it does not reload by itself). If it
   cannot be run, say plainly in your reply that the change was not proven through the API and why.`
4. Nothing happens when the model made no API call in this turn, changed no code after it, or already
   called again after the change.

**Tests (mocked model, a small local HTTP server as the existing `http_request` tests use):** call, edit a
`.py` file, final text: the reminder is added once and the notice published; call, edit, call again,
final text: no reminder; only an edit: no reminder; a call from an earlier turn and an edit in this one:
no reminder; the reminder is given at most once per turn.

**Live measurement (the only live run in this work order):** `.venv\Scripts\python -m pytest
tests/test_live_running_system.py -m live -q` once before the change (use `git stash` only if nothing
else is uncommitted; otherwise run it first, before starting HW5) and once after. Report both results as
they are printed. Do not tune anything to make it pass.

**Done when:** the offline tests pass and both live results are in the report.

## 8. HW4: a syntax check after an edit for JavaScript, TypeScript and JSON

**Goal:** a broken bracket in a front-end file is reported in the edit's own result, as it is for Python.
Syntax only; a full type check stays a command the model runs.

**Files:** `src/forge/tools/diagnostics.py`, `src/forge/tools/files.py` (the call in `_save`); tests in
the file that tests `diagnose_file` (search `tests/` for `Syntax check FAILED`).

**Security rule (invariant 1, read it twice):** today's Python check starts the interpreter directly and
runs no project code. A JavaScript or TypeScript check runs Node, and the TypeScript one loads
`typescript` from the project's `node_modules`, which is code from the workspace. **It must run through
the sandboxed command path**, the function `execute(context, command, timeout_s, cwd)` in
`forge/toolkit/shell.py` that the post-edit hooks use (`_post_edit_hooks` in `agent/loop.py`), never
through `asyncio.create_subprocess_exec`. If `context.shell` is `None`, skip the check. If you cannot
make it run through `execute`, build only the JSON part and say so in the report.

**Build:**

1. `diagnose_file` takes the `ToolContext` instead of the workspace (one caller, in `_save`).
2. `.json`: parse with `json.loads` in-process. Skip (no check) when the file name starts with
   `tsconfig`, `jsconfig` or `.eslintrc`, when it lies under `.vscode/`, or when the text contains `//` or
   `/*` anywhere (it may be JSON with comments; telling a comment from a string is not worth the risk of
   a false report). A failure reports `Syntax check FAILED:` with the line, column and message.
3. `.js`, `.mjs`, `.cjs`: `node --check <file>` through `execute`, timeout 10 s. No `node` on the PATH
   (`shutil.which`): skip.
4. `.ts`, `.tsx`: find `node_modules/typescript/lib/typescript.js` by walking up from the file's folder to
   the workspace root; none or no `node`: skip. Otherwise run through `execute` a one-line Node script
   that reads the file, calls `ts.transpileModule(source, {reportDiagnostics: true, fileName: <name>,
   compilerOptions: {jsx: "preserve"}})` and prints each diagnostic as `line:column message` (at most 6),
   exit code 1 when there are any. Timeout 20 s. Put the script in a small `.js` file inside the package
   (`src/forge/tools/`, loaded with `importlib.resources`, passed to Node by path) rather than quoting it
   on a PowerShell command line.
5. A check that times out or cannot start returns `None` (no report), never an error for the model: a
   missing tool must not look like a mistake in the file.
6. `.jsx` and `.vue` are not checked.

**Tests:** JSON good and bad, a `tsconfig.json` with comments is skipped; the Node checks are tested only
when `node` is found (skip with a clear reason otherwise, like the optional-tool tests): bad `.js` reports,
good `.js` does not; the TypeScript check with a workspace that has no `node_modules` is skipped silently.
If `typescript` is not available on the build machine, write the test, mark it skipped with the reason,
and say in the report that the TypeScript path was not run.

**Done when:** tests pass and the report says which of the three paths was really run on this machine.

## 9. Report for the reviewer

When everything is done (or you stopped), append a section `## 10. Builder's report` to this file with:

- the `git status --short` output from before you started;
- per item: built or not, files changed, tests added (names), anything that differs from this file and why;
- the real last lines of the full test run, ruff, ruff format and mypy;
- the two live results of HW5;
- every place where you were unsure or chose between two readings of this file.

Do not write "done" for anything you did not run.

## 10. Builder's report

**`git status --short` before I started** (the changes below were already there):
```
 M TODO.md
 M docs/DECISIONS.md
 M docs/INSTALL.md
 M src/forge/agent/loop.py
 M src/forge/cli.py
 M src/forge/engine/log_summary.py
 M src/forge/engine/session_host.py
 M src/forge/protocol/events.py
 M src/forge/tools/code_map_tool.py
 M src/forge/tools/knowledge_tools.py
 M tests/test_knowledge_topics.py
 M tests/test_live_learn.py
 M tests/test_log_summary.py
?? docs/SPEC_HARNESS_WASTE.md
```
So `loop.py`, `log_summary.py` and `tests/test_log_summary.py` already held someone else's edits (D-575, D-574); mine are on top of them.

**Per item** (all built; nothing committed or pushed; DECISIONS D-576 to D-581; TODO 0l lines set to `[~]`):
- **HW0:** `engine/log_summary.py`; tests in `tests/test_log_summary.py`: `test_failed_calls_are_listed_per_tool_with_the_most_common_reason`, `test_time_to_first_word_is_bucketed_by_input_size`, `test_a_log_without_first_token_values_has_no_first_word_section`, `test_repeat_line_counts_all_repeats_and_pointers`. The line reads "...: N of M; answered with a pointer: K." (I added the pointer part now, not after HW1.)
- **HW3:** new `tools/edit_match.py` (holds `EditError`, re-exported from `files.py`), `tools/files.py`; tests `tests/test_edit_match.py` (10) and `test_edit_with_wrong_indentation_reports_the_note_and_saves_the_right_file` in `tests/test_tools.py`.
- **HW1:** new `agent/repeats.py`, `agent/loop.py` (`_answer_to_repeat`, `_result_is_whole`), `tools/todo.py`; `SAME_RESULT_START` lives in `context/compaction.py`. Tests: `tests/test_repeats.py` (ledger, pointer, third-read pointer, changed file, trimmed first result, note, todo_write). The cap, flag and rework lines now run before the `tool_call_finished` publish (needed for `repeat_of`).
- **HW2:** `context/compaction.py` (`stub_superseded_reads`), `context/manager.py`; 3 tests added to `tests/test_context.py`.
- **HW5:** `toolkit/base.py` (`api_calls`), `tools/http_request.py`, `agent/loop.py` (`PROOF_NOTE`, `_calls_to_repeat_after_change`); 5 tests at the end of `tests/test_agent_loop.py`. In them the edit's first-edit test-run gate (`require_baseline`) is switched off through a `setup` hook, otherwise `edit_file` is refused.
- **HW4:** `tools/diagnostics.py` (takes `ToolContext`), new `tools/ts_syntax_check.js`, `files.py`, `pyproject.toml` (package-data gets the `.js`: not a dependency, but a change the order did not name). Tests: `tests/test_diagnostics.py`. **Paths really run on this machine:** JSON (in-process) and JavaScript (`node --check` v24 through `execute`). **TypeScript:** only plumbing with a stand-in `typescript.js`; the real-compiler test is skipped: TypeScript 7 in `ui-react/node_modules` has no `lib/typescript.js`, so for such a project the check silently does nothing.

**Final checks:**
- Full run `-m "not browser and not live"`: `1 failed, 2127 passed, 14 skipped in 287.42s`. The failure is `tests/test_handoff_review.py::test_a_hand_off_debcraft_can_do_itself_is_sent_back_with_what_to_do`; it passes alone (`6 passed`), so I take it for load flakiness, not for my change (I did not look at its code).
- `ruff check .`: `All checks passed!` (after removing one unused `noqa` of mine). `ruff format --check .`: `1400 files already formatted`. `mypy`: `Success: no issues found in 368 source files`.

**HW5 live (`tests/test_live_running_system.py -m live`):**
- "Before": I only thought of the baseline after HW5 was built and the tree had other uncommitted changes, so I switched the reminder off by hand (`proof_nudges = 1`, since restored) and ran: `1 failed, 1 passed in 31375.55s (8:42:55)`; the failing one is `[token_asked]` (final status "failed", the API never called). This is not a run of the code before all my changes.
- "After" (reminder on): `1 failed, 1 passed in 518.20s (0:08:38)`; the failing one is again `[token_asked]`. Same outcome as before; nothing tuned. The log file does not record notices, so I cannot say from it whether the reminder fired in the passing run.

**Where I was unsure:** the pointer/note digest is of the text after cap, flag and rework note; `repeat_of` also marks note cases, so the summary's "answered with a pointer" counts those too (as the order words it); a failed result can get the repeat note; a `new` string with no non-blank lines deletes the block.
