---
name: sync-docs
description: Use this in Dialectic-CLI when the user asks Codex to check documentation synchronization for code/.md changes or newly added docs using the canonical .claude sync-docs workflow. Applies Codex compatibility rules from docs/dev-docs/codex-compat.md.
---

# sync-docs

Codex-native entrypoint for the canonical `.claude/skills/sync-docs/SKILL.md` workflow.

## Workflow

1. Read `docs/dev-docs/codex-compat.md`.
2. Read `.claude/skills/sync-docs/SKILL.md`.
3. Apply the Codex overrides from `docs/dev-docs/codex-compat.md`.
4. Use `docs/dev-docs/Documentation-Checklist.md` as the mapping source.
5. Do not auto-edit docs unless the user separately asks for fixes.

If the canonical skill conflicts with Codex tool policy, Codex tool policy wins. Report the conflict and continue with the nearest safe equivalent.
