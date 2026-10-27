# Keeping the user's code off the internet (D-503)

Written for the person who uses DebCraft on a company codebase. What can leave the machine, what stops it, and what does not.

## What goes out by design
The model provider you configured (Azure OpenAI, or Gemini): every prompt contains what the agent has read. Retention is set by your company's
agreement with the provider, not by DebCraft. Mode B never sends the host code at all.

## Tools that talk to other servers
`web_search`, `web_fetch`, `find_image`, `fetch_image`, `find_font`, `fetch_font`, `theme_search`, `library_api`, `design_inspire`, `design_md_import`
and every MCP tool carry `sends_outside = True`. Before one of them runs, `safety/egress.py` checks every text value of the call:
- **Copies of the project's code.** Twelve consecutive code tokens that also occur in the repository copy (Mode A `repo/`, Mode B `project/`) or in
  anything a local tool has shown the model in this session are refused. Spaces, line breaks, URL escapes and base64 do not hide a copy.
- **Pasted text.** A query over 500 characters or with three or more lines.
- **Data in addresses.** An address over 2000 characters, or with a long mixed-case encoded-looking string. An address the user typed themselves is
  exempt: it is theirs to send.
The model sees "Not sent: ..." with the reason and rewrites the call; the session shows a notice. Short queries ("pandas read_csv usecols") cannot match.

Alongside this, the destination rules of D-209 still apply (no internal addresses; allow/deny domains), Mode B masks the profile's sensitive terms,
and `git push`, uploads and other network commands are refused or asked about, always.

## What it does not stop
- **Code the model writes and runs.** A script or a package install hook can open a connection; the low-integrity sandbox limits files, not the
  network. Installs ask first (always); reading what a script does before approving a run is the control.
- **Shell commands you approve.** The approval card shows the command. The egress check does not read approved commands.
- **Identifiers alone.** A query naming a function or table (`reconcile_ledger`) is shorter than twelve tokens and goes out. Only copied code is blocked.
- **A rewording.** A model that paraphrases a function in prose is not caught.
- **Pasted-in-chat code in Mode A** is remembered only if a local tool returns it; text typed into the chat is not indexed.

## For the strictest cases
Turn web tools off (`web.allow_domains` with one harmless domain, or no search provider), do not configure MCP servers, and use Mode B for code that
must not reach any model.
