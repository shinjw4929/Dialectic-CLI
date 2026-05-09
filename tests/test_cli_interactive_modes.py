"""Phase A · 009-user-synthesis-wiring — `--interactive` choices 확장 단위 테스트.

plan/009-user-synthesis-wiring/phase-a-cli-mode.md §3·§5 정합.

검증:
1. argparse `--interactive` 3 mode (end-only/critical/full) parsing 통과
2. `--interactive` default = `"end-only"` (CLI 직접 호출 시 자동 dialectic 유지)
3. 잘못된 mode (`partial` 등) argparse 자동 차단 (SystemExit)
4. `_interactive_menu_body` 메뉴 default = `"critical"` (Namespace 빌더 격리)

격리 방침: `parser.parse_args` / `argparse.Namespace` 직접 단언만 사용.
`from src.cli import main; main()`은 `args.func` 통해 실 codex/claude 호출 발생 →
P0-2 격리 의도와 정반대이므로 사용 X.
"""

from __future__ import annotations

import argparse
import inspect

import pytest

from src import cli


def _build_parser() -> argparse.ArgumentParser:
    """cli.main 본문에서 parser 구성 부분만 재현 (실 호출 회피)."""
    parser = argparse.ArgumentParser(prog="dialectic")
    subs = parser.add_subparsers(dest="cmd", required=False)
    p_run = subs.add_parser("run")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--workdir", default=None)
    p_run.add_argument("--driver", choices=["codex", "claude"], default="codex")
    p_run.add_argument("--reviewer", choices=["codex", "claude"], default="claude")
    p_run.add_argument("--max-turns", type=cli._positive_int, default=1)
    p_run.add_argument("--mode", choices=["run"], default="run")
    p_run.add_argument("--convergence-streak", type=cli._positive_int, default=2)
    p_run.add_argument(
        "--interactive",
        choices=["end-only", "critical", "full"],
        default="end-only",
    )
    return parser


@pytest.mark.parametrize("mode", ["end-only", "critical", "full"])
def test_interactive_choices_3_mode_parsing(mode: str) -> None:
    """3 mode 모두 argparse parsing 통과 — Phase A §4 작업단위."""
    parser = _build_parser()
    args = parser.parse_args(["run", "--task", "x", "--interactive", mode])
    assert args.interactive == mode


def test_interactive_default_is_end_only() -> None:
    """CLI default = end-only 유지 (Phase A §3 출력 정합)."""
    parser = _build_parser()
    args = parser.parse_args(["run", "--task", "x"])
    assert args.interactive == "end-only"


def test_interactive_invalid_mode_rejected() -> None:
    """choices 외 값 (`partial` 등) argparse 자동 차단 → SystemExit."""
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--task", "x", "--interactive", "partial"])


def test_interactive_menu_default_is_critical() -> None:
    """`_interactive_menu_body` Namespace 빌더의 interactive default = critical.

    plan body §3.2 — Day 2의 메뉴 default `end-only` → `critical` 변경.
    `inspect.getsource`로 함수 본문 텍스트 단언 (실 메뉴 흐름 호출 X).
    """
    src = inspect.getsource(cli._interactive_menu_body)
    assert 'interactive="critical"' in src
    assert 'interactive="end-only"' not in src


def test_cli_module_argparse_choices_3_mode() -> None:
    """실 cli.main이 등록한 parser도 3 mode를 노출하는지 회귀 보호.

    `_build_parser` 재현이 cli.main 본문과 다르면 본 단언이 실패해 drift 알림.
    """
    cli_src = inspect.getsource(cli.main)
    assert 'choices=["end-only", "critical", "full"]' in cli_src
