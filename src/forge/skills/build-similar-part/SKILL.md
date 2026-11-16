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
- A dependency that cannot run on this machine and is not what you are building: bypass it with an edit
  marked `temporary` = `bypass` and its reason. It stays in your copy, is taken out of the delivered files
  and is named in the report.

## 6. Report and remember

The same/different list; what was reused; what was written new; what the user has to apply (files, the
data statement, settings by name); what you could not run and why. Write how such a part is built with
`knowledge_write`, so the next one starts from step 3.
