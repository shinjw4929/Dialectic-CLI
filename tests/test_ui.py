"""ui.prompt_decision 4 케이스 — phase-a-ui.md §3.2 DoD 1:1."""

from __future__ import annotations

import builtins

import pytest

from src.ui import DECISION_KEYS, INVALID_RETRY_LIMIT, prompt_decision


from collections.abc import Callable, Iterable


def _input_seq(values: Iterable[str]) -> Callable[[str], str]:
    """builtins.input 대체 — 시퀀스 소진 후 EOFError raise."""
    it = iter(values)

    def fake(_prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return fake


def test_prompt_decision_six_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """a/r/m/i/e/s 6 키 모두 정확히 매핑."""
    for key in DECISION_KEYS:
        monkeypatch.setattr(builtins, "input", _input_seq([key]))
        result = prompt_decision(1, interactive_mode="end-only")
        assert result == (key, None), f"key={key!r} got {result!r}"


def test_prompt_decision_enter_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """빈 입력 → ('i', None) (outline/03-ux §3.3 default)."""
    monkeypatch.setattr(builtins, "input", _input_seq([""]))
    assert prompt_decision(2, interactive_mode="end-only") == ("i", None)


def test_prompt_decision_eof_returns_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """EOFError → ('e', None) — 파이프·CI 안전망."""

    def raise_eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)
    assert prompt_decision(3, interactive_mode="end-only") == ("e", None)


def test_prompt_decision_keyboard_interrupt_returns_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """KeyboardInterrupt → ('e', None) — Ctrl-C 안전망."""

    def raise_kbi(_prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", raise_kbi)
    assert prompt_decision(4, interactive_mode="end-only") == ("e", None)


def test_prompt_decision_invalid_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """잘못된 키 INVALID_RETRY_LIMIT(=3)회 → ('i', None) fallback."""
    bad_inputs = ["x", "z", "qq"]
    assert len(bad_inputs) == INVALID_RETRY_LIMIT
    monkeypatch.setattr(builtins, "input", _input_seq(bad_inputs))
    assert prompt_decision(5, interactive_mode="end-only") == ("i", None)


def test_flush_stdin_calls_tcflush_on_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """isatty=True → termios.tcflush(stdin, TCIFLUSH) 호출 + select 통한 drain loop.

    plan 008-ui-polish hot-fix: spinner 종료 직후 stdin 누수 차단 (Enter 입력이 다음
    `input(...)` prompt를 즉시 소비해 단계 skip되는 UX 결함 회귀 차단).
    """
    import select
    import sys
    import termios

    from src.ui import flush_stdin

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    called: list[tuple] = []
    monkeypatch.setattr(termios, "tcflush", lambda fd, queue: called.append((fd, queue)))
    # select.select가 빈 ready 반환 → drain loop 즉시 break (실제 os.read 회피)
    monkeypatch.setattr(select, "select", lambda r, w, x, t: ([], [], []))

    flush_stdin()

    assert len(called) == 1
    assert called[0][1] == termios.TCIFLUSH


def test_flush_stdin_skips_when_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """isatty=False → tcflush 호출 X (CI/파이프 silent skip)."""
    import sys
    import termios

    from src.ui import flush_stdin

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    called: list[tuple] = []
    monkeypatch.setattr(termios, "tcflush", lambda fd, queue: called.append((fd, queue)))

    flush_stdin()

    assert called == []


def test_stdin_canonical_off_disables_and_restores(monkeypatch: pytest.MonkeyPatch) -> None:
    """isatty=True → tcgetattr 캐시 + tcsetattr 2회 (off + restore) + tcflush 1회.

    plan 008-ui-polish hot-fix: spinner 동안 사용자 Enter가 line buffer로 완성되어
    다음 input()에 누수되는 root cause 차단 (canonical mode + ECHO off + 종료 시 복원).
    drain thread는 select.select mock으로 즉시 break — 실제 stdin fd 0 polling 회피
    (CI flaky 차단).
    """
    import select
    import sys
    import termios

    from src.ui import stdin_canonical_off

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)

    original_lflag = termios.ICANON | termios.ECHO | termios.ISIG
    fake_attrs = [0, 0, 0, original_lflag, 0, 0, [0] * 32]
    monkeypatch.setattr(termios, "tcgetattr", lambda fd: list(fake_attrs))

    set_calls: list = []
    flush_calls: list = []
    monkeypatch.setattr(termios, "tcsetattr", lambda fd, when, attrs: set_calls.append(list(attrs)))
    monkeypatch.setattr(termios, "tcflush", lambda fd, queue: flush_calls.append(queue))
    # drain thread가 실제 fd 0에 select 안 하도록 — 빈 ready 반환 후 stop_event 감지로 break
    monkeypatch.setattr(select, "select", lambda r, w, x, t: ([], [], []))

    with stdin_canonical_off():
        # body 내부 — first tcsetattr는 ICANON·ECHO off로 호출됐어야 함
        assert len(set_calls) == 1
        new_lflag = set_calls[0][3]
        assert not (new_lflag & termios.ICANON)
        assert not (new_lflag & termios.ECHO)
        assert new_lflag & termios.ISIG  # ISIG는 보존 (Ctrl-C 작동)

    # exit — restore + flush
    assert len(set_calls) == 2
    restored_lflag = set_calls[1][3]
    assert restored_lflag == original_lflag
    assert flush_calls == [termios.TCIFLUSH]


