"""사용자 개입 UI — 6지선다 + directive + spinner.

outline/03-ux.md §3.3 SSOT 키 매핑 (a/r/m/i/e/s).
Enter = iterate + empty directive (default UX).
EOF/KeyboardInterrupt = end (비대화형 환경 안전망).
"""

from __future__ import annotations

import fcntl
import os
import queue
import select
import signal
import sys
import threading
import time
import tty
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

try:
    import termios
except ImportError:  # pragma: no cover — Windows native cmd
    termios = None  # type: ignore[assignment]

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
    "spec-reviewer": "코드 검토자",
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

    호출자: orchestrator.run_session full 모드 (plan 009-user-synthesis-wiring 산출).
    매 턴 끝 호출 — 6 분기 (a/r/m/i/e/s) 결과는 `_decision_msg` (kind=decision, seq=97)로
    JSONL 보존. critical 모드는 별도 함수 `prompt_end_or_iterate` (Y/n/text 분기).
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


def _read_line_for_prompt() -> str:
    """fd-level readline — Python `sys.stdin` TextIOWrapper buffer 우회.

    사용자 결함 환원 (1.5차 fix 후에도 발생): GNU readline lib 우회 후에도 Python
    TextIOWrapper internal buffer가 listener thread race로 채워지지 않거나, listener
    thread가 join timeout으로 백그라운드에서 stdin byte 절도 → readline()이 빈 newline
    만 받음. 본 helper는 `os.read(fd, 4096)`로 byte 단위 직접 누적 — TextIOWrapper
    buffer 완전 우회. canonical mode가 line discipline 처리 (newline까지 byte buffer).

    `flush_stdin` 호출 X — TriggerListener.__exit__가 이미 queue drain + tcsetattr
    TCSAFLUSH + tcflush(TCIFLUSH)로 stdin 청소. prompt 표시 후 추가 drain은 사용자가
    반사적으로 타이핑한 'y'/'c' byte를 grace_period_s 안에서 폐기 → 빈 줄 처리 →
    INVALID_RETRY 반복 결함 (사용자 보고 환원, plan 015 정공법 추가 fix). prompt
    표시 후 사용자 byte는 모두 의도된 입력 — 추가 drain 금지.

    EOF (chunk 빈 bytes) 시 EOFError raise — 호출자가 ("e", None) fallback 처리.
    """
    fd = sys.stdin.fileno()
    buf = bytearray()
    while True:
        chunk = os.read(fd, 4096)
        if not chunk:
            raise EOFError
        buf.extend(chunk)
        if b"\n" in chunk:
            break
    line, _, _ = bytes(buf).partition(b"\n")
    return line.decode("utf-8", errors="replace").rstrip("\r")


