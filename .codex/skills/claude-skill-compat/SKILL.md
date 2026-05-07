---
name: claude-skill-compat
description: Use this in Dialectic-CLI when the user asks Codex to run or follow the repo's .claude/skills workflows such as create-plan, execute-plan, review-plan, review-code, sync-docs, or commit. This is a Codex compatibility layer over the canonical Claude skill files.
---

# Claude Skill Compatibility

This skill lets Codex use the repo-local `.claude/skills` workflows without copying their full bodies into Codex-specific files. The canonical Codex compatibility policy lives in `docs/dev-docs/codex-compat.md`; this file is the thin Codex skill-discovery adapter.

## Canonical Policy

Read `docs/dev-docs/codex-compat.md` first. It defines canonical sources, Codex overrides, workflow steps, command wrapper behavior, and reporting text.

## Workflow

1. Identify the requested workflow name.
2. Read `docs/dev-docs/codex-compat.md`.
3. Read the matching canonical `.claude/skills/<workflow>/SKILL.md`.
4. Apply the Codex overrides from `docs/dev-docs/codex-compat.md`.
5. Follow `AGENTS.md` Pre/Post-Implementation Checklist.

If the canonical skill conflicts with Codex tool policy, Codex tool policy wins. Report the conflict and continue with the nearest safe equivalent.
