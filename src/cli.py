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
        return _interactive_menu()
    return args.func(args)


def _interactive_menu() -> int:
    """outline/03-ux §3.2 단계 1·3 minimum cut.

    Day 2 한정: run 모드 + default 매핑(driver=codex, reviewer=claude) +
    max-turns=1 + --interactive end-only 고정.
    단계 2(모드 선택) / 4(매핑·workdir) / 5(턴 진행 화면)는 후속 plan 분리.

    EOFError / KeyboardInterrupt → exit 0 (안전 종료).

    parser 인자 미수령 — Namespace 직접 구성으로 argparse 분기 우회 (cli.py
    args.func(args) 패턴과 비대칭은 minimum cut 한정, 후속 plan에서 정합화 검토).
    """
    print("Dialectic-CLI · Day 2 minimum cut: run 모드 + default 매핑 (codex/claude).")
    print("다른 옵션은 CLI 인자로 직접 지정.\n")

    # 환경 점검 1줄 요약 (env_check.check_env() 결과 → 활성 N/M 형태)
    res = check_env()
    active = sum(1 for tool in res.values() for r in tool.values() if r["ok"])
    total = sum(1 for tool in res.values() for _ in tool.values())
    print(f"환경 점검: 활성 {active}/{total}\n")

    try:
        task = input("task (한 줄): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()  # newline 정리
        return 0
    if not task:
        print("task 비어 있음 — 종료.")
        return 0

    # default 매핑으로 run_session 직접 호출 (parser.parse_args 재호출 회피 — sys.exit 부작용 차단).
    # argparse Namespace 직접 구성: run subparser default 값 + task input 합성.
    args = argparse.Namespace(
        cmd="run", task=task, workdir=None,
        driver="codex", reviewer="claude",
        max_turns=1, mode="run",
        convergence_streak=2, interactive="end-only",
    )
    return orchestrator.run_session(args)


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
