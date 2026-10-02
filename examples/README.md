# Examples

Copy these into Forge Home (`%USERPROFILE%\.forge`) or a workspace to try them.

- `FORGE.md`: an instruction file (always pinned into the model's context; the equivalent of CLAUDE.md).
- `agents/test-writer.md`: a custom subagent, started with `spawn_subagent` by its name.
- `skills/release-notes/SKILL.md`: a skill; the model loads its full text with `load_skill` when relevant.
