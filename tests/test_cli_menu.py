"""Phase B — CLI default 메뉴 진입 단위 테스트.

`src/cli.py:_interactive_menu` EOFError/empty/KeyboardInterrupt 안전 종료 단언.
plan/006-ui/phase-b-cli-menu.md §3.2 / §6 엣지케이스 정합.
"""

from __future__ import annotations

import builtins

import pytest

from src import cli


@pytest.fixture
def stub_check_env(monkeypatch):
    """env_check.check_env() 결과 stub — 활성 N/M 요약 출력 단계 통과용."""
    def _stub() -> dict:
        return {
            "claude": {
                "version": {"ok": True, "stdout": "v0", "stderr": ""},
                "auth": {"ok": False, "stdout": "", "stderr": ""},
            },
            "codex": {
                "version": {"ok": True, "stdout": "v0", "stderr": ""},
                "login": {"ok": False, "stdout": "", "stderr": ""},
            },
        }
    monkeypatch.setattr(cli, "check_env", _stub)


def test_interactive_menu_eof_exits_zero(monkeypatch, capsys, stub_check_env):
    """input() EOFError raise → _interactive_menu return 0 + traceback 노출 X."""
    def _raise_eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(builtins, "input", _raise_eof)
    rc = cli._interactive_menu()
    assert rc == 0
    out = capsys.readouterr().out
    assert "환경 점검" in out
    assert "Traceback" not in out


def test_interactive_menu_empty_task_exits(monkeypatch, capsys, stub_check_env):
    """빈 task 입력 → return 0 ('task 비어 있음' 메시지 + run_session 호출 X)."""
    monkeypatch.setattr(builtins, "input", lambda prompt="": "   ")  # whitespace만

    called = {"hit": False}
    def _no_call(_args):
        called["hit"] = True
        return 99

    monkeypatch.setattr(cli.orchestrator, "run_session", _no_call)
    rc = cli._interactive_menu()
    assert rc == 0
    assert called["hit"] is False
    out = capsys.readouterr().out
    assert "task 비어 있음" in out


def test_interactive_menu_keyboard_interrupt(monkeypatch, capsys, stub_check_env):
    """KeyboardInterrupt → return 0 안전 종료 (Ctrl-C 시나리오)."""
    def _raise_kbi(prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", _raise_kbi)
    rc = cli._interactive_menu()
    assert rc == 0
    out = capsys.readouterr().out
    assert "Traceback" not in out


def test_interactive_menu_task_dispatches_run_session(monkeypatch, stub_check_env):
    """task 입력 시 default 매핑으로 orchestrator.run_session 호출 + Namespace 정합."""
    monkeypatch.setattr(builtins, "input", lambda prompt="": "demo task")

    captured = {}
    def _capture(args):
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli.orchestrator, "run_session", _capture)
    rc = cli._interactive_menu()
    assert rc == 0
    args = captured["args"]
    assert args.cmd == "run"
    assert args.task == "demo task"
    assert args.driver == "codex"
    assert args.reviewer == "claude"
    assert args.max_turns == 1
    assert args.mode == "run"
    assert args.convergence_streak == 2
    assert args.interactive == "end-only"
    assert args.workdir is None
