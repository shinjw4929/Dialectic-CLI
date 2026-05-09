"""ui.print_message — phase-b-stdout.md §3.3 DoD 1:1.

3 케이스: proposal cyan / critique yellow / isatty=False no-ansi.
"""

from __future__ import annotations

import sys

from src.schema import Meta
from src.ui import ANSI_CYAN, ANSI_YELLOW, SEPARATOR, print_message


def _meta(latency_ms: int = 1500, output_tokens: int = 42, input_tokens: int = 100,
          cost_usd: float | None = 0.0123) -> Meta:
    return Meta(
        vendor="anthropic",
        agent_cli="claude",
        model=None,
        session_id=None,
        thread_id=None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=0,
        reasoning_output_tokens=0,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        is_mock=False,
        workdir="/tmp/x",
    )


def test_print_message_proposal_cyan_with_isatty(monkeypatch, capsys):
    """isatty=True 환경에서 kind=proposal → ANSI_CYAN 헤더 + SEPARATOR 3회 + 본문."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    print_message(
        role_label="구현자",
        vendor_label="Claude Code",
        kind="proposal",
        text="hello world",
        meta=_meta(),
    )
    out = capsys.readouterr().out
    assert out.count(SEPARATOR) == 3, f"SEPARATOR 3회 기대, got {out.count(SEPARATOR)}"
    assert "구현자" in out
    assert "Claude Code" in out
    assert ANSI_CYAN in out
    assert "hello world" in out


def test_print_message_critique_yellow(monkeypatch, capsys):
    """kind=critique → ANSI_YELLOW substring."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    print_message(
        role_label="코드 검토자",
        vendor_label="Codex CLI",
        kind="critique",
        text="critique body",
        meta=_meta(cost_usd=None),
    )
    out = capsys.readouterr().out
    assert ANSI_YELLOW in out
    assert "코드 검토자" in out
    assert "Codex CLI" in out
    assert "critique body" in out


def test_print_message_isatty_false_no_ansi(monkeypatch, capsys):
    """isatty=False 환경에서 ANSI escape 미포함. 출력 자체는 진행."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    print_message(
        role_label="구현자",
        vendor_label="Claude Code",
        kind="proposal",
        text="plain text",
        meta=_meta(),
    )
    out = capsys.readouterr().out
    assert "\x1b" not in out, f"ANSI escape 부재 기대, got {out!r}"
    assert "구현자" in out
    assert "plain text" in out
    assert SEPARATOR in out
