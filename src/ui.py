"""사용자 개입 UI — 6지선다 + directive + spinner.

outline/03-ux.md §3.3 SSOT 키 매핑 (a/r/m/i/e/s).
Enter = iterate + empty directive (default UX).
EOF/KeyboardInterrupt = end (비대화형 환경 안전망).
"""

from __future__ import annotations

import sys
import threading

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
            if self._stop.wait(0.1):
                break
        try:
            sys.stderr.write("\r" + " " * (len(self._message) + 2) + "\r")
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
            self._thread.join(timeout=1)
