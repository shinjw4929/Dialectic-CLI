"""ui.prompt_decision 4 케이스 — phase-a-ui.md §3.2 DoD 1:1."""

from __future__ import annotations

import builtins

from src.ui import DECISION_KEYS, INVALID_RETRY_LIMIT, prompt_decision


def _input_seq(values):
    """builtins.input 대체 — 시퀀스 소진 후 EOFError raise."""
    it = iter(values)

    def fake(_prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return fake


def test_prompt_decision_six_keys(monkeypatch):
    """a/r/m/i/e/s 6 키 모두 정확히 매핑."""
    for key in DECISION_KEYS:
        monkeypatch.setattr(builtins, "input", _input_seq([key]))
        result = prompt_decision(1, interactive_mode="end-only")
        assert result == (key, None), f"key={key!r} got {result!r}"


def test_prompt_decision_enter_default(monkeypatch):
    """빈 입력 → ('i', None) (outline/03-ux §3.3 default)."""
    monkeypatch.setattr(builtins, "input", _input_seq([""]))
    assert prompt_decision(2, interactive_mode="end-only") == ("i", None)


def test_prompt_decision_eof_returns_end(monkeypatch):
    """EOFError → ('e', None) — 파이프·CI 안전망."""

    def raise_eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)
    assert prompt_decision(3, interactive_mode="end-only") == ("e", None)


def test_prompt_decision_keyboard_interrupt_returns_end(monkeypatch):
    """KeyboardInterrupt → ('e', None) — Ctrl-C 안전망."""

    def raise_kbi(_prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", raise_kbi)
    assert prompt_decision(4, interactive_mode="end-only") == ("e", None)


def test_prompt_decision_invalid_retry(monkeypatch):
    """잘못된 키 INVALID_RETRY_LIMIT(=3)회 → ('i', None) fallback."""
    bad_inputs = ["x", "z", "qq"]
    assert len(bad_inputs) == INVALID_RETRY_LIMIT
    monkeypatch.setattr(builtins, "input", _input_seq(bad_inputs))
    assert prompt_decision(5, interactive_mode="end-only") == ("i", None)
