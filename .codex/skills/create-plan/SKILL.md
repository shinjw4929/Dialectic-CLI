---
name: create-plan
description: Use this in Dialectic-CLI when the user asks Codex to create a repo-local implementation plan using the canonical .claude create-plan workflow. Applies Codex compatibility rules from docs/dev-docs/codex-compat.md.
---

# create-plan

Codex-native entrypoint for the canonical `.claude/skills/create-plan/SKILL.md` workflow.

## Workflow

1. Read `docs/dev-docs/codex-compat.md`.
2. Read `.claude/skills/create-plan/SKILL.md`.
3. Apply the Codex overrides from `docs/dev-docs/codex-compat.md`.
4. Follow `AGENTS.md` Pre-Implementation Checklist.

If the canonical skill conflicts with Codex tool policy, Codex tool policy wins. Report the conflict and continue with the nearest safe equivalent.
