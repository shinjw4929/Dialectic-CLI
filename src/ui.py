"""사용자 개입 UI — 6지선다 + directive + spinner.

outline/03-ux.md §3.3 SSOT 키 매핑 (a/r/m/i/e/s).
Enter = iterate + empty directive (default UX).
EOF/KeyboardInterrupt = end (비대화형 환경 안전망).
"""

from __future__ import annotations

import os
import select
import signal
import sys
import termios
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from .schema import Meta

# spinner / drain timing 상수 — 매직 넘버 회피 (review-code §컨벤션 매직 넘버 항목)
SPINNER_TICK_S = 0.1          # spinner 프레임 갱신 주기
DRAIN_POLL_S = 0.05            # stdin drain thread select timeout
DRAIN_BUF_BYTES = 4096         # os.read drain buf 크기
THREAD_JOIN_TIMEOUT_S = 1.0    # spinner/drain thread join 한계

DECISION_KEYS = ("a", "r", "m", "i", "e", "s")  # outline/03-ux §3.3 SSOT 1:1

KEY_LABEL = {
    "a": "accept driver",
    "r": "accept reviewer",
    "m": "merge",
    "i": "iterate",
    "e": "end",
    "s": "skip review",
}

# spinner ANSI 프레임 — code-conventions §2 외부 의존성 0
SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

VENDOR_LABEL = {
    "codex": "Codex CLI",
    "claude": "Claude Code",
    "mock": "Mock",
}

ROLE_LABEL_KO = {
    "implementer":   "구현자",
    "spec-reviewer": "기획 검토자",
    "planner":       "계획자",
    "plan-reviewer": "계획 검토자",
}

INVALID_RETRY_LIMIT = 3  # 잘못된 키 입력 retry 한계 — 비대화형 환경 fallback 트리거


def prompt_decision(
    turn_id: int,
    *,
    interactive_mode: str = "end-only",
) -> tuple[str, str | None]:
    """6지선다 + directive 한 줄 입력. 반환 (key, directive_or_None).

    - turn_id: prompt 라벨 출력에 사용 (outline §3.2 line 216 형식
      `[User Synthesis · Turn {turn_id}]`). retry 시도 N회 안에서 turn_id 불변
    - Enter (빈 입력) → ("i", None)
    - 잘못된 키 → 안내 + retry. INVALID_RETRY_LIMIT 회 fail → ("i", None) fallback
    - KeyboardInterrupt / EOFError → ("e", None) — Ctrl-C·파이프·CI 안전망
    - interactive_mode == "end-only" 시 directive 입력 단계 skip (key만)

    호출자: 본 plan 범위 내 0건 (test 외). 후속 plan(`--interactive critical/full`)에서
    orchestrator.run_session 또는 turn loop 내 호출 wiring.
    """
    label = f"[User Synthesis · Turn {turn_id}]"
    options = " / ".join(f"{k}={KEY_LABEL[k]}" for k in DECISION_KEYS)
    invalid_count = 0

    while invalid_count < INVALID_RETRY_LIMIT:
        try:
            print(label, file=sys.stderr)
            print(options, file=sys.stderr)
            raw = input("> ")
        except (EOFError, KeyboardInterrupt):
            return ("e", None)

        key = raw.strip().lower()
        if key == "":
            return ("i", None)
        if key in DECISION_KEYS:
            if interactive_mode == "end-only":
                return (key, None)
            try:
                directive = input("directive (one line, Enter for empty)> ")
            except (EOFError, KeyboardInterrupt):
                return (key, None)
            directive = directive.strip()
            return (key, directive if directive else None)

        invalid_count += 1
        print(
            f"invalid key: {raw!r}. expected one of {DECISION_KEYS} or Enter.",
            file=sys.stderr,
        )

    # INVALID_RETRY_LIMIT 회 fail → iterate fallback
    return ("i", None)


