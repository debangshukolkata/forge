---
name: solve-against-running-system
description: Makes an existing system fulfil a requirement it cannot fulfil yet, by running it and watching what happens. Use when the user wants an agent, a tool, an API or a workflow of their existing application to be able to do something ("the agent should be able to ...", "make it answer ...", "it fails when ..."), and whenever reading the code alone cannot tell you whether the requirement is met.
---

# Solving a requirement against the running system

You are not asked to change code to a description. You are asked to make the system **do** something. Reading
the code tells you how it is built; only running it tells you whether it does the thing. Work in this order and
do not skip a step because the answer seems obvious.

## 1. The requirement as a check

Write down (todo_write) the one run that proves the requirement: what goes in, what must come out. Example:
"POST the question 'what are the names of the deployments?' to the ops agent; the answer lists the names."
This check is run before any change and again after every change.

**The check goes through the door the users use**: the application's API (or its page, or its command), with the
application started. Calling an inner function yourself (`python_run` importing the agent and running it) is a
way to look closer while you investigate; it is never the check. It skips the login, the request format, the
server's own error handling and the run log, which are part of what the user gets and often where the problem is.

## 2. Understand what the system has

- `knowledge_search` first: an earlier project may have written down how agents, tools and the API fit together.
- `code_map`: `endpoints` and `endpoint` for how the thing is called (path, payload, auth); `find`, `callers`,
  `callees` for how a run proceeds; `tables` and `table` for where its configuration lives.
- Capabilities are often **data, not code**: which tools an agent has, their descriptions, the API behind each,
  prompts, limits. Read those rows (`db_query`, or the application's own database file) as well as the code
  that uses them. List what the agent can already do.
- Write what you worked out with `knowledge_write` before you finish.

## 3. Run it here, on its own data

You work on a copy of the repository. Start that copy; never test against, or write to, the user's real system.

1. Settings: `code_map` action `env` shows what the application reads and what its env files lack.
2. Database: when the application needs data from a database you may only read, copy the tables it needs with
   `db_copy_table` (use `where` to take only the rows of the agent or tenant you are working on), then
   `use_scratch_database` to point the application's own database settings at your copy. Start the application
   after that. From then on its writes land in your copy.
3. Start it with `start_background` and wait for it to listen.

## 4. Call it the way its users do

Do this before you change anything: the first run through the API is the evidence the rest is built on.

- `http_request` to the endpoint you found, with the payload it expects. Give `timeout_s` for a run that takes long.
- **A token only the user can get** (issued by a login page or a console): a 401 or 403 tells you. Do not look
  for one in files and do not invent one. Call again with `token_env` = `DEVELOPMENT_INSTANCE_TOKEN`. If the
  tool says it is not set, the user is asked to add it (the tool asks them itself where it can; otherwise ask with
  `ask_user`): say which file to put it in (the tool names it),
  the line to add, and where the token comes from in their application. When they answer, call again.
  A token expires: on a later 401 ask for a fresh one, do not give up.
- **The token line needs no care from the user.** `http_request` reads DebCraft's .env on every call, sends a
  value saved as `Bearer <token>` correctly, and tries the bare token when the API refuses `Bearer`. Never ask
  the user to rewrite the line or to restart DebCraft.
- **Settings the application itself needs** (the variables of a secret store such as Infisical, a gateway
  address, a token for another service such as ArgoCD): when the user says they are in DebCraft's .env file,
  call `request_app_secret` with all the names at once. The user confirms with one click and your commands,
  including the application you start, get them as environment variables. A command that checks `os.environ`
  before that shows them as missing: that is by design, not a fault, and no restart or copying fixes it.
  Never ask the user to paste a token into the chat: it is hidden from you there, and `ask_user` and
  `request_user_action` refuse such a question.

## 5. Observe before you explain

Collect what the run left behind, all of it, before you name a cause:

- the answer of the API: status, size, the parts by size that `http_request` prints;
- the application's own record of the run: its log file or log table, the output of the process
  (`read_background`), rows it wrote;
- which capability it used, with what input, and what came back, how large.

State the failure as a fact with its evidence ("the tool list_deployments returned 343,634 characters; the
agent's context holds 20,000; logs/runs.jsonl line 3"). If the evidence does not show the cause, run a
narrower experiment (call the tool's API yourself through the application, shorten the input); do not guess.

## 6. Choose the smallest change that makes the check pass

Decide from the cause, not from habit. The usual options, from least to most invasive:

| The cause | A fitting change |
|---|---|
| The right capability exists but is not chosen | Its description or the agent's prompt |
| A capability returns far more than is needed | A filter on its result, or a new tool that returns only what the task needs |
| The capability is missing | A new tool, registered the way the existing ones are |
| The steps are right but the order or the stopping rule is wrong | The agent's prompt or its loop settings |
| Knowledge is missing, not a capability | A skill, a document or a prompt section the agent reads |
| A limit is too low for a legitimate case | The limit, with the reason, only when nothing above fits |

Prefer the way the system already extends itself (if tools are rows in a table, add a row; if custom tools are
functions in one module, add a function there). Say in one line which option you chose and why the others do
not fit.

## 7. Implement, then run the same check again

- Make the change in the copy. If it includes data (a new row), write the row in your copy of the database
  **and** deliver it as a migration or seed statement the user can apply: a change that exists only in your
  scratch database is not delivered.
- Restart the application if it loads that data or code at start.
- Run the check from step 1 again, exactly as before: through the API of the restarted application, not through a function call. Compare with the first run: what was the result then,
  what is it now. Then run one neighbouring case that must still work (another question to the same agent,
  another agent that shares the tool).
- If it still fails, go back to step 5 with the new evidence. A second failure for the same reason means the
  cause was wrong, not that the fix needs more force.

## 8. Report

What the requirement was; what the system did before (with the evidence); the cause; the change and why this
kind of change; what the system does now (the same check, its result); what the user has to apply on their
side (files, the data statement, a restart); what you could not check here and why.
