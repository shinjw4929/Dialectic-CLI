"""Dialectic-CLI entry point — argparse subparsers `run` + `doctor`.

code-conventions.md §6 (`:122-131`) CLI 인자 처리 규약 정합.
"""

import argparse
import sys
from pathlib import Path

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
        "--mode", choices=["run", "plan", "implement"],
        default="run",
        help="run/plan/implement 3 모드. compare는 별도 subcommand 필요 (본 plan 외).",
    )
    p_run.add_argument(
        "--convergence-streak", type=_positive_int, default=2,
        help="reviewer [CONVERGED] 마커 누적 K턴 도달 시 auto_end_converged "
             "(outline/02 §2.9). default K=2. ADR-9: --max-turns < K+1 시 K=1 fallback.",
    )
    p_run.add_argument(
        "--interactive", choices=["end-only", "critical", "full"], default="end-only",
        help="사용자 개입 강도 dial (outline §3.1). "
             "end-only=세션 종료 시 1회만 prompt (CLI default). "
             "critical=Ctrl+F 비동기 트리거 + 수렴 시 잠재 prompt. "
             "full=매 턴 6지선다 prompt (end/iterate/skip/abort/replace/etc).",
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


def _input_mode() -> str:
    """단계 2 mode 선택. 4 옵션 표시 (1=run / 2=plan / 3=implement / 4=compare).

    - default Enter = "run" (현재 동작 보존)
    - implement → "implement 모드는 spec.md 경로 입력 wiring이 본 plan 외 — 별도 plan에서
      `dialectic implement` subparser 추가 예정 (outline `:50`)." 안내 + retry
    - compare → "compare 모드는 별도 subparser(`dialectic compare --configs ...`,
      outline `:53-57`)가 본 plan 외 — 별도 plan에서 wiring 예정." 안내 + retry
    - 그 외 입력 → 재입력
    """
    print("mode 선택 (1=run / 2=plan / 3=implement / 4=compare, default Enter=run)")
    while True:
        raw = _safe_input("> ").strip()
        if raw == "" or raw == "1":
            return "run"
        if raw == "2":
            return "plan"
        if raw == "3":
            print(
                "implement 모드는 spec.md 경로 입력 wiring이 본 plan 외 — "
                "별도 plan에서 `dialectic implement` subparser 추가 예정 (outline :50). "
                "다른 모드를 선택해주세요."
            )
            continue
        if raw == "4":
            print(
                "compare 모드는 별도 subparser(`dialectic compare --configs ...`, "
                "outline :53-57)가 본 plan 외 — 별도 plan에서 wiring 예정. "
                "다른 모드를 선택해주세요."
            )
            continue
        print(f"1/2/3/4 중 선택. 입력: {raw!r} — 다시.")


def _input_mapping() -> tuple[str, str]:
    """단계 4 driver/reviewer 매핑 선택. 2 조합 표시 (outline `:166-170` 정확 추종).

    1) codex → claude   (default)
    2) claude → codex   (스왑)

    default Enter = (1) → ("codex", "claude")
    invalid → 재입력
    EOF/Ctrl-C → _safe_input이 종료 확인 prompt → _MenuExit propagate
    """
    print("매핑 선택 (1=codex→claude / 2=claude→codex, default Enter=1)")
    while True:
        raw = _safe_input("> ").strip()
        if raw == "" or raw == "1":
            return ("codex", "claude")
        if raw == "2":
            return ("claude", "codex")
        print(f"1/2 중 선택. 입력: {raw!r} — 다시.")


def _input_workdir() -> str | None:
    """단계 4 workdir 선택. single-prompt UX.

    빈 입력(Enter) → None 반환 (orchestrator 자동 생성 — `tempfile.mkdtemp(...)` 또는
    plan 010 진입 후 `~/.local/share/dialectic/runs/<...>`).
    그 외 입력 → 경로로 해석:
      - 존재하는 디렉토리 → resolve된 절대 경로 반환
      - 존재하는 파일 → 거부 + 재입력
      - 존재 X → 생성 확인 [Y/n]: Y/Enter → mkdir + 반환, n → 재입력

    repo-root 차단은 본 helper의 책임 X — orchestrator `:616-625`의
    `DIALECTIC_REPO_ROOT` SystemExit이 SSOT (단일 진실원 보존, P-VENDOR 회피).
    사용자가 repo-root 입력 시 orchestrator 진입 직후 SystemExit으로 차단됨.

    EOF/Ctrl-C → `_safe_input`이 종료 확인 prompt → `_MenuExit` propagate.
    """
    print("workdir (Enter=자동 생성된 작업 디렉토리, 또는 절대 경로 직접 입력)")
    while True:
        raw = _safe_input("> ").strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except OSError as exc:
            print(f"경로 해석 실패 ({exc}) — 다시 입력하거나 Ctrl-C로 종료.")
            continue
        if path.is_file():
            print(f"파일은 workdir로 사용 불가: {path} — 다시.")
            continue
        if path.is_dir():
            return str(path)
        confirm = _safe_input(
            f"디렉토리 없음 ({path}) — 생성 후 진행? [Y/n]> "
        ).strip().lower()
        if confirm in ("n", "no"):
            print("취소 — workdir 다시 입력 (Ctrl-C로 종료).")
            continue
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"디렉토리 생성 실패 ({exc}) — 다시 입력하거나 Ctrl-C로 종료.")
            continue
        print(f"디렉토리 생성: {path}")
        return str(path)


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