class Spinner:
    """ANSI spinner (frames=SPINNER_FRAMES). threading.Thread daemon.
    `not sys.stderr.isatty()` 시 모든 메서드 no-op (CI·파이프 silent).
    컨텍스트 매니저로 `with Spinner("running..."): ...` 사용.
    __exit__에서 Event.set() + thread.join(timeout=1) — daemon이지만 명시 정리.
    """

    def __init__(self, message: str = "") -> None:
        self._message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._enabled = bool(getattr(sys.stderr, "isatty", lambda: False)())

    def _run(self) -> None:
        i = 0
        while not self._stop.is_set():
            frame = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
            try:
                sys.stderr.write(f"\r{frame} {self._message}")
                sys.stderr.flush()
            except Exception:
                return
            i += 1
            if self._stop.wait(SPINNER_TICK_S):
                break
        try:
            # ANSI `\x1b[2K`: 현재 라인 전체 clear (cursor 위치 무관). `len(message) + 2`
            # ASCII space로 덮는 방식은 wide-char(한글 등) 시각 width 불일치 시 잔여 발생.
            sys.stderr.write("\r\x1b[2K")
            sys.stderr.flush()
        except Exception:
            pass

    def __enter__(self) -> "Spinner":
        if self._enabled:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        if not self._enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=THREAD_JOIN_TIMEOUT_S)


# Linux <termios.h> IUTF8 비트 (Python termios 모듈에 미노출 빌드 fallback).
# uapi/asm-generic/termbits.h `#define IUTF8 0040000` SSOT.
_LINUX_IUTF8 = 0o040000


@contextmanager
def stdin_utf8_mode() -> Iterator[None]:
    """Linux line discipline IUTF8 iflag set — UTF-8 multi-byte Backspace 정상 처리.

    line discipline default는 IUTF8 off → 한글(3 byte) 같은 multi-byte를 byte 단위
    Backspace로 처리해 1byte씩 지움. IUTF8 set 시 multi-byte를 한 char 단위로 인식,
    Backspace 1회로 wide-char 전체 폐기. cursor 위치 정상.

    Python termios 모듈이 IUTF8 상수 미노출 빌드(WSL 일부 등)에선 Linux hardcode 값
    `0o040000` fallback (sys.platform이 'linux'로 시작 시만). 비-Linux/비-tty는 silent
    skip. 종료 시 원래 iflag 복원.
    """
    if not sys.stdin.isatty():
        yield
        return
    iutf8 = getattr(termios, "IUTF8", None)
    if iutf8 is None and sys.platform.startswith("linux"):
        iutf8 = _LINUX_IUTF8
    if iutf8 is None:
        yield
        return
    try:
        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
    except (OSError, termios.error):
        # termios.error는 OSError 하위 클래스가 아님 (검증: issubclass False) —
        # 명시 catch 필수. tcgetattr 실패 시 silent skip (P-RAW 견고성).
        yield
        return
    new_attrs = list(old_attrs)
    new_attrs[0] |= iutf8
    try:
        termios.tcsetattr(fd, termios.TCSANOW, new_attrs)
    except (OSError, termios.error):
        # set 실패 시 silent skip — yield 후 contextmanager 정상 종료, 기능만 비활성.
        yield
        return
    try:
        yield
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSANOW, old_attrs)
        except (OSError, termios.error):
            pass


