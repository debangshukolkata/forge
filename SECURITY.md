# Security

Forge is a local tool that runs a model with access to files and a shell on your machine. Its safety rules are
built into the code and each one has a test. They are listed in CLAUDE.md under "Safety invariants" and described
in spec §14 (docs/FORGE_BUILD_SPEC.md):

1. Forge never writes to your original repository (code-level write jail plus an OS-level low-integrity sandbox).
2. In Mode B, Forge never reads outside the workspace and the profile folder.
3. Secrets never reach the model, transcripts, memory files, events or the browser (redaction on every result).
4. Database writes happen only in the scratch schema for the current requirement.
5. Forge cannot modify its own install folder or `config.yaml`.
6. Actions Forge cannot or must not do are handed to you; if you cannot do them either, Forge proposes a
   workaround or a code change.

The local web UI listens on 127.0.0.1 only and requires a random per-run token (spec §15A.3). Prompt-injection
markers are flagged in tool results (spec §14.4).

## Reporting a problem
Tell the maintainer privately before opening a public issue if you find a way to break one of the rules above
(for example a write outside the workspace, a secret reaching a log, or a bypass of the permission gate). Include
the Forge build id (`forge --version`), the steps, and the events log of the run if it does not contain secrets.

Do not paste real keys, tokens or data rows into an issue.
