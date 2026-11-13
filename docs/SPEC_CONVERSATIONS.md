# Work order: several conversations in one project, and the model's history kept (CV1, CV2, CV4)

Written 2026-11-12, **rewritten 2026-11-13 after the design pass with the user (D-582)**. The user decided:
option A (conversations inside a project), a folder per conversation, the model's history saved after every
step, a card that asks before a running conversation is stopped for a switch, a fresh start for a new
conversation, and a dropdown in the chat header. Items: TODO.md section 0k, `CV1`, `CV2`, `CV4`.
**Who does what:** a smaller model builds from this file; the analysis model reviews the result (`CV5`).
Build in the order of section 10; finish and test each part before the next.

## 1. What is wrong today

- A project has one event log for its whole life: `<project>/.forge/transcripts/events.jsonl`. The screen is
  drawn from it; every open reads all of it.
- The messages sent to the model are a list in memory (`SessionHost.history`). When a project is reopened
  the list starts again with the system prompt only. The screen still shows the whole earlier chat, so the
  user cannot see that none of it is sent to the model any more.
- A long conversation makes every step slow, and the only way to start small again is `/clear`, which
  leaves the screen and the log as they are.

## 2. What is built

1. A project holds several conversations; exactly one is active. Each has its own event log, its own saved
   model history and its own task state. Files, changes, checkpoints, memory, knowledge, cost and the
   subagent transcripts stay with the project.
2. The model's history is saved after every step and loaded when the conversation is opened.
3. A new conversation starts with an empty history, the project's shared knowledge and one line per earlier
   conversation (section 7).
4. A dropdown in the chat header lists the conversations, starts a new one and renames one (section 9).
5. A conversation that has no saved history says so once in the chat (section 8).

## 3. On-disk format (D-582; hard to change later, build it exactly)

```
<project>/.forge/
  conversations/
    index.json                       the index (new)
    c1/events.jsonl                  event log of conversation c1
    c1/history.json                  saved model history
    c1/state.json                    task state
    c2/...
  transcripts/
    events.jsonl                     the OLD log: left untouched after the copy (section 4), the backup
    subagents/                       unchanged, per project
  state.json                         the OLD task state: left untouched after the copy
```

`index.json`:

```json
{"version": 1, "active": "c2",
 "conversations": [
   {"id": "c1", "title": "Fix the ArgoCD tool answer", "created": "2026-11-12T09:14:03+00:00", "updated": "2026-11-12T17:40:11+00:00"},
   {"id": "c2", "title": "", "created": "...", "updated": "..."}]}
```

- Ids are `c1`, `c2`, ... in order of creation; never reused. Validate with `^c[1-9][0-9]{0,5}$` before a path
  is built from an id (it arrives from the browser).
- `title`: empty until the first user message; then that message in one line cut to 60 characters. The user
  can rename it (a rename is kept; the first message never overwrites a title that is set).
- `updated`: set when a step ends.

`history.json`:

```json
{"version": 1, "saved": "2026-11-12T17:40:11+00:00", "messages": [...], "pinned": {"compaction_summary": "..."}}
```

- `messages`: `SessionHost.history` **without its first message** (the system prompt is always built fresh),
  each as `Message.model_dump(mode="json")` with `provider_items` and `provider_items_model` set to null and
  `images` emptied.
- `pinned`: only the slot `compaction_summary` (the other slots are rebuilt at open from the project).

## 4. Migration of an existing project (once, never loses anything)

Run by `ConversationStore` the first time a project is opened and `conversations/index.json` is absent:

1. Create `conversations/c1/`. **Copy** (never move) `transcripts/events.jsonl` to `c1/events.jsonl` and
   `state.json` to `c1/state.json` when they exist. The old files stay where they are: they are the backup
   and an older DebCraft that opens the project still finds them.
2. Write `index.json` last, with `c1` active: title from the first `user_message` event (empty if none),
   `created` and `updated` from the old log's file times. A crash before this line leaves no index, so the
   next open starts the migration again from the beginning (copying over a half-copied `c1`).