@contextmanager
def stdin_canonical_off() -> Iterator[None]:
    """spinner/긴 작업 동안 stdin canonical mode + echo off + 적극 drain thread —
    사용자 키 입력이 line으로 완성되어 다음 `input(...)` prompt에 누수되는 결함 차단.

    3중 방어:
    1. **canonical mode + echo off** (`termios.tcsetattr(TCSAFLUSH)`) — line discipline
       자체를 끔. Enter도 byte 단위로만 들어가고 line으로 완성 안 됨.
    2. **drain thread** — spinner 동안 daemon thread가 select+os.read로 stdin을 적극
       폐기. termios 효과 없는 환경(WSL 일부 PTY 등)에서도 byte 즉시 drain.
    3. **종료 시 mode 복원 + tcflush** — 원래 attrs 복원 (TCSAFLUSH) + 잔여 buffer 폐기.

    isatty=False (CI/파이프) 또는 비-POSIX(Windows) 또는 termios 미지원 fd 시 silent
    (yield only — context body는 그대로 실행).
    """
    if not sys.stdin.isatty():
        yield
        return
    try:
        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
    except (OSError, termios.error):
        # termios.error는 OSError 하위 클래스가 아님 (검증: issubclass False) —
        # 명시 catch 필수. tcgetattr 실패 시 silent skip (P-RAW 견고성).
        yield
        return

    stop_event = threading.Event()

    def _drain_loop() -> None:
        """spinner 동안 stdin byte를 즉시 read해 폐기 (line으로 완성 차단의 적극적 보강).

        ISIG 처리 보존: drain이 raw read하면 line discipline이 INTR character(`\\x03`,
        Ctrl-C)를 SIGINT로 변환할 시간 없이 byte로 폐기됨 — Ctrl-C 무력화 결함. 본 loop가
        직접 `\\x03` 감지 시 main thread에 SIGINT raise (`os.kill(getpid(), SIGINT)`)
        하여 사용자 종료 의도 보존.
        """
        while not stop_event.is_set():
            try:
                ready, _, _ = select.select([fd], [], [], DRAIN_POLL_S)
                if ready:
                    data = os.read(fd, DRAIN_BUF_BYTES)
                    if not data:
                        # EOF — PTY closed. busy loop 차단 위해 즉시 종료 (C-013, P-RAW).
                        return
                    if b"\x03" in data:  # Ctrl-C INTR character
                        os.kill(os.getpid(), signal.SIGINT)
                        return
            except (OSError, ValueError):
                return

    drain_thread = threading.Thread(target=_drain_loop, daemon=True)

    new_attrs = list(old_attrs)
    new_attrs[3] = new_attrs[3] & ~termios.ICANON & ~termios.ECHO
    # TCSAFLUSH: mode 변경 시 pending input/output queue 동시 flush.
    # set 실패 silent skip — `stdin_utf8_mode` 정책과 일관 (P-RAW: tty이지만 권한·기능
    # 미지원 환경 호환). yield 후 finally는 drain_thread.is_alive() guard로 자연 정리.
    try:
        termios.tcsetattr(fd, termios.TCSAFLUSH, new_attrs)
    except (OSError, termios.error):
        yield
        return
    try:
        drain_thread.start()
        yield
    finally:
        stop_event.set()
        # is_alive() guard: tcsetattr OSError/termios.error로 thread.start() 미실행 path에서
        # join이 RuntimeError("cannot join thread before it is started") 발생 → 원본 예외 mask
        # + mode 복원 차단. start 성공 path에서만 join (C-012, P-RAW 인접).
        if drain_thread.is_alive():
            drain_thread.join(timeout=THREAD_JOIN_TIMEOUT_S)
        try:
            # 복원도 TCSAFLUSH — 잔여 buffer 폐기 + 원래 attrs 적용.
            termios.tcsetattr(fd, termios.TCSAFLUSH, old_attrs)
            termios.tcflush(fd, termios.TCIFLUSH)
        except (OSError, termios.error):
            pass


