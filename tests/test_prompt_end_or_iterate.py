"""ui.prompt_end_or_iterate — phase-c-prompt-end-or-iterate.md §5 DoD 1:1.

Y/n/c/text/EOF/KBI 분기 + outline §3.2:216 라벨 SSOT 정합 회귀 보호.
prompt_end_or_iterate는 ui._read_line_for_prompt() 직접 사용 (사용자 결함 환원: input()
GNU readline lib + Python sys.stdin TextIOWrapper buffer race로 사용자 'y' 입력이 빈 줄로
처리되던 결함 fix — fd-level os.read로 buffer 우회).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest

from src import ui
from src.ui import prompt_end_or_iterate


def _line_seq(values: Iterable[str]) -> Callable[[], str]:
    """ui._read_line_for_prompt 대체 — 시퀀스 소진 후 EOFError raise.

    값은 trailing newline 없이 raw text (helper가 이미 strip 처리).
    """
    it = iter(values)

    def fake() -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return fake


def test_enter_retries_then_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    """빈 입력(Enter) → 재입력 안내. 다음 호출 EOF → ("e", None) 안전망."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq([""]))
    assert prompt_end_or_iterate(1, "Ctrl+F 트리거") == ("e", None)


def test_enter_retry_limit_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """빈 입력 INVALID_RETRY_LIMIT(3)회 → ("c", None) fallback."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["", "", ""]))
    assert prompt_end_or_iterate(1, "reason") == ("c", None)


def test_c_lower_and_upper_returns_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    """c / C → ("c", None) — 취소 (이어서 진행)."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["c"]))
    assert prompt_end_or_iterate(1, "reason") == ("c", None)
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["C"]))
    assert prompt_end_or_iterate(1, "reason") == ("c", None)


def test_y_lower_and_upper_returns_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """y / Y → ("e", None) (명시 종료)."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["y"]))
    assert prompt_end_or_iterate(1, "reason") == ("e", None)
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["Y"]))
    assert prompt_end_or_iterate(1, "reason") == ("e", None)
    # whitespace-only도 strip 후 빈 문자열 → retry path → EOF → end (안전망)
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["   "]))
    assert prompt_end_or_iterate(1, "reason") == ("e", None)


def test_n_lower_and_upper_returns_iterate_no_directive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """n / N → ("i", None) (allow_iterate_no_directive=True default)."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["n"]))
    assert prompt_end_or_iterate(2, "reason") == ("i", None)
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["N"]))
    assert prompt_end_or_iterate(2, "reason") == ("i", None)


def test_text_returns_iterate_with_directive(monkeypatch: pytest.MonkeyPatch) -> None:
    """그 외 텍스트 → ("i", text) directive 주입 (원본 strip 결과 보존)."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["추가로 X 구현해줘"]))
    assert prompt_end_or_iterate(1, "reason") == ("i", "추가로 X 구현해줘")
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["  hello world  "]))
    assert prompt_end_or_iterate(1, "reason") == ("i", "hello world")
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["e"]))
    assert prompt_end_or_iterate(1, "reason") == ("i", "e")


def test_eof_returns_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """EOFError → ("e", None) (CI·파이프 안전망)."""

    def raise_eof() -> str:
        raise EOFError

    monkeypatch.setattr(ui, "_read_line_for_prompt", raise_eof)
    assert prompt_end_or_iterate(1, "reason") == ("e", None)


def test_keyboard_interrupt_returns_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """KeyboardInterrupt → ("e", None) (Ctrl-C 안전망)."""

    def raise_kbi() -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(ui, "_read_line_for_prompt", raise_kbi)
    assert prompt_end_or_iterate(1, "reason") == ("e", None)


def test_label_format_outline_ssot(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """outline §3.2:216 SSOT 라벨 형식 stderr 출력."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["y"]))
    prompt_end_or_iterate(3, "[CONVERGED] streak 2 도달")
    captured = capsys.readouterr()
    assert "[User Synthesis · Turn 3]" in captured.err


def test_reason_appears_in_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """reason 문자열이 stderr에 정확히 포함."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["y"]))
    prompt_end_or_iterate(7, "Ctrl+F 트리거")
    captured = capsys.readouterr()
    assert "reason: Ctrl+F 트리거" in captured.err


def test_allow_continue_false_hides_c(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """allow_continue=False — c 옵션 미노출 + c 입력 시 invalid."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["c", "y"]))
    result = prompt_end_or_iterate(1, "[CONVERGED] streak 2 도달", allow_continue=False)
    assert result == ("e", None)
    captured = capsys.readouterr()
    assert "c=취소" not in captured.err


def test_allow_iterate_no_directive_false_hides_n(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """allow_iterate_no_directive=False (trigger only) — n 옵션 미노출 + n 입력 시 invalid."""
    monkeypatch.setattr(ui, "_read_line_for_prompt", _line_seq(["n", "c"]))
    result = prompt_end_or_iterate(
        1, "Ctrl+F 트리거",
        allow_continue=True,
        allow_iterate_no_directive=False,
    )
    assert result == ("c", None)
    captured = capsys.readouterr()
    assert "n=지시" not in captured.err