def prompt_end_or_iterate(
    turn_id: int,
    reason: str,
    *,
    allow_continue: bool = True,
    allow_iterate_no_directive: bool = True,
) -> tuple[str, str | None]:
    """critical 모드 매 턴 끝 prompt — Y/n/text 3 분기.

    잠재 prompt 시점 narrative:
      호출 시점은 critical 모드 매 턴 끝의 "잠재 prompt 시점" — Phase D
      orchestrator wiring에서 `should_prompt = trigger.is_set() OR converged_now
      OR last_turn_now` 셋 OR 분기. "종료 직전"이 아니라 "사용자 결정 잠재 시점".
      함수 이름 `end_or_iterate`는 두 결과(e=end / i=iterate) 강조.

    라벨: outline §3.2 line 216 SSOT 형식 — `[User Synthesis · Turn {turn_id}]`.
    이어서 reason 별도 라인 (`reason: <reason>`).

    reason 예:
        "Ctrl+F 트리거"
        "[CONVERGED] streak 2 도달"
        "max-turns 5 도달"

    분기:
        Y / y                        → ("e", None)  종료
        n / N                        → ("i", None)  지시 없이 한 턴 더
        c / C                        → ("c", None)  취소 (이어서 진행)
        그 외 텍스트                  → ("i", text) driver에 지시 전달 (원본 strip 보존)
        Enter (빈 입력)               → 재입력 안내 + retry. INVALID_RETRY_LIMIT 회 fail 시
                                       ("c", None) fallback (자연 진행 default, 비대화형 안전망)
        EOFError / KeyboardInterrupt → ("e", None) CI·파이프 abort

    `prompt_decision`과 분리 — Enter default 의미 정반대 (full 모드 = iterate vs
    critical 모드 잠재 prompt = end). 한 함수에 mode 분기 넣으면 default 의미 모호.

    호출 시점: orchestrator.run_session critical 모드, with TriggerListener 블록
    종료 (cleanup) 직후. canonical mode 회복 상태이므로 input() 정상 동작 (P-RAW 정합).

    호출자: orchestrator.run_session critical 모드 (Phase D wiring).
    """
    label = f"[User Synthesis · Turn {turn_id}]"
    # 옵션 분기:
    #   trigger 단독 (allow_continue=True, allow_iterate_no_directive=False) → Y/c/텍스트
    #   CONVERGED/last_turn (allow_continue=False, allow_iterate_no_directive=True) → Y/n/텍스트
    #   둘 다 (default) → Y/n/c/텍스트
    options_parts = ["Y=종료"]
    valid_keys_parts = ["Y"]
    if allow_iterate_no_directive:
        options_parts.append("n=지시 없이 한 턴 더")
        valid_keys_parts.append("n")
    if allow_continue:
        options_parts.append("c=취소 (이어서 진행)")
        valid_keys_parts.append("c")
    options_parts.append("텍스트=driver에 지시 전달")
    valid_keys_parts.append("텍스트")
    options_narrative = ", ".join(options_parts)
    valid_keys = " / ".join(valid_keys_parts)
    invalid = 0
    while invalid < INVALID_RETRY_LIMIT:
        try:
            print(label, file=sys.stderr)
            print(f"reason: {reason}", file=sys.stderr)
            print(options_narrative, file=sys.stderr)
            sys.stdout.write("> ")
            sys.stdout.flush()
            raw = _read_line_for_prompt()
        except (EOFError, KeyboardInterrupt):
            return ("e", None)
        text = raw.strip()
        if text == "":
            invalid += 1
            print(f"{valid_keys} 중 하나를 입력해주세요.", file=sys.stderr)
            continue
        if text.lower() == "y":
            return ("e", None)
        if text.lower() == "n":
            if allow_iterate_no_directive:
                return ("i", None)
            invalid += 1
            print(
                "n 사용 불가 (trigger 시점) — 텍스트로 driver에 지시 전달.",
                file=sys.stderr,
            )
            continue
        if text.lower() == "c":
            if allow_continue:
                return ("c", None)
            invalid += 1
            print(
                "c 사용 불가 (자연 종료 시점) — Y 또는 텍스트.",
                file=sys.stderr,
            )
            continue
        return ("i", text)
    # 한계 fallback —
    #   allow_continue=True (trigger): c (자연 진행)
    #   allow_continue=False (CONVERGED/last_turn): e (자연 종료 정합)
    if allow_continue:
        print("유효 입력 없음 — 자동으로 '취소 (이어서 진행)' 적용.", file=sys.stderr)
        return ("c", None)
    print("유효 입력 없음 — 자동으로 '종료' 적용.", file=sys.stderr)
    return ("e", None)


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


