"""Dialectic-CLI entry point — argparse subparsers `run` + `doctor`.

code-conventions.md §6 (`:122-131`) CLI 인자 처리 규약 정합.
"""

import argparse
import sys

from . import orchestrator
from .env_check import check_env
from .ui import Spinner, flush_stdin, stdin_canonical_off, stdin_utf8_mode


def _readline_input(prompt: str) -> str:
    """`input()` readline 라이브러리의 wide-char(한글 등) cursor 계산 결함 회피.

    `input()`은 GNU readline 기반 line edit를 제공하지만 한글·CJK character의 column
    width를 1로 가정 → Backspace 시 cursor가 prompt 영역까지 침범하는 결함 발생.
    `sys.stdin.readline()` 직접 사용 — terminal emulator의 line discipline이 echo·
    Backspace를 처리(wide-char width 정확). 단점: 좌우 이동·히스토리 등 line edit
    기능 잃음. trade-off 수용 (UX 결함 > 편의 기능).

    EOF (`readline` 빈 문자열 반환) → EOFError raise해 `_safe_input`의 catch 분기와 정합.
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line.rstrip("\n").rstrip("\r")


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


class _MenuExit(Exception):
    """`_safe_input` 종료 확인 통과 시 raise — `_interactive_menu` outer try/except가 catch해 return 0."""


def _safe_input(prompt: str) -> str:
    """`_readline_input` wrapper — EOF/Ctrl-C 시 종료 확인 prompt → 'n' 시 원래 prompt 재시도, 그 외는 _MenuExit raise.

    종료 통로 단일화: 사용자가 실수로 Ctrl-C/Ctrl-D 눌러도 즉시 종료 X, 한 번 더 의지 확인 후 종료.
    종료 확인 단계에서 다시 EOF/Ctrl-C → 즉시 _MenuExit (의지 확정).
    """
    while True:
        try:
            flush_stdin()
            return _readline_input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            try:
                ans = _readline_input("종료하시겠습니까? (Enter=종료, n=계속): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                raise _MenuExit
            if ans in ("n", "no"):
                continue
            raise _MenuExit


def _check_env_with_spinner_retry() -> dict | None:
    """`check_env()`를 Spinner+stdin_canonical_off로 wrap. KeyboardInterrupt 시 종료 확인.

    반환: 환경 점검 결과 dict, 사용자 종료 시 None.
    """
    while True:
        try:
            with stdin_canonical_off(), Spinner("환경 점검 중..."):
                res = check_env()
            # spinner 종료 후 race window — 사용자 fast-typing/auto-repeat keystroke가
            # mode 복원·flush 사이에 buffer 누적될 수 있음. grace_period로 추가 폐기.
            flush_stdin(grace_period_s=0.1)
            return res
        except KeyboardInterrupt:
            print()
            try:
                ans = _readline_input("종료하시겠습니까? (Enter=종료, n=계속): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return None
            if ans not in ("n", "no"):
                return None
            # 'n' → 환경 점검 재시도


def _print_env_summary(res: dict) -> None:
    """활성 부족(N<M) 시 어느 sub-check가 fail인지 1줄 안내 (plan 009 env_check 안정화 전 임시)."""
    active = sum(1 for tool in res.values() for r in tool.values() if r["ok"])
    total = sum(1 for tool in res.values() for _ in tool.values())
    if active >= total:
        return
    fails = [
        f"{tool}/{sub}"
        for tool, results in res.items()
        for sub, r in results.items()
        if not r["ok"]
    ]
    print(
        f"환경 점검: 활성 {active}/{total} "
        f"(FAIL: {', '.join(fails)} — `dialectic doctor`로 상세 확인)"
    )


def _input_task() -> str:
    """task input — '?' 도움말 키 + 빈 입력 재요청 retry. `_MenuExit`은 호출자로 propagate.

    prompt는 `> ` 2 ASCII char로 최소화 — terminal emulator wide-char(한글) Backspace
    표시 결함이 있어도 prompt 영역 침범 영향 최소 (입력 buffer 자체는 정확,
    line discipline이 byte 정확 누적).
    """
    while True:
        raw = _safe_input("> ").strip()
        if raw == "?":
            print(
                "도움말: task는 driver(codex)가 구현할 한 줄 작업 의도. "
                "예: 'JSON 파싱 함수 작성', '이진 탐색 트리 구현'. 종료는 Ctrl-C."
            )
            continue
        if not raw:
            print("task가 비었습니다 — 다시 입력하거나 Ctrl-C로 종료.")
            continue
        return raw


def _input_max_turns() -> int:
    """max-turns input — 빈 입력은 default 1, 양수 정수 검증, 비정수/0/음수는 retry."""
    print("max-turns (default 1, 양수 정수)")
    while True:
        raw_turns = _safe_input("> ").strip()
        if not raw_turns:
            return 1
        try:
            value = int(raw_turns)
        except ValueError:
            print(f"정수 필요. 입력: {raw_turns!r} — 다시.")
            continue
        if value < 1:
            print(f"양수 필요 (1 이상). 입력: {value} — 다시.")
            continue
        return value


def _input_confirm(*, max_turns: int, task: str) -> bool:
    """진행 확인 — 'n'/'no' 거부 시 False, 빈/y/invalid는 Y default True.

    task 내용을 echo back — terminal wide-char Backspace 표시 결함이 있어도
    실제 입력 buffer 정확성을 사용자가 시각 검증. 60 char 초과 시 truncate + ellipsis.
    """
    preview = task if len(task) <= 60 else task[:60] + "..."
    print(f"task: {preview!r}")
    print(f"driver=codex, reviewer=claude, {max_turns}턴 — 진행 (n=task 재입력)")
    confirm = _safe_input("[Y/n]> ").strip().lower()
    return confirm not in ("n", "no")


def _interactive_menu() -> int:
    """outline/03-ux §3.2 단계 1·3 minimum cut + UI polish (plan 008-ui-polish).

    Day 2 한정: run 모드 + default 매핑(driver=codex, reviewer=claude) +
    `--interactive end-only` 고정. max-turns은 사용자 입력값.
    단계 2(모드 선택) / 4(매핑·workdir) / 5(턴 진행 화면)는 후속 plan 분리.

    UI 흐름은 4 helper로 분리 (review-code §컨벤션 함수 길이 fix):
    - `_check_env_with_spinner_retry`: 환경 점검 + Ctrl-C 종료 확인 retry
    - `_print_env_summary`: fail sub-check 1줄 안내
    - `_input_task` / `_input_max_turns` / `_input_confirm`: 단계별 input retry
    `_safe_input`이 모든 input을 wrap — EOF/Ctrl-C 시 종료 확인 prompt + 'n' retry
    + 종료 확인 EOF/Ctrl-C 시 `_MenuExit` (의지 확정).
    `stdin_utf8_mode`: line discipline IUTF8 set — 한글 등 multi-byte Backspace
    1회로 한 char 폐기 (default off 시 byte 단위 → cursor 결함).
    """
    with stdin_utf8_mode():
        return _interactive_menu_body()


def _interactive_menu_body() -> int:
    """`_interactive_menu`의 실제 메뉴 흐름. `stdin_utf8_mode` 컨텍스트 안에서 호출."""
    print("Dialectic-CLI · default 매핑 codex→claude (run). 다른 옵션은 CLI 인자로.")

    res = _check_env_with_spinner_retry()
    if res is None:
        return 0
    _print_env_summary(res)

    # prompt는 `> ` 2 char로 최소화 — terminal wide-char(한글) Backspace 표시 결함은
    # IUTF8 + 짧은 prompt + 진행 확인 단계의 task echo back으로 cover (입력 buffer는
    # line discipline이 정확히 누적). 안내·example은 별도 print 라인.
    print("task: 한 줄로 작업 의도. 예: '다익스트라 최단거리 알고리즘 Python 예제 작성'")
    print("'?'=도움말, Ctrl-C=종료. 한글 입력 시 IME 조립 결함으로 일부 char가 buffer에 누락될 수 있음 — 진행 확인 단계의 task echo back 시각 검증 권장.")

    try:
        while True:  # outer: 진행 확인 'n' 거부 시 task 재입력
            task = _input_task()
            max_turns = _input_max_turns()
            if _input_confirm(max_turns=max_turns, task=task):
                break
            print("취소 — task 재입력 (Ctrl-C로 종료).")
    except _MenuExit:
        return 0

    # default 매핑으로 run_session 직접 호출 (parser.parse_args 재호출 회피 — sys.exit 부작용 차단).
    args = argparse.Namespace(
        cmd="run", task=task, workdir=None,
        driver="codex", reviewer="claude",
        max_turns=max_turns, mode="run",
        convergence_streak=2, interactive="end-only",
    )
    # run_session 진행 중 Ctrl-C도 _safe_input과 동일 종료 확인 패턴 (한글 cursor 결함 차단 위해
    # `_readline_input` 통일 — review-code P1 fix).
    try:
        return orchestrator.run_session(args)
    except KeyboardInterrupt:
        print()
        try:
            ans = _readline_input("종료하시겠습니까? (Enter=종료, n=계속): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if ans in ("n", "no"):
            # 'n' → 진행 의지 유지하지만 run_session은 이미 중단됐으니 fresh 재진입.
            return _interactive_menu()
        return 0


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
    sys.exit(main())
