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
        help="작업 디렉토리. 미지정 시 ~/.local/share/dialectic/runs/<timestamp-id>/ 자동 생성. "
             "DIALECTIC_RUNS_DIR / XDG_DATA_HOME 환경변수로 base_dir 변경 가능. "
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
    p_run.add_argument(
        "--spec", type=str, default=None,
        help="implement 모드 입력 — `<workdir>/specs/<slug>.md` 또는 임의 spec.md 경로. "
             "mode==implement 시 required (run_session 진입 시 검증). 다른 모드에선 무시.",
    )
    p_run.set_defaults(func=lambda args: orchestrator.run_session(args))

    # implement (alias subparser — set_defaults(mode="implement", task="") 자동 적용)
    p_implement = subs.add_parser(
        "implement",
        help="dialectic implement 모드 — spec.md 본문을 task 자리에 주입 + "
             "driver(implementer) ↔ reviewer(spec-reviewer)",
    )
    p_implement.add_argument(
        "--spec", required=True, type=str,
        help="implement 모드 spec.md 경로 (필수)",
    )
    p_implement.add_argument("--driver", choices=["codex", "claude"], default="codex")
    p_implement.add_argument("--reviewer", choices=["codex", "claude"], default="claude")
    p_implement.add_argument("--max-turns", type=_positive_int, default=1)
    p_implement.add_argument(
        "--workdir", default=None,
        help="작업 디렉토리. 미지정 시 ~/.local/share/dialectic/runs/<timestamp-id>/ 자동 생성.",
    )
    p_implement.add_argument(
        "--convergence-streak", type=_positive_int, default=2,
        help="reviewer [CONVERGED] 마커 누적 K턴 도달 시 auto_end_converged.",
    )
    p_implement.add_argument(
        "--interactive", choices=["end-only", "critical", "full"], default="end-only",
        help="사용자 개입 강도 dial (outline §3.1).",
    )
    # alias 진입은 mode=implement 자동, task는 빈 문자열 (run_session에서 spec body로 substitution).
    p_implement.set_defaults(
        func=lambda args: orchestrator.run_session(args),
        mode="implement",
        task="",
    )

    # doctor
    p_doc = subs.add_parser("doctor", help="환경 점검 (claude/codex --version + auth status, 비용 0)")
    p_doc.set_defaults(func=lambda args: _print_env_check())

    # logs (outline/03-ux.md §3.5 — Q3 관찰성, plan 010 Phase A 1차 범위)
    p_logs = subs.add_parser(
        "logs",
        help="messages.jsonl 흐름 관찰 (turn/seq/kind 1줄 요약 또는 본문 펼침). plan 010 Phase A.",
    )
    p_logs.add_argument(
        "--workdir", default=None,
        help="workdir 또는 session_dir 직접 지정. 미지정 시 base_dir 우선순위로 자동 탐색 "
             "(DIALECTIC_RUNS_DIR > XDG_DATA_HOME/dialectic/runs > ~/.local/share/dialectic/runs).",
    )
    p_logs.add_argument(
        "--session", default=None,
        help="session_ts(`%%Y%%m%%dT%%H%%M%%SZ`) — `--workdir`가 workdir level일 때 명시 지정. "
             "지정 시 `<workdir>/<session>/`로 직접 해소.",
    )
    p_logs.add_argument(
        "--tail", type=int, default=None,
        help="마지막 N개 메시지만 출력 (kind 필터 적용 후). 미지정 시 전체.",
    )
    p_logs.add_argument(
        "--follow", action="store_true",
        help="EOF 도달 후 polling(0.5s) 새 line append 시 추가 출력. Ctrl-C로 종료. (`src.logs._FOLLOW_POLL_INTERVAL_S` SSOT)",
    )
    p_logs.add_argument(
        "--kind", dest="kind", default=None,
        help="kind 필터 (proposal|critique|decision|error|meta|task|patch_applied 등). 미지정 시 전체.",
    )
    p_logs.add_argument(
        "--full", action="store_true",
        help="본문 펼침 (default 1줄 요약).",
    )
    p_logs.set_defaults(func=_logs_entry)

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


def _print_env_summary(res: dict) -> bool:
    """활성 부족(N<M) 시 FAIL 안내 + 진행 confirm prompt.

    반환: True면 메뉴 진행, False면 FAIL 상태로 진행 거부 (사용자 종료 의사).
    활성 모두 OK면 print 0 + return True (자동 진행).
    """
    active = sum(1 for tool in res.values() for r in tool.values() if r["ok"])
    total = sum(1 for tool in res.values() for _ in tool.values())
    if active >= total:
        return True
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
    # FAIL 상태에서 그대로 진행하면 driver/reviewer 호출 시 어댑터 단에서 즉시 실패 traceback.
    # 사용자가 의도적으로 진행하는 경우만 통과 — default는 종료.
    try:
        ans = _safe_input(
            "FAIL 상태로 계속 진행하시겠습니까? (y=진행, Enter=종료): "
        ).strip().lower()
    except _MenuExit:
        return False
    return ans in ("y", "yes")


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
    - implement → "implement" 반환 → 단계 3에서 `_input_spec_path` 분기 (mode-aware,
      plan 014 wiring)
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
            return "implement"
        if raw == "4":
            print(
                "compare 모드는 별도 subparser(`dialectic compare --configs ...`, "
                "outline :53-57)가 본 plan 외 — 별도 plan에서 wiring 예정. "
                "다른 모드를 선택해주세요."
            )
            continue
        print(f"1/2/3/4 중 선택. 입력: {raw!r} — 다시.")


