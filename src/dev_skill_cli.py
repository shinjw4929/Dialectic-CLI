"""Developer skill command wrapper for Dialectic-CLI."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class SkillSpec:
    """Repo-local developer skill metadata."""

    name: str
    path: str
    summary: str

    @property
    def codex_path(self) -> str:
        return f".codex/skills/{self.name}/SKILL.md"


SKILLS: tuple[SkillSpec, ...] = (
    SkillSpec("create-plan", ".claude/skills/create-plan/SKILL.md", "작업 계획 생성"),
    SkillSpec("execute-plan", ".claude/skills/execute-plan/SKILL.md", "plan phase 실행"),
    SkillSpec("review-plan", ".claude/skills/review-plan/SKILL.md", "plan 결함 검토"),
    SkillSpec("review-code", ".claude/skills/review-code/SKILL.md", "코드 결함 검토"),
    SkillSpec("sync-docs", ".claude/skills/sync-docs/SKILL.md", "문서 동기화 누락 점검"),
    SkillSpec("commit", ".claude/skills/commit/SKILL.md", "변경 분류 후 커밋 준비"),
)


def _skill_by_name(name: str) -> SkillSpec | None:
    return next((skill for skill in SKILLS if skill.name == name), None)


def _existing_path(relative_path: str) -> Path:
    path = REPO_ROOT / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"required file not found: {relative_path}")
    return path


def list_skills() -> str:
    lines = [
        "Dialectic-CLI dev skills",
        "",
        "Usage:",
        "  dialectic-skill <workflow> [target]",
        "  dialectic-skill --show <workflow>",
        "",
        "Workflows:",
    ]
    for skill in SKILLS:
        lines.append(f"  {skill.name:<12} {skill.summary}")
    return "\n".join(lines)


def build_prompt(skill: SkillSpec, target: str | None) -> str:
    _existing_path(skill.codex_path)
    _existing_path(skill.path)

    target_text = f" 대상: {target}" if target else ""
    return "\n".join(
        [
            f"${skill.name}",
            "",
            f"`{skill.path}`를 Codex 방식으로 적용해서 `{skill.name}` 실행해줘.{target_text}",
        ]
    )


def show_skill(skill: SkillSpec) -> str:
    return _existing_path(skill.path).read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dialectic-skill",
        description="Generate Codex prompts for repo-local .claude skills.",
    )
    parser.add_argument("workflow", nargs="?", help="Skill workflow name, e.g. sync-docs")
    parser.add_argument("target", nargs="?", help="Optional target, e.g. plan/001-run-mode-core")
    parser.add_argument("--show", action="store_true", help="Print the canonical SKILL.md body")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.workflow:
        print(list_skills())
        return 0

    skill = _skill_by_name(args.workflow)
    if skill is None:
        print(f"error: unknown workflow: {args.workflow}", file=sys.stderr)
        print("run `dialectic-skill` to list workflows", file=sys.stderr)
        return 2

    try:
        output = show_skill(skill) if args.show else build_prompt(skill, args.target)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
