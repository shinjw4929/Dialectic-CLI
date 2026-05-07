"""Dialectic-CLI entry point — argparse subparsers `run` + `doctor`.

code-conventions.md §6 (`:122-131`) CLI 인자 처리 규약 정합.
"""

import argparse

from . import orchestrator
from .env_check import check_env


def _positive_int(raw: str) -> int:
    """argparse type — 양수만 허용 (음수/0 의미 오류 차단). P-CLI_GUARD 후보 fix.

    --max-turns 0 (빈 루프) / --convergence-streak 0 (streak >= 0 분기에서 첫 마커가 즉시 K=1 동작)
    같은 의미 오류 입력을 argparse 단계에서 차단.
    """
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"int 변환 실패: {raw!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(
            f"양수 필요 (1 이상), 입력: {value}. --max-turns/--convergence-streak 의미 오류 차단."
        )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(prog="dialectic")
    subs = parser.add_subparsers(dest="cmd", required=False)

    # run
    p_run = subs.add_parser("run", help="dialectic 한 턴 실행")
    p_run.add_argument("--task", required=True)
    p_run.add_argument(
        "--workdir", default=None,
        help="작업 디렉토리. 미지정 시 tempfile.mkdtemp(prefix='dialectic-')로 자동 생성. "
             "Dialectic-CLI repo 루트는 ADR-6에 의해 사용 불가 (개발용 .md 누수).",
    )
    p_run.add_argument("--driver", choices=["codex", "claude"], default="codex")
    p_run.add_argument("--reviewer", choices=["codex", "claude"], default="claude")
    p_run.add_argument("--max-turns", type=_positive_int, default=1)
    p_run.add_argument(
        "--mode", choices=["run"], default="run",
        help="Day 2는 'run' 모드만 노출. plan/implement/compare는 Day 3+에서 추가.",
    )
    p_run.add_argument(
        "--convergence-streak", type=_positive_int, default=2,
        help="reviewer [CONVERGED] 마커 누적 K턴 도달 시 auto_end_converged "
             "(outline/02 §2.9). default K=2. ADR-9: --max-turns < K+1 시 K=1 fallback.",
    )
    p_run.add_argument(
        "--interactive", choices=["end-only"], default="end-only",
        help="Day 2 한정 'end-only' 단일 노출. Day 3+에서 full/critical 추가.",
    )
    p_run.set_defaults(func=lambda args: orchestrator.run_session(args))

    # doctor
    p_doc = subs.add_parser("doctor", help="환경 점검 (claude/codex --version + auth status, 비용 0)")
    p_doc.set_defaults(func=lambda args: _print_env_check())

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 0
    return args.func(args)


def _print_env_check() -> int:
    res = check_env()
    for tool, results in res.items():
        print(f"[{tool}]")
        for sub, r in results.items():
            mark = "OK" if r["ok"] else "FAIL"
            line = r["stdout"] or r["stderr"] or "(no output)"
            print(f"  {sub:8s} {mark:4s} {line}")
    ok = all(r["ok"] for tool in res.values() for r in tool.values())
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
