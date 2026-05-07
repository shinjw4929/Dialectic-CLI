---
name: execute-plan
description: Use this in Dialectic-CLI when the user asks Codex to execute a plan directory using the canonical .claude execute-plan workflow. Applies Codex compatibility rules from docs/dev-docs/codex-compat.md.
---

# execute-plan

Codex-native entrypoint for the canonical `.claude/skills/execute-plan/SKILL.md` workflow.

## Workflow

1. Read `docs/dev-docs/codex-compat.md`.
2. Read `.claude/skills/execute-plan/SKILL.md`.
3. Apply the Codex overrides from `docs/dev-docs/codex-compat.md`.
4. Preserve the phase graph semantics. Execute sequentially in the main Codex thread unless the user explicitly authorizes subagents or parallel agent work.
5. Follow `AGENTS.md` Pre/Post-Implementation Checklist.

If the canonical skill conflicts with Codex tool policy, Codex tool policy wins. Report the conflict and continue with the nearest safe equivalent.