def test_stdin_utf8_mode_sets_iutf8_iflag(monkeypatch: pytest.MonkeyPatch) -> None:
    """isatty=True (Linux) → iflag에 IUTF8 비트 set + 종료 시 원래 iflag 복원.

    plan 008-ui-polish hot-fix: 한글 등 multi-byte Backspace 정상 처리 (P-RAW 인접).
    Python termios 빌드에 IUTF8 미노출 시 `_LINUX_IUTF8 = 0o040000` fallback.
    """
    import sys
    import termios

    from src.ui import _LINUX_IUTF8, stdin_utf8_mode

    if not sys.platform.startswith("linux"):
        pytest.skip("IUTF8 fallback은 Linux 한정")

    iutf8_bit = getattr(termios, "IUTF8", _LINUX_IUTF8)

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    fake_attrs = [0, 0, 0, 0, 0, 0, [0] * 32]  # iflag=0 (IUTF8 off)
    monkeypatch.setattr(termios, "tcgetattr", lambda fd: list(fake_attrs))
    set_calls: list = []
    monkeypatch.setattr(termios, "tcsetattr", lambda fd, when, attrs: set_calls.append(list(attrs)))

    with stdin_utf8_mode():
        # body 진입 — IUTF8 set
        assert len(set_calls) == 1
        assert set_calls[0][0] & iutf8_bit

    # exit — restore (iflag IUTF8 off)
    assert len(set_calls) == 2
    assert not (set_calls[1][0] & iutf8_bit)


def test_stdin_utf8_mode_skips_when_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """isatty=False → tcsetattr 호출 X."""
    import sys
    import termios

    from src.ui import stdin_utf8_mode

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    called: list = []
    monkeypatch.setattr(termios, "tcgetattr", lambda fd: called.append("get") or [0]*7)
    monkeypatch.setattr(termios, "tcsetattr", lambda *a: called.append("set"))

    with stdin_utf8_mode():
        pass

    assert called == []


def test_stdin_canonical_off_skips_when_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """isatty=False → termios 호출 0 (CI/파이프 silent yield)."""
    import sys
    import termios

    from src.ui import stdin_canonical_off

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    called: list = []
    monkeypatch.setattr(termios, "tcgetattr", lambda fd: called.append("get") or [0]*7)
    monkeypatch.setattr(termios, "tcsetattr", lambda *a: called.append("set"))
    monkeypatch.setattr(termios, "tcflush", lambda *a: called.append("flush"))

    with stdin_canonical_off():
        pass

    assert called == []
