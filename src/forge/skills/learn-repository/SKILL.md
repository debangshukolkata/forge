---
name: learn-repository
description: Explores an existing repository and writes down how it works as topic notes that every later project on it starts with. Use when the user says /learn, asks you to learn, study or explore the codebase, or to update what you know about it.
---

# Learning a repository

The goal is that no later project has to work out again what you work out now. You write **topics**: short notes
about one thing each, with the files and lines that prove them. You change no file of the repository.

## 1. See what is known and what is open

1. `knowledge_search` with action `agenda`. It lists, in this order of value:
   - topics whose source files changed (re-check these first: a wrong note is worse than none);
   - questions no topic answers yet;
   - areas of the code with nothing written down;
   - files that changed in the repository since the map was last updated.
2. If the user named a focus, start there and leave the rest of the agenda for later.
3. Write a todo list with the items you will take, most valuable first. One item is one topic.

## 2. For each item

1. **Structure first, from the map, not by reading around.** `code_map`: `overview`, `find`, `file`, `endpoints`,
   `endpoint`, `callers`, `callees`, `tables`, `table`. This tells you where things are and how they are linked.
2. **Then read the few files that matter**, the parts the map pointed to. Follow one real path from start to end
   (a request from the endpoint to the table; an agent from where it is built to where it runs).
3. **Write the topic** with `knowledge_write`:
   - `title`: the thing, as a person would ask for it ("How tools are attached to an agent").
   - `summary`: one line saying what the topic answers.
   - `body`: start with a `## Key facts` section of three to five short lines, the ones people ask most
     (the pin shows them for the most used topics, so a common question needs no tool call), then the facts
     in the order things happen. Every fact has its file and line (`agents/react.py:42`).
     Name classes, functions, tables, settings. Say what you checked and what you only inferred.
     Short excerpts only (a signature, a registration line); never whole functions.
   - `sources`: every file the topic rests on.
4. **Check it before moving on.** Open two of the lines you cited and see that they say what you wrote.
   If a link came from the map marked "by name", read the code and confirm it or leave it out.

Topics worth having for a service or an agent platform (take the ones the agenda says are missing):
how to run and test it; the web API by group, and how a request is authenticated (which setting holds the
token or secret: the NAME only, never a value from an `.env` file); the main tables and what they hold; which
endpoint touches which tables; which agents exist and what each is for, by kind if the code has kinds; where the
agent loop is, for a normal answer and for a streamed one; where tools are written, how one is registered and
attached to an agent, and where agents with their tools are stored; how the orchestration is built: nodes,
edges, how an agent is put on a node, how a run starts and ends.

## 3. When a topic already exists

- Its files did not change: leave it. Do not rewrite what is right.
- Its files changed: read the changed files. Still right: `knowledge_write` with its `slug` and `confirm: true`.
  Not right any more: write it again with the same `slug` and a `reason` saying what was wrong.
- You find it wrong while doing other work: correct it then, with the `reason`. Do not leave a note you know is wrong.

## 4. Size and speed

- A large repository is learned over many sessions. Take the most valuable items and finish them properly,
  rather than touching everything thinly.
- Separate areas can be explored at the same time: `spawn_subagent` with agent `explore`, one per area, each
  asked for the facts with file and line. You write the topics from their reports and check the cited lines.
- One topic is about one thing and at most about 150 lines. Split a long one.

## 5. Finish

Say which topics you wrote, which you corrected (and what was wrong), which you confirmed, and what the agenda
still lists. If you were given a time limit, stop taking new items when it is near and write this report.