def flush_stdin(*, grace_period_s: float = 0.0) -> None:
    """spinner/긴 작업 동안 stdin buffer에 쌓인 입력 폐기 (tty 한정).

    Spinner 중 사용자가 Enter 누르면 다음 `input(...)` prompt가 그 `\\n`을 즉시
    소비해 빈 문자열 반환 — 의도치 않게 단계 skip되는 UX 결함 차단.

    POSIX `termios.tcflush(TCIFLUSH)`로 kernel input queue 1차 drain + `select`로
    stdin ready 감지 후 `os.read` 비-blocking drain 2차 (terminal line discipline에
    이미 line이 완성됐거나 readline 등 추가 buffer 영역 누수 방지).

    `grace_period_s > 0`: deadline 기반 polling — spinner 종료 직후 mode 복원·flush
    사이의 race window를 통과하는 fast-typing/auto-repeat keystroke까지 폐기.
    예: spinner 직후 `flush_stdin(grace_period_s=0.1)` → 100ms 동안 들어오는 byte
    추가 drain. 의도된 사용자 입력 시작 전 grace이라 영향 0.

    isatty=False (CI/파이프) 또는 비-POSIX(Windows native) 환경은 silent skip.
    """
    if not sys.stdin.isatty():
        return
    try:
        fd = sys.stdin.fileno()
        # 1차: kernel input queue drain
        termios.tcflush(fd, termios.TCIFLUSH)
        # 2차: select + os.read polling drain
        # grace_period_s>0 시 deadline까지 polling, 0 시 즉시 ready만 드레인.
        deadline: float | None = None
        if grace_period_s > 0:
            deadline = time.monotonic() + grace_period_s
        while True:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                timeout = min(remaining, DRAIN_POLL_S)
            else:
                timeout = 0.0
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                if deadline is None:
                    break
                continue
            chunk = os.read(fd, DRAIN_BUF_BYTES)
            # EOF guard 일관 (C-013, P-RAW): 빈 bytes 받으면 grace/즉시 모드 무관 즉시 종료.
            # grace mode에서 EOF 시 select가 ready 반환을 반복 → CPU busy loop 차단.
            if not chunk:
                break
    except (OSError, termios.error):
        pass


ANSI_CYAN = "\x1b[36m"
ANSI_YELLOW = "\x1b[33m"
ANSI_GREEN = "\x1b[32m"
ANSI_RED = "\x1b[31m"
ANSI_RESET = "\x1b[0m"

KIND_COLOR = {
    "proposal": ANSI_CYAN,
    "critique": ANSI_YELLOW,
    "decision": ANSI_GREEN,
    "error":    ANSI_RED,
}

# outline/03-ux §3.2 line 193·201·205 구분선 — 65 chars `─`
SEPARATOR = "─" * 65


def print_message(
    *,
    role_label: str,
    vendor_label: str,
    kind: str,
    text: str,
    meta: "Meta",
) -> None:
    """outline/03-ux §3.2 line 193-201 형식 1:1로 stdout 출력.

    형식:
        ─────────────────────────────────────────────────────────────────
        [{role_label}: {vendor_label}] ✓ {latency}s · {output_tokens} out / {input_tokens} in[· ${cost:.3f}]
        ─────────────────────────────────────────────────────────────────
        {text}
        ─────────────────────────────────────────────────────────────────

    - `latency` = meta.latency_ms / 1000.0, 소수점 1자리 (`{:.1f}`)
    - `cost` 표시는 `meta.cost_usd is not None` 시에만 ` · ${cost:.3f}` 부분 추가
    - ANSI 색상: KIND_COLOR.get(kind, "") — 헤더 라인만 색상 (구분선·본문은 평문)
    - `sys.stdout.isatty()` False 시 ANSI 색상 모두 빈 문자열 치환 (capsys/CI 회귀 차단)
    - 출력 자체는 isatty 무관 항상 진행
    """
    isatty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    color = KIND_COLOR.get(kind, "") if isatty else ""
    reset = ANSI_RESET if isatty and color else ""

    latency = meta.latency_ms / 1000.0
    cost_part = f" · ${meta.cost_usd:.3f}" if meta.cost_usd is not None else ""
    header = (
        f"{color}[{role_label}: {vendor_label}] ✓ {latency:.1f}s · "
        f"{meta.output_tokens} out / {meta.input_tokens} in{cost_part}{reset}"
    )

    sys.stdout.write(SEPARATOR + "\n")
    sys.stdout.write(header + "\n")
    sys.stdout.write(SEPARATOR + "\n")
    sys.stdout.write(text + "\n")
    sys.stdout.write(SEPARATOR + "\n")
    sys.stdout.flush()
