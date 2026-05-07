---
name: review-code
description: Use this in Dialectic-CLI when the user asks Codex to review code using the canonical .claude review-code workflow. Applies Codex compatibility rules from docs/dev-docs/codex-compat.md.
---

# review-code

Codex-native entrypoint for the canonical `.claude/skills/review-code/SKILL.md` workflow.

## Workflow

1. Read `docs/dev-docs/codex-compat.md`.
2. Read `.claude/skills/review-code/SKILL.md`.
3. Apply the Codex overrides from `docs/dev-docs/codex-compat.md`.
4. Preserve the independent-review stance. If subagents are not explicitly authorized, disclose that the review is same-context and apply the checklist more strictly.
5. Do not auto-fix code. Report findings for user synthesis.

If the canonical skill conflicts with Codex tool policy, Codex tool policy wins. Report the conflict and continue with the nearest safe equivalent.