3. From then on only `conversations/` is used. Nothing is ever copied back.
4. Test: an old-style project with a 3 MB log opens, `c1/events.jsonl` equals the old log byte for byte,
   the old files are still there, a killed migration (index missing, `c1` half written) repeats cleanly.

## 5. Security (invariants 1 to 3; the reviewer checks each line)

1. **The saved history is redacted.** The list in memory is not: redaction happens when a request is sent
   (`llm/router.py`) and when an event is published. Before writing, pass the whole dump through the event
   bus's redactor (add a public `EventBus.redact_data(data)` beside `redact_text`; do not build a second
   redactor). **On loading, redact again** (a file edited by hand or written by an older version must not
   bring a secret back into the model's context). Test with a fake secret in a tool result and in a user
   message (comment `# check_secrets: fake`): the file on disk must not contain the value, and a file that
   does contain it loads without it.
2. Every path is checked by the workspace jail before writing (`workspace.jail.check(path)`, as
   `usage.json` is). Write to a temporary file in the same folder and replace it, so a killed process never
   leaves half a file.
3. Nothing of this is written outside `<project>/.forge/`. Nothing is sent anywhere.
4. A conversation id from a request is validated before it becomes a path (section 3), and the resulting
   path is checked to lie inside `conversations/`.
5. Loading: a file that does not parse, has another `version`, or holds an invalid message is ignored as a
   whole (the conversation opens without history and section 8 applies). Never raise from a bad file.
6. The history file holds what the model saw: tool outputs as capped for the model. It is not exported by
   `/export` and not shown in the UI.

## 6. Module `src/forge/workspace/conversations.py` (new)

Tier: `workspace` (it may import what `workspace/workspace.py` imports, nothing later; check
`tests/test_module_boundaries.py` and the module's `MODULE.md`). Pure file work, no model, no events.

- `class Conversation(BaseModel)`: `id`, `title`, `created`, `updated`.
- `class ConversationStore` built from a `Workspace` (runs the migration of section 4 on first use):
  - `list() -> list[Conversation]` (oldest first); `active() -> Conversation`;
  - `create(title: str = "") -> Conversation` (next id, makes its folder, becomes active, writes the index);
  - `activate(conversation_id)` (unknown id: raise a specific error from `forge/errors.py`);
  - `rename(conversation_id, title)`; `touch(conversation_id)`; `set_title_if_empty(conversation_id, text)`;
  - `events_path`, `history_path`, `state_path` (all `conversations/<id>/...`).
- `save_history(path, messages, pinned, redact)` and `load_history(path, redact) -> tuple[list[Message],
  dict[str, str]] | None` as in sections 3 and 5. If `forge.llm.base.Message` cannot be imported from this
  tier, put these two functions into `src/forge/engine/history_store.py` and say so in the report.
- After loading, the messages must form valid pairs (`pairs_are_valid` in `context/compaction.py`): if they
  do not, cut the list back to the last index returned by `step_starts` at which the list before it is
  valid. Do this where the history is loaded into the session (the context tier is available there).

## 7. Wiring

1. `src/forge/session.py`, `build_session`: with a workspace and no `log_path`, the log is
   `ConversationStore(workspace).events_path(active id)`.
2. `src/forge/workflow/state.py`, `StateStore`: the path is `ConversationStore(workspace).state_path(active id)`.
   A new conversation starts with an empty task state, except that the `cadence` of the conversation that
   was active is copied into the new `state.json` (the user set it by saying so; it must not be lost). If
   `state.json` is read anywhere else than through `StateStore`, stop and report.
3. `src/forge/engine/session_host.py`:
   - in `__init__`, after `self.history` is created and only with a workspace: load the active
     conversation's history; when it is there, `self.history = [system message, *messages]` and the pinned
     `compaction_summary` is set. Keep the open time in mind (D-573): time `SessionHost(...)` with a 1 MB
     history file and put the number into the report.
   - **after every finished step** (when the tool results of a step have been appended to the history, so the
     pairs are complete), after `/clear` (`reset_history`) and after `/compact`: save the history with
     `asyncio.to_thread` and `touch` the conversation. Save at most once per second while steps are fast
     (skip a save when the last was less than a second ago, and always save at the end of the turn). A save
     that fails publishes one notice (`kind: "history_not_saved"`) and never ends the turn.
   - in `submit`, on a `SendMessage` that is not a slash command: `set_title_if_empty`.
   - **the other conversations line.** For a conversation that is not `c1`, or any conversation when the
     index holds more than one entry, set a pinned slot `conversations` (use the existing pin mechanism of the
     todo list): one line per other conversation, `c2 "Add retry to tools" (2026-11-10): <first user message,
     80 characters>`, at most 10, newest first, plus the sentence `Earlier conversations of this project can
     be read with conversation_recall.` Nothing when there is only one conversation.
4. New tool `conversation_recall(id, what="summary"|"requests")` in `src/forge/tools/` in a deferred group
   (`tools/deferred.py`, CLAUDE.md "Light core"): read-only, returns that conversation's user messages and
   final answers from its `events.jsonl` (the `user_message` and `message_done` events), redacted, at most
   12,000 characters; an invalid or unknown id is an error result. It cannot read the active conversation.
   Add it to the tool listing tests the way other deferred tools are listed.
5. `src/forge/web/manager.py`, `WebSessionManager`:
   - `conversations() -> list[dict]` (the list with an `active` flag on one and `running` on the active one
     when the host is busy);
   - `async new_conversation(title="", stop_running=False)` and `async open_conversation(conversation_id,
     stop_running=False)`: when the session is busy and `stop_running` is false, raise a specific busy
     error. When `stop_running` is true: cancel the run the same way the Stop button does, wait until the
     turn has ended (up to 10 seconds, then report an error and switch nothing), make sure the history of
     the last finished step is saved, then set the active conversation and open the project again as
     `open_workspace` does (close the session, build a new one in a thread);
   - `rename_conversation(conversation_id, title)`.
6. `src/forge/web/server.py`:
   - `GET /api/conversations` -> the list;
   - `POST /api/conversations` body `{"title": "", "stop_running": false}` -> creates and opens it;
   - `POST /api/conversations/open` body `{"id": "c2", "stop_running": false}`;
   - `POST /api/conversations/rename` body `{"id": "c2", "title": "..."}`;
   - busy and not `stop_running`: HTTP 409 with `{"detail": "DebCraft is working in this conversation.",
     "busy": true}` (the UI shows the card of section 9 and repeats the call with `stop_running: true`);
     unknown or invalid id: 404;
   - `/api/state` gets `"conversation": {"id", "title"}` inside `"workspace"`.
   These go through the same request guard and login check as the other `/api/` routes; add nothing that
   bypasses them.
7. Readers of the old fixed path now use the active conversation unless told otherwise:
   `src/forge/web/project_list.py` (last activity and last request), `src/forge/engine/run_report.py` and
   `src/forge/cli.py` (`run-report`, `log-summary --workspace`; both get `--conversation <id>`).
8. Not changed: `usage.json` (cost stays per project), checkpoints, `.forge/tool_outputs`, memory,
   knowledge, subagent transcripts, project delete (it removes the whole folder), `/export` (it exports
   the open conversation, which is what the bus holds).

## 8. The line "DebCraft no longer has what is above"

When a session opens a conversation whose log holds at least one `user_message` event and no history was
loaded (no file, or an invalid one), and the last event of the log is not already this notice: publish one
`NOTICE` with `kind: "history_not_restored"` and the text
`What is above this line is no longer in DebCraft's working memory: this conversation was held before
conversations were saved. The files, the notes and the to-do list are kept. Say what you want to continue
with, or start a new conversation.`
Do this in `SessionHost.run` before the input loop. A notice is already shown in the chat.

## 9. The UI (`ui-react/`, part `CV4`; the look follows docs/DESIGN.md, one blue accent)

Built after sections 3 to 8 work and are tested through the API.
- The chat header shows the conversation's title; a click opens a list: `+ New conversation` on top, then
  the conversations newest first with the title, the time of the last use ("now", "2 d") and a dot for the
  one that is running. A click on an entry opens it. The list closes on a click outside and on Escape.
- A pencil next to the title renames it (inline field; Enter saves, Escape cancels).
- When the call answers 409 `busy`, a card asks: "DebCraft is working in this conversation. Stop it and
  switch?" with `Stop and switch` and `Keep working`. On the first the call is repeated with
  `stop_running: true`.
- After a switch the screen is drawn from the other conversation's events (the same replay as opening a
  project; the sequence numbers start at 1 for each log). While the call runs the list shows a spinner and
  cannot be clicked again.
- A project with one conversation shows the title and the dropdown with only `+ New conversation`.
- Browser tests (`tests/test_web_e2e.py` style, headless Edge, screenshots to `test-artifacts/react-ui/`):
  the list opens and closes; a new conversation empties the chat; switching back restores the first chat;
  rename; the card on a busy switch. **Look at the screenshots before reporting done** (CLAUDE.md).
- `npm run build` writes `src/forge/web/react/`; commit source and build together (the builder does not
  commit).

## 10. Build order and tests

Order: (1) `conversations.py` with the migration and the history functions; (2) wiring of sections 7.1 to
7.3 and 8; (3) `conversation_recall`; (4) manager and server routes; (5) the readers (7.7); (6) the UI.

New `tests/test_conversations.py` (file work, direct):
- no index: the migration of section 4 (copy, old files kept, a killed migration repeats);
- `create` makes `c2`, its folder, the index, and it is active; ids are never reused;
- `activate` of an unknown id raises; an id like `../x` or `c0` is refused before any path is built;
- `save_history` then `load_history` gives the same messages without `provider_items` and `images`;
- the fake secret is not in the file, and a file that holds it loads without it (section 5.1);
- a truncated or wrong-version file loads as `None`;
- a write goes through the jail (a path outside the workspace is refused).

In a new `tests/test_history_restore.py` (real `SessionHost`, `mocked_router`, as the existing loop tests do):
- one turn, close, build a new session on the same workspace: the second request the mocked model receives
  contains the first turn's user text and answer;
- the history is saved after each step: kill the session in the middle of a turn after a finished tool step
  (cancel the task), open again: the first steps are there and the pairs are valid;
- a history file whose last tool call has no result is cut back to valid pairs and the session still answers;
- an old project (events, no history file): the notice of section 8 is published once, and not again on a
  second open;
- a new conversation: the request holds nothing of conversation 1, the task state is empty, the cadence
  was copied, the pinned line lists conversation 1, and `usage.json` still counts both;
- `/clear` then reopen: the history stays empty;
- `conversation_recall` returns the other conversation's requests and answers, refuses the active one and a
  bad id, and does not contain a fake secret.

In the web server's test file (search `tests/` for `/api/open`): the routes, 409 `busy` without and the
switch with `stop_running`, 404 for an unknown id, and that after `POST /api/conversations/open` the socket
replays the other conversation's events.

No live test in this work order.

## 11. Rules for the builder

The rules of `docs/SPEC_HARNESS_WASTE.md` section 2 apply here too (read CLAUDE.md and the MODULE.md files,
no commit, no push, no dependency, quick check while working, the full non-browser run with ruff, ruff
format and mypy at the end, stop and report instead of guessing; the browser tests for section 9). In
addition:

- Update `src/forge/workspace/MODULE.md`, `src/forge/engine/MODULE.md`, `src/forge/tools/MODULE.md` and
  `src/forge/web/MODULE.md`.
- Update the lines `CV1`, `CV2`, `CV4` in TODO.md to `[~]` with what is built; never `[x]`.
- Append `## 12. Builder's report` to this file: `git status --short` from before you started; what was
  built per section; files changed; test names; the measured open time; the real last lines of the test
  run, ruff and mypy; every place where the code was not as described here or you chose between two
  readings.

## Known limits (accepted, not to be solved here)

- A process killed in the middle of a step loses that step's messages for the model (the history is saved
  after every finished step); the events are in the log and the changed files are on disk.
- A conversation cannot be deleted yet (the project delete removes all), and conversations cannot run at the
  same time (one session per project, D-572).
- Read-before-edit, the repeat ledger and the step counters start fresh after a reopen: the model reads a
  file again before it edits it.
- Subagent transcripts are per project, not per conversation.
