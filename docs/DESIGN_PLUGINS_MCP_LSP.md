# Design for sign-off: plugins and hooks, MCP in Mode B, code intelligence (LSP)

Status: **proposal, nothing built.** Per CLAUDE.md these are security-relevant or new interfaces, so they wait for the
user's decision. Each part: context, options with trade-offs, recommendation, what the user decides.

## 1. Plugins, project folder, settings, hooks

**Context.** Forge already loads skills, custom agents, custom slash commands, FORGE.md and MCP servers, but from different
places (`<home>/skills`, `<home>/agents`, `<home>/commands`, `<home>/memory/scopes/<scope>/`), and has one hook (`post_edit`,
plus `pre_compact`/`post_compact` since D-176). There is no project-level folder and no settings file with permission rules.

| Option | What | Pros | Risks |
|---|---|---|---|
| A. Layout only | One documented folder layout (user: `<home>/`, project: `<home>/memory/scopes/<scope>/`), no plugins | Small, nothing new to trust | No sharing, no hooks per tool |
| B. Plugins as folders (recommended) | `plugins/<name>/` with `plugin.json` + `commands/ agents/ skills/ hooks/`; enabled once per user | Shareable bundle; same loaders reused | A plugin can run commands (hooks): needs the trust rules below |
| C. Full marketplace | Install from URLs | Convenient | Supply-chain risk, network, out of scope |

**Recommendation: B**, in three steps, each shippable alone:
1. *Folders and settings*: user and project `settings.json` (project overrides user) with **permission rules** such as
   `allow: ["run_command(python -m pytest*)"]`, `deny: ["run_command(git push*)"]`; evaluated before the shell classifier,
   which stays the floor: the always-ask list can never be allowed by a rule. Commands/agents/skills load from user and
   project folders.
2. *Plugins*: `plugin.json` (name, version, description, what it adds). A plugin is **off until the user enables it**; the
   prompt lists exactly what it adds (commands, agents, skills, hooks, MCP servers). Mode B: a plugin may only come from
   Forge Home, never from a folder inside the workspace.
3. *Hooks*: events `pre_tool`, `post_tool`, `session_start`, `session_end`, `user_message`, plus the existing compaction hooks.
   A hook command runs through **the same shell classifier, permission gate and sandbox as any command the model runs**;
   its output is untrusted text (injection markers apply) and is capped and redacted. A hook cannot approve anything.

**User decides:** B or A; whether `pre_tool` hooks may block a call (recommended: yes, a hook may *deny*, never *allow*).

## 2. MCP in Mode B

**Context.** `parity/mcp_client.py` and `McpHub` exist (stdio servers from `config.yaml` `mcp.*`, off by default). Mode B's
promise: Forge never sees the host's code. An MCP server is a process Forge does not control: its tools can read anything it
can reach, and what they return goes to the model.

| Option | What | Risks |
|---|---|---|
| A. Off in Mode B | MCP only in Mode A | Safe; loses internal tools in Mode B |
| B. Allow-list per project (recommended) | A server and each of its tools must be listed in the project's settings; Mode B tools get redaction plus the sensitive-term filter on arguments and results; results flagged as untrusted data | The server itself can still touch the host; the user must trust it |
| C. Sandboxed servers | Run servers in the low-integrity sandbox | Strongest; many servers need network or user-profile access and break |

**Recommendation: B with a visible warning per server in Mode B**, tool calls always listed in the run log with arguments, and
tools default to the permission gate's "ask". C is a later option for local servers that need no network.
**User decides:** A or B for Mode B; which servers exist at all (only the user can vouch for them).

## 3. Code intelligence (definitions, references, symbols, diagnostics)

**Context.** The knowledge base and its symbol tools were retired (D-160); the model uses grep/read. For large repos a
language-aware lookup would be faster and more exact. "LSP" is one way; the need is definition, references, symbols and diagnostics.

| Option | What | Pros | Risks |
|---|---|---|---|
| A. Stay with grep | nothing new | Simple | Slow on large code, imprecise for dynamic names |
| B. `jedi` in process (recommended first) | pure-Python library (MIT), three tools: `find_definition`, `find_references`, `list_symbols`, read-only | Offline-friendly wheel, no server to manage, Python repos are Forge's main case | Python only, no live diagnostics |
| C. Real LSP clients | pyright or pylsp, typescript-language-server | Diagnostics, multi-language | pyright needs Node and a download; process management; more moving parts |

**Recommendation: B now; C only for TypeScript/Angular projects when the workspace already has `node_env`.** All tools are
read-only, run on the workspace copy only (Mode A) or the project folder (Mode B), and respect the write jail and redaction.
**User decides:** B (new dependency `jedi`, MIT, pure Python, wheel can go in the offline wheelhouse).

## What I would build, in order, if approved
1. settings + permission rules (small, high value), 2. `jedi` tools, 3. plugins (enable-once, no marketplace), 4. hooks,
5. MCP allow-list. Each step gets tests (deterministic where possible), a decision record and a MODULE.md update; the
always-ask list and the safety invariants stay untouched.
