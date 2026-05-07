---
name: commit
description: Use this in Dialectic-CLI when the user asks Codex to prepare or perform the canonical .claude commit workflow. Applies Codex compatibility rules from docs/dev-docs/codex-compat.md and never auto-commits without user approval.
---

# commit

Codex-native entrypoint for the canonical `.claude/skills/commit/SKILL.md` workflow.

## Workflow

1. Read `docs/dev-docs/codex-compat.md`.
2. Read `.claude/skills/commit/SKILL.md`.
3. Apply the Codex overrides from `docs/dev-docs/codex-compat.md`.
4. Present the change classification and requested commit grouping.
5. Do not run `git commit` until the user explicitly approves the exact commit action.

If the canonical skill conflicts with Codex tool policy, Codex tool policy wins. Report the conflict and continue with the nearest safe equivalent.
