---
name: review-plan
description: Use this in Dialectic-CLI when the user asks Codex to review a plan using the canonical .claude review-plan workflow. Applies Codex compatibility rules from docs/dev-docs/codex-compat.md.
---

# review-plan

Codex-native entrypoint for the canonical `.claude/skills/review-plan/SKILL.md` workflow.

## Workflow

1. Read `docs/dev-docs/codex-compat.md`.
2. Read `.claude/skills/review-plan/SKILL.md`.
3. Apply the Codex overrides from `docs/dev-docs/codex-compat.md`.
4. Preserve the independent-review stance. If subagents are not explicitly authorized, disclose that the review is same-context and apply the checklist more strictly.
5. Do not auto-edit the plan. Report findings for user synthesis.

If the canonical skill conflicts with Codex tool policy, Codex tool policy wins. Report the conflict and continue with the nearest safe equivalent.