class TriggerListener:
    """Ctrl+F (chr(0x06)) 단일 byte 비동기 listener.

    Spinner와 동일 패턴 (isatty 가드, threading.Thread daemon, threading.Event).
    POSIX termios raw mode → listener thread fd 한정. main thread stdout/stderr 영향 X.
    Windows native cmd는 termios import 실패 → no-op fallback (self._enabled=False).

    cleanup-restart 패턴: __exit__ 시 thread.join + tcsetattr 복원 → 매 턴 끝
    `with TriggerListener() as trigger:` 블록 종료 → main thread `prompt_end_or_iterate`
    호출 (canonical mode 회복) → 다음 턴 진입 시 새 인스턴스 `with`. fd 동시 점유 0
    (P-RAW R5 차단). 비용 ms 단위, 사용자 인지 0.

    컨텍스트 매니저 사용 (한 턴 단위):
        for turn in ...:
            with TriggerListener() as trigger:
                run_turn(...)
                if trigger.is_set() or converged:
                    pass  # block exit → cleanup
            # 여기서 prompt_end_or_iterate (canonical mode)

    __enter__: stderr 안내 1줄 + thread.start(). isatty=False면 no-op
    __exit__: stop event set + thread.join(timeout=THREAD_JOIN_TIMEOUT_S)
              + try/finally tcsetattr 복원 (R3 안전망 필수)
    """

    TRIGGER_BYTE: int = 0x06  # Ctrl+F (paste — 변형 금지, Linux ASCII control char)
    # 사용자 환경 (WSL2 PTY)에서 첫 누름 byte race로 1회 단발 인식 어려움 — Ctrl+T로
    # 변경 시도했으나 동일 결함. 환경 특성으로 받아들임. 사용자 narrative: "2회 연타"
    # 안내. listener thread는 자체 polling 0.1s + 사전 누름 회수 path도 race 잔존.

    def __init__(self) -> None:
        self._triggered = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._old_attrs: list | None = None
        self._fd: int = -1
        # self-pipe — pause/__exit__ 시 select 즉시 깨움 (cycle 0.1s 안 byte 절도 차단).
        self._wake_r: int = -1
        self._wake_w: int = -1
        # plan 015 채택 ① — listener thread가 절도한 byte를 thread-safe queue에 보존.
        # __exit__ 시 drain + discard로 main thread readline 진입 전 깨끗한 상태 보장
        # (forward 시 stdin readline에 listener가 잠시 가져갔던 사용자 'y' prefix 누수 차단).
        self._byte_queue: queue.Queue[bytes] = queue.Queue(maxsize=1024)
        isatty = bool(getattr(sys.stderr, "isatty", lambda: False)())
        self._enabled = isatty and termios is not None

    def is_set(self) -> bool:
        """트리거 발생 여부 (threading.Event proxy)."""
        return self._triggered.is_set()

    def _run(self) -> None:
        """listener thread body — tty.setcbreak + select fd-level + os.read byte 단위.

        select에 self._fd 직접 + os.read(fd, 1) byte 단위 — sys.stdin TextIOWrapper
        buffer 우회 (Python text mode + fd-level select 불일치 회피, P-RAW 정공법.
        stdin_canonical_off:209-287 동일 패턴).
        select timeout=0.1로 self._stop polling. tty.setcbreak는 fd 한정 raw 효과 —
        main thread stdout/stderr 출력에 영향 X. 실패 silent return.
        """
        try:
            # setcbreak default `when=TCSAFLUSH` — input queue drain 후 raw mode 적용 →
            # setcbreak 호출 직전 사용자가 누른 byte 손실 (사용자 narrative: "Ctrl+F 2번
            # 눌러야지만 반영" — 첫 byte가 setcbreak TCSAFLUSH drain으로 폐기, 두 번째
            # byte만 raw mode 적용 후 인식). when=TCSANOW로 변경 — 즉시 적용 + buffer 보존.
            if termios is None:
                return
            tty.setcbreak(self._fd, when=termios.TCSANOW)
        except Exception:
            # OSError, termios.error 둘 다 silent — termios.error는 OSError 하위 X.
            return
        while not self._stop.is_set():
            # self-pipe로 stop 신호 즉시 감지 — pause/__exit__ 호출 시 select 즉시 깨움.
            # cycle timeout 0.1s 그대로지만 self._wake_r에 byte 들어오면 즉시 ready.
            watch_fds = [self._fd]
            if self._wake_r >= 0:
                watch_fds.append(self._wake_r)
            try:
                ready, _, _ = select.select(watch_fds, [], [], 0.1)
            except (OSError, ValueError):
                return
            if not ready:
                continue
            # stop 신호 우선 검사 — self._wake_r ready 시 즉시 종료 (사용자 byte 절도 차단).
            if self._wake_r in ready or self._stop.is_set():
                return
            try:
                ch_bytes = os.read(self._fd, 1)
            except (OSError, ValueError):
                return
            if not ch_bytes:
                # EOF — PTY closed. busy loop 차단 위해 즉시 종료 (C-013, P-RAW).
                return
            # plan 015 채택 ① — 절도한 모든 byte를 queue에 보존. __exit__가 drain +
            # discard로 정리 → main thread readline 진입 전 깨끗한 상태 보장.
            try:
                self._byte_queue.put_nowait(ch_bytes)
            except queue.Full:
                pass
            if ch_bytes[0] == self.TRIGGER_BYTE:
                # 이미 trigger 상태 — 같은 턴 안 추가 누름 (driver/reviewer 순서 모두 누른 경우).
                # 사용자가 trigger 인식 못 한 채 또 누른 시나리오 — 안내로 인식 보장.
                if self._triggered.is_set():
                    try:
                        sys.stderr.write(
                            "\n[i] 이미 트리거 set — 이번 턴 종료 후 입력 가능 "
                            "(추가 Ctrl+F 무시)\n"
                        )
                        sys.stderr.flush()
                    except Exception:
                        pass
                    continue
                # 첫 trigger — 즉시 피드백 + thread loop 계속 (추가 누름 안내 가능).
                # spinner와 충돌 회피 위해 \n 명시 (별도 라인 출력 — spinner는 위 라인 유지).
                self._triggered.set()
                try:
                    sys.stderr.write(
                        "\n[i] 사용자 트리거 발동 — 이번 턴 종료 후 입력 가능\n"
                    )
                    sys.stderr.flush()
                except Exception:
                    pass
                # return 폐기 — loop 계속 (자명한 동작: 같은 턴 추가 byte 0x06 안내).
                # thread 종료는 self._stop.set() (pause/exit) 또는 EOF만.

    def __enter__(self) -> "TriggerListener":
        if not self._enabled:
            return self
        try:
            self._fd = sys.stdin.fileno()
            self._old_attrs = termios.tcgetattr(self._fd)  # type: ignore[union-attr]
        except Exception:
            # tcgetattr 실패 (termios.error 포함) — silent no-op (P-RAW 견고성).
            # termios.error는 OSError 하위 클래스가 아니라 명시 catch — Exception 폭넓게.
            self._enabled = False
            return self
        # 사전 누름 byte 회수 — 사용자 narrative: "트리거 키 첫 누름 미인식".
        # listener __enter__ 직전·직후 사용자가 누른 byte가 fd queue에 잔존 가능
        # (line buffer canonical 또는 raw queue). setcbreak 즉시 진입 + non-blocking
        # drain으로 byte 확보 후 0x06 (Ctrl+F = TRIGGER_BYTE) 검사. 발견 시 trigger.set
        # — 첫 누름 보존.
        try:
            tty.setcbreak(self._fd, when=termios.TCSANOW)  # type: ignore[union-attr]
        except Exception:
            self._enabled = False
            return self
        try:
            flags = fcntl.fcntl(self._fd, fcntl.F_GETFL)
            fcntl.fcntl(self._fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            try:
                while True:
                    try:
                        data = os.read(self._fd, 4096)
                    except (BlockingIOError, OSError):
                        break
                    if not data:
                        break
                    if self.TRIGGER_BYTE in data and not self._triggered.is_set():
                        self._triggered.set()
                        try:
                            sys.stderr.write(
                                "\n[i] 사용자 트리거 발동 (사전 누름 인식) — "
                                "이번 턴 종료 후 입력 가능\n"
                            )
                            sys.stderr.flush()
                        except Exception:
                            pass
            finally:
                fcntl.fcntl(self._fd, fcntl.F_SETFL, flags)
        except Exception:
            pass
        # 사용자 안내는 단순 — 개발 narrative (WSL2 PTY 환경 특성, 1회 단발 인식 불안정,
        # listener thread polling 0.1s race) 등은 본 클래스 docstring + validation.md
        # P-RAW에 보존. 사용자에게는 동작 방법만.
        try:
            sys.stderr.write("[i] Ctrl+F 2회 연타 = 다음 턴 끝 개입 단계 진입\n")
            sys.stderr.flush()
        except Exception:
            pass
        # self-pipe pair 생성 — pause/__exit__ 시 select 즉시 깨움
        try:
            self._wake_r, self._wake_w = os.pipe()
        except Exception:
            self._wake_r = -1
            self._wake_w = -1
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        if not self._enabled:
            return
        # self-pipe wake — select 즉시 ready (cycle 안 byte 절도 차단)
        self._stop.set()
        if self._wake_w >= 0:
            try:
                os.write(self._wake_w, b"x")
            except Exception:
                pass
        try:
            if self._thread is not None:
                self._thread.join(timeout=THREAD_JOIN_TIMEOUT_S)
                # join timeout 시 listener thread가 백그라운드에서 stdin byte 절도 가능
                # (사용자 결함 환원: 사용자가 prompt에 'y' 입력해도 빈 줄로 처리되던
                # race). self._stop 한 번 더 set + 추가 wake + 추가 join으로 race 완화.
                if self._thread.is_alive():
                    if self._wake_w >= 0:
                        try:
                            os.write(self._wake_w, b"x")
                        except Exception:
                            pass
                    self._thread.join(timeout=THREAD_JOIN_TIMEOUT_S)
                    if self._thread.is_alive():
                        try:
                            sys.stderr.write(
                                "\n[!] listener thread join timeout — stdin byte 절도 "
                                "race 잔존 가능 (terminal reset 권고)\n"
                            )
                            sys.stderr.flush()
                        except Exception:
                            pass
        finally:
            # plan 015 채택 ① — listener queue 잔존 byte 폐기 (forward 시 stdin readline에
            # listener가 잠시 가져갔던 사용자 'y'·trigger 0x06 prefix 누수). thread join
            # 후 시점이라 race-free.
            while True:
                try:
                    self._byte_queue.get_nowait()
                except queue.Empty:
                    break
            # R3 안전망 — tcsetattr 복원은 thread join 실패해도 반드시 시도.
            # TCSAFLUSH (drain output queue + flush input queue + 즉시 적용) 사용 — TCSADRAIN은
            # drain 후 적용이라 prompt readline 호출 시점에 line discipline 정상화 보장 X
            # (사용자 보고 결함 환원: "Ctrl+F 후 Enter 여러 번 눌러야 prompt readline 반응" —
            # raw mode 잔존으로 사용자 byte가 line buffer 안 거치다가 일정 시간 후 자체 회복).
            if self._old_attrs is not None and termios is not None:
                try:
                    termios.tcsetattr(self._fd, termios.TCSAFLUSH, self._old_attrs)
                except Exception:
                    # OSError, termios.error 둘 다 silent — 사용자 terminal 복원 best-effort.
                    pass
                # canonical mode 복원 후 fd queue 잔재 byte drain — 사용자가 Ctrl+F 연타로
                # 누적시킨 0x06 byte들이 raw → canonical 전환 시 line buffer로 옮겨가
                # 다음 readline()이 "\x06\x06...\nc\n" 받음 → invalid retry 발생.
                # tcflush(TCIFLUSH) — kernel input queue 명시 drain.
                try:
                    termios.tcflush(self._fd, termios.TCIFLUSH)
                except Exception:
                    pass
            # self-pipe close
            if self._wake_r >= 0:
                try:
                    os.close(self._wake_r)
                except Exception:
                    pass
                self._wake_r = -1
            if self._wake_w >= 0:
                try:
                    os.close(self._wake_w)
                except Exception:
                    pass
                self._wake_w = -1



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