def _input_spec_path() -> str:
    """단계 3 implement 모드 — spec.md 경로 입력.

    절대 또는 상대 경로 (Path.resolve()로 정규화 후 절대 경로 반환).
    파일 부재·디렉토리·UTF-8 디코딩 실패 시 retry + 안내.
    '?' 도움말 키 — post-010 default workdir narrative 포함
    (`~/.local/share/dialectic/runs/<...>/specs/<slug>.md` 자동 탐색 가능 안내).
    EOF/Ctrl-C → `_safe_input`이 `_MenuExit` raise (기존 `_input_task` 패턴 정합).

    반환: 절대 경로 문자열 (str, Path 아님 — argparse 호환).
    """
    while True:
        raw = _safe_input("> ").strip()
        if raw == "?":
            print(
                "도움말: spec.md는 implement 모드 입력 — driver(implementer)가 본문을 task "
                "자리에 받아 구현. 절대 또는 상대 경로 (해석 후 절대 정규화). "
                "post-010 default workdir에서 plan 모드 산출이 "
                "`~/.local/share/dialectic/runs/<ts-id>/specs/<slug>.md`로 저장 — "
                "해당 경로 직접 입력 가능. 종료는 Ctrl-C."
            )
            continue
        if not raw:
            print("spec 경로가 비었습니다 — 다시 입력하거나 Ctrl-C로 종료.")
            continue
        try:
            path = Path(raw).expanduser().resolve()
        except OSError as exc:
            print(f"경로 해석 실패 ({exc}) — 다시 입력하거나 Ctrl-C로 종료.")
            continue
        if not path.exists():
            print(f"파일 없음: {path} — 다시 입력하거나 Ctrl-C로 종료.")
            continue
        if not path.is_file():
            print(f"디렉토리는 spec.md로 사용 불가: {path} — 다시.")
            continue
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"UTF-8 디코딩 실패 ({exc}) — 다시 입력하거나 Ctrl-C로 종료.")
            continue
        return str(path)


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

    빈 입력(Enter) → None 반환 (orchestrator 자동 생성 —
    `~/.local/share/dialectic/runs/<...>` default, `DIALECTIC_RUNS_DIR`/`XDG_DATA_HOME` env override).
    그 외 입력 → 경로로 해석:
      - 존재하는 디렉토리 → resolve 후 ADR-6 검사, 통과 시 절대 경로 반환
      - 존재하는 파일 → 거부 + 재입력
      - 존재 X → ADR-6 검사 우선, 통과 시 생성 확인 [Y/n]: Y/Enter → mkdir + 반환, n → 재입력

    ADR-6 차단 규칙 SSOT는 `orchestrator.is_under_repo_root` — 본 helper는 동일 predicate
    를 import해 mkdir 직전에 조기 거부 (orphan dir 잔존 + UX 혼란 차단). 규칙 본문은
    여전히 orchestrator (`run_session` 진입 SystemExit), 본 helper는 UX-level 미러.
    `Path(raw).resolve()`는 cwd 기준 — Dialectic-CLI repo 안에서 실행 시 relative path
    (`2`, `test3`)가 repo 하위로 떨어지는 상황을 차단.

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
        if orchestrator.is_under_repo_root(path):
            print(
                f"Dialectic-CLI repo 하위 경로는 workdir로 사용 불가 ({path}, ADR-6) — "
                "claude/codex가 부모 dir CLAUDE.md/AGENTS.md를 auto-discovery해 개발용 "
                ".md가 런타임 prompt에 누수됨. 절대 경로로 repo 밖을 지정하거나 Enter로 "
                "자동 생성을 사용하십시오."
            )
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
    *, max_turns: int, task: str, mode: str, driver: str, reviewer: str,
    workdir: str | None,
    spec: str | None = None,
) -> bool:
    """진행 확인 — 'n'/'no' 거부 시 False, 빈/y/invalid는 Y default True.

    task 또는 spec 경로를 mode-aware로 echo back — terminal wide-char Backspace 표시
    결함이 있어도 실제 입력 buffer 정확성을 사용자가 시각 검증. task는 60 char 초과
    시 truncate + ellipsis.

    mode==implement & spec is not None → "spec: '<path>'" echo
    그 외 → "task: '<preview>'" echo (기존 동작)

    workdir is None → "workdir=auto" (orchestrator default 위임)
    workdir is str  → f"workdir={workdir}"
    """
    if mode == "implement" and spec is not None:
        print(f"spec: {spec!r}")
    else:
        preview = task if len(task) <= 60 else task[:60] + "..."
        print(f"task: {preview!r}")
    workdir_label = "auto" if workdir is None else workdir
    print(
        f"mode={mode}, {driver}→{reviewer}, {max_turns}턴, workdir={workdir_label} "
        f"— 진행 (n=재입력)"
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
    `src/orchestrator.is_under_repo_root` predicate가 단일 진실원. orchestrator
    `run_session` 진입 SystemExit이 final gate, `_input_workdir`은 동일 predicate를
    import해 mkdir 전 UX-level 조기 거부 (orphan dir 잔존 + 사용자 혼란 차단).

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
    if not _print_env_summary(res):
        return 0

    try:
        mode = _input_mode()
    except _MenuExit:
        return 0

    # prompt는 `> ` 2 char로 최소화 — terminal wide-char(한글) Backspace 표시 결함은
    # IUTF8 + 짧은 prompt + 진행 확인 단계의 task echo back으로 cover (입력 buffer는
    # line discipline이 정확히 누적). 안내·example은 별도 print 라인.
    if mode == "implement":
        print(
            "spec: implement 모드 입력 — spec.md 경로 (절대 또는 상대, 해석 후 절대 정규화). "
            "예: ~/.local/share/dialectic/runs/<ts-id>/specs/<slug>.md (plan 모드 산출)."
        )
        print("'?'=도움말, Ctrl-C=종료.")
    else:
        print(
            "task: 한 줄로 작업 의도. "
            "예: '다익스트라 최단거리 알고리즘 Python 예제를 작성해줘. "
            "이때 아스키 아트로 매 턴 시각적 검증이 될 수 있도록 해줘'"
        )
        print("'?'=도움말, Ctrl-C=종료. 한글 입력 시 IME 조립 결함으로 일부 char가 buffer에 누락될 수 있음 — 진행 확인 단계의 task echo back 시각 검증 권장.")

    try:
        while True:  # outer: 진행 확인 'n' 거부 시 task/spec 재입력
            # 단계 3: mode-aware — implement는 spec 경로, 그 외는 task 입력
            if mode == "implement":
                task = ""
                spec = _input_spec_path()
            else:
                task = _input_task()
                spec = None
            driver, reviewer = _input_mapping()
            workdir = _input_workdir()
            max_turns = _input_max_turns()
            if _input_confirm(
                max_turns=max_turns, task=task, mode=mode,
                driver=driver, reviewer=reviewer, workdir=workdir,
                spec=spec,
            ):
                break
            print("취소 — 재입력 (Ctrl-C로 종료).")
    except _MenuExit:
        return 0

    # 사용자 선택 매핑으로 run_session 직접 호출 (parser.parse_args 재호출 회피 — sys.exit 부작용 차단).
    args = argparse.Namespace(
        cmd="run", task=task, workdir=workdir,
        driver=driver, reviewer=reviewer,
        max_turns=max_turns, mode=mode, spec=spec,
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


def _logs_entry(args: argparse.Namespace) -> int:
    """`dialectic logs` argparse Namespace → `render_logs` kwarg 매핑.

    분기:
      - `--workdir` 미지정 → `find_latest_session_dir()` 자동 탐색 (base_dir 우선순위)
      - `--workdir` + `--session` 지정 → `<workdir>/<session>/` 직접
      - `--workdir` only → `resolve_session_dir`이 workdir/session_dir 자동 분기

    plan 010 Phase A 신설. logs 모듈은 `src/logs.py` SSOT.
    """
    # logs 모듈은 lazy import — `dialectic run` 등 다른 subcmd 시작 비용 0 유지.
    from .logs import find_latest_session_dir, render_logs, resolve_session_dir

    if args.workdir is None:
        session_dir = find_latest_session_dir()
        if session_dir is None:
            sys.stderr.write("[logs] 마지막 세션 미발견 — --workdir로 지정\n")
            return 1
    else:
        user_path = Path(args.workdir).resolve()
        if args.session:
            session_dir = user_path / args.session
            if not (session_dir / "messages.jsonl").exists():
                sys.stderr.write(f"[logs] {session_dir}/messages.jsonl 미존재\n")
                return 1
        else:
            resolved = resolve_session_dir(user_path)
            if resolved is None:
                sys.stderr.write(
                    f"[logs] {user_path} 하위 session 미발견 "
                    f"(workdir 자체에 messages.jsonl 없음)\n"
                )
                return 1
            session_dir = resolved
    return render_logs(
        session_dir=session_dir,
        tail=args.tail,
        follow=args.follow,
        kind_filter=args.kind,
        full=args.full,
    )


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