def _input_confirm(
    *, max_turns: int, task: str, mode: str, driver: str, reviewer: str, workdir: str | None
) -> bool:
    """진행 확인 — 'n'/'no' 거부 시 False, 빈/y/invalid는 Y default True.

    task 내용을 echo back — terminal wide-char Backspace 표시 결함이 있어도
    실제 입력 buffer 정확성을 사용자가 시각 검증. 60 char 초과 시 truncate + ellipsis.

    workdir is None → "workdir=auto" (orchestrator default 위임)
    workdir is str  → f"workdir={workdir}"
    """
    preview = task if len(task) <= 60 else task[:60] + "..."
    workdir_label = "auto" if workdir is None else workdir
    print(f"task: {preview!r}")
    print(
        f"mode={mode}, {driver}→{reviewer}, {max_turns}턴, workdir={workdir_label} "
        f"— 진행 (n=task 재입력)"
    )
    confirm = _safe_input("[Y/n]> ").strip().lower()
    return confirm not in ("n", "no")


def _interactive_menu() -> int:
    """outline/03-ux §3.2 5단계 메뉴 wiring (plan 011-menu-expansion 완료 후).

    outline `:104-179` narrative 정확 추종:
    - 단계 1: 환경 점검 spinner (`_check_env_with_spinner_retry` + `_print_env_summary`)
    - 단계 2: mode 선택 (`_input_mode` — run/plan; implement·compare는 안내 + retry)
    - 단계 3: task 입력 (`_input_task`)
    - 단계 4: 매핑 + workdir + max-turns (`_input_mapping` + `_input_workdir` + `_input_max_turns`)
    - 단계 5: 진행 확인 + execute (`_input_confirm` + `orchestrator.run_session`)

    plan 009 산출 보존: Namespace `interactive="critical"` (CLI default `end-only`와 별개).

    workdir repo-root 차단은 ADR-6 SSOT — `docs/dev-docs/architecture.md` ADR-6 +
    `src/orchestrator.py:616-625` `DIALECTIC_REPO_ROOT` SystemExit 단일 진실원.
    메뉴 helper(`_input_workdir`)는 입력만 수집하고 검증을 위임 (P-VENDOR 회피).

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

    try:
        mode = _input_mode()
    except _MenuExit:
        return 0

    # prompt는 `> ` 2 char로 최소화 — terminal wide-char(한글) Backspace 표시 결함은
    # IUTF8 + 짧은 prompt + 진행 확인 단계의 task echo back으로 cover (입력 buffer는
    # line discipline이 정확히 누적). 안내·example은 별도 print 라인.
    print(
        "task: 한 줄로 작업 의도. "
        "예: '다익스트라 최단거리 알고리즘 Python 예제를 작성해줘. "
        "이때 아스키 아트로 매 턴 시각적 검증이 될 수 있도록 해줘'"
    )
    print("'?'=도움말, Ctrl-C=종료. 한글 입력 시 IME 조립 결함으로 일부 char가 buffer에 누락될 수 있음 — 진행 확인 단계의 task echo back 시각 검증 권장.")

    try:
        while True:  # outer: 진행 확인 'n' 거부 시 task 재입력
            task = _input_task()
            driver, reviewer = _input_mapping()
            workdir = _input_workdir()
            max_turns = _input_max_turns()
            if _input_confirm(
                max_turns=max_turns, task=task, mode=mode,
                driver=driver, reviewer=reviewer, workdir=workdir,
            ):
                break
            print("취소 — task 재입력 (Ctrl-C로 종료).")
    except _MenuExit:
        return 0

    # 사용자 선택 매핑으로 run_session 직접 호출 (parser.parse_args 재호출 회피 — sys.exit 부작용 차단).
    args = argparse.Namespace(
        cmd="run", task=task, workdir=workdir,
        driver=driver, reviewer=reviewer,
        max_turns=max_turns, mode=mode,
        convergence_streak=2, interactive="critical",
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
