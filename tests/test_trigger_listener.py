"""ui.TriggerListener — phase-b-trigger-listener.md §5 DoD 1:1.

isatty silent / __exit__ cleanup (R3) / cleanup-restart round-trip / is_set 초기값.
실 호출 검증(R1: subprocess.run + Ctrl+F 입력)은 사용자 시연으로 미룸 — 본 단위
테스트는 monkeypatch isatty=True + termios.tcgetattr stub로 R3 안전망만 단언.
"""

from __future__ import annotations

import sys

import pytest

from src import ui
from src.ui import TriggerListener


def test_is_set_initial_false() -> None:
    """is_set 초기값 False — 인스턴스 생성 직후 트리거 미발생."""
    listener = TriggerListener()
    assert listener.is_set() is False


def test_isatty_false_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    """sys.stderr.isatty=False (CI/파이프) 환경에서 모든 메서드 no-op silent."""

    class _NotTTY:
        def isatty(self) -> bool:
            return False

        def write(self, _s: str) -> int:  # noqa: ARG002 — file-like stub
            return 0

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stderr", _NotTTY())

    listener = TriggerListener()
    assert listener._enabled is False  # noqa: SLF001 — silent path 검증
    with listener as t:
        # 가동 0 — thread 미생성, 트리거 false
        assert t._thread is None  # noqa: SLF001
        assert t.is_set() is False
    # __exit__ 후에도 트리거 false
    assert listener.is_set() is False


def test_exit_restores_attrs_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """R3 안전망 — `with TriggerListener(): raise` 후 tcsetattr 복원 보장.

    isatty=True 강제 + tcgetattr/tcsetattr stub로 attrs flow 검증. thread는
    started 상태이지만 self._stop.set() + join(timeout)으로 정리.
    """
    sentinel_attrs = ["sentinel-iflag", "etc"]
    set_calls: list[tuple[int, int, list]] = []

    class _FakeTTY:
        def isatty(self) -> bool:
            return True

        def write(self, _s: str) -> int:  # noqa: ARG002
            return 0

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stderr", _FakeTTY())
    # _run thread가 sys.stdin을 select하지 않도록 stub stdin도 격리.
    # (단, listener thread는 isatty=stderr 기반이라 stderr만 가짜면 충분.
    # _run 내부 select는 실 fd로 읽으나 self._stop.set 후 join 회수)

    fake_termios = type(ui.termios)("fake_termios")  # type: ignore[arg-type]

    def fake_tcgetattr(_fd: int) -> list:
        return list(sentinel_attrs)

    def fake_tcsetattr(fd: int, when: int, attrs: list) -> None:
        set_calls.append((fd, when, list(attrs)))

    fake_termios.tcgetattr = fake_tcgetattr
    fake_termios.tcsetattr = fake_tcsetattr
    fake_termios.TCSADRAIN = 1
    fake_termios.TCSAFLUSH = 2
    fake_termios.TCSANOW = 0  # __enter__ setcbreak when= 인자

    monkeypatch.setattr(ui, "termios", fake_termios)
    # tty.setcbreak: __enter__ 사전 누름 회수 path + _run thread 진입 시 둘 다 호출 가능.
    # keyword 인자 when= 받음 — fake는 *args/**kwargs 무시.
    monkeypatch.setattr(ui.tty, "setcbreak", lambda *_a, **_kw: None)
    # _run thread가 select에서 실 stdin 점유 안 하도록 select 즉시 timeout 반환
    monkeypatch.setattr(ui.select, "select", lambda *_a, **_kw: ([], [], []))
    # sys.stdin.fileno도 stub — 실 fd 사용하지 않도록
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    # __enter__ 사전 누름 회수 path: fcntl + os.read는 실 fd 0 호출 → BlockingIOError/OSError
    # try/except로 cover. fcntl은 module-level 그대로 (try/except가 잡음).

    with pytest.raises(RuntimeError, match="boom"):
        with TriggerListener():
            raise RuntimeError("boom")

    # tcsetattr이 진입 전 attrs로 복원 호출됐는지 (마지막 호출이 TCSAFLUSH 복원).
    # TCSADRAIN → TCSAFLUSH 변경 (사용자 결함 환원: drain 후 적용은 prompt readline 시점에
    # line discipline 정상화 보장 X. flush + 즉시 적용 보장).
    # __enter__ 사전 회수 path는 tcsetattr 호출 X (setcbreak이 tty 라이브러리 호출이지만
    # fake로 monkeypatch라 실 tcsetattr 호출 0). __exit__의 복원 호출만 set_calls에 등록.
    assert len(set_calls) >= 1
    last_call = set_calls[-1]
    assert last_call[1] == fake_termios.TCSAFLUSH
    assert last_call[2] == sentinel_attrs


def test_cleanup_restart_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    """cleanup-restart — `with TriggerListener(): pass` 두 번 연속 정상 동작.

    매번 진입 시 새 attrs 보존, __exit__ 시 복원. fd/thread 누수 0.
    """
    set_calls: list[tuple[int, int, list]] = []
    sentinel_attrs = ["round-trip-attrs"]

    class _FakeTTY:
        def isatty(self) -> bool:
            return True

        def write(self, _s: str) -> int:  # noqa: ARG002
            return 0

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stderr", _FakeTTY())

    fake_termios = type(ui.termios)("fake_termios2")  # type: ignore[arg-type]
    fake_termios.tcgetattr = lambda _fd: list(sentinel_attrs)
    fake_termios.tcsetattr = lambda fd, when, attrs: set_calls.append((fd, when, list(attrs)))
    fake_termios.TCSADRAIN = 1
    fake_termios.TCSAFLUSH = 2
    fake_termios.TCSANOW = 0

    monkeypatch.setattr(ui, "termios", fake_termios)
    monkeypatch.setattr(ui.tty, "setcbreak", lambda *_a, **_kw: None)
    monkeypatch.setattr(ui.select, "select", lambda *_a, **_kw: ([], [], []))
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)

    # 1차 round
    with TriggerListener() as t1:
        assert t1._enabled is True  # noqa: SLF001
    # 2차 round (새 인스턴스)
    with TriggerListener() as t2:
        assert t2._enabled is True  # noqa: SLF001

    # 매 round 마다 tcsetattr 복원 호출 (2회 이상)
    assert len(set_calls) >= 2
    for call in set_calls:
        assert call[2] == sentinel_attrs


def test_termios_unavailable_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    """termios is None (Windows native cmd) 환경 → self._enabled=False, no-op."""

    class _FakeTTY:
        def isatty(self) -> bool:
            return True

        def write(self, _s: str) -> int:  # noqa: ARG002
            return 0

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stderr", _FakeTTY())
    monkeypatch.setattr(ui, "termios", None)

    listener = TriggerListener()
    assert listener._enabled is False  # noqa: SLF001
    with listener as t:
        assert t.is_set() is False
        assert t._thread is None  # noqa: SLF001
