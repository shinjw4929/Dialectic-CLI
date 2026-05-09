"""Phase B — CLI default 메뉴 진입 단위 테스트.

`src/cli.py:_interactive_menu` EOFError/empty/KeyboardInterrupt 안전 종료 단언.
plan/006-ui/phase-b-cli-menu.md §3.2 / §6 엣지케이스 정합.
"""

from __future__ import annotations

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

    monkeypatch.setattr(cli, "_readline_input", _raise_eof)
    rc = cli._interactive_menu()
    assert rc == 0
    out = capsys.readouterr().out
    assert "환경 점검" in out
    assert "Traceback" not in out


def test_interactive_menu_empty_task_retries_until_eof(monkeypatch, capsys, stub_check_env):
    """빈 task 입력 → 종료 X, 재입력 안내 + retry. EOF로만 종료 (Ctrl-C 패턴 동치).

    plan 008-ui-polish hot-fix: 빈 task = 종료가 아닌 retry. Ctrl-C/EOF만 안전 종료.
    """
    inputs = iter(["   ", "", "  \t  "])  # 3회 빈 입력 후 EOF (StopIteration → EOFError)

    def _seq(prompt: str = "") -> str:
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(cli, "_readline_input", _seq)
    called = {"hit": False}
    def _no_call(_args):
        called["hit"] = True
        return 99

    monkeypatch.setattr(cli.orchestrator, "run_session", _no_call)
    rc = cli._interactive_menu()
    assert rc == 0
    assert called["hit"] is False
    out = capsys.readouterr().out
    # 빈 입력 안내가 1회 이상 (3회 retry 중 최소 1회 — strip 후 빈 자리)
    assert "다시 입력하거나" in out


def test_interactive_menu_keyboard_interrupt(monkeypatch, capsys, stub_check_env):
    """KeyboardInterrupt → return 0 안전 종료 (Ctrl-C 시나리오)."""
    def _raise_kbi(prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_readline_input", _raise_kbi)
    rc = cli._interactive_menu()
    assert rc == 0
    out = capsys.readouterr().out
    assert "Traceback" not in out


def test_interactive_menu_task_dispatches_run_session(monkeypatch, stub_check_env):
    """task 입력 → max-turns 빈 입력(default 1) → confirm 빈(Y default) → run_session 호출.

    Namespace max_turns=1 (default), 다른 필드는 default 매핑 정합.
    """
    inputs = iter(["demo task", "", ""])  # task → max-turns(default) → confirm(Y default)
    monkeypatch.setattr(cli, "_readline_input", lambda prompt="": next(inputs))

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
    assert args.interactive == "critical"  # plan 009 Phase A: 메뉴 default 변경
    assert args.workdir is None


def test_interactive_menu_max_turns_custom(monkeypatch, stub_check_env):
    """max-turns 명시 입력 '5' → Namespace.max_turns=5로 dispatch."""
    inputs = iter(["demo task", "5", ""])  # task → max-turns 5 → confirm Y
    monkeypatch.setattr(cli, "_readline_input", lambda prompt="": next(inputs))

    captured = {}
    def _capture(a):
        captured["args"] = a
        return 0
    monkeypatch.setattr(cli.orchestrator, "run_session", _capture)
    rc = cli._interactive_menu()
    assert rc == 0
    assert captured["args"].max_turns == 5


def test_interactive_menu_max_turns_invalid_retries(monkeypatch, capsys, stub_check_env):
    """max-turns 비정수/음수 입력 → retry. 빈 입력 fallback default 1."""
    inputs = iter(["demo task", "abc", "0", "", ""])  # task → invalid → 0 → 빈(1) → confirm Y
    monkeypatch.setattr(cli, "_readline_input", lambda prompt="": next(inputs))

    captured = {}
    def _capture(a):
        captured["args"] = a
        return 0
    monkeypatch.setattr(cli.orchestrator, "run_session", _capture)
    rc = cli._interactive_menu()
    assert rc == 0
    assert captured["args"].max_turns == 1
    out = capsys.readouterr().out
    assert "정수 필요" in out
    assert "양수 필요" in out


def test_interactive_menu_task_prompt_shows_example(monkeypatch, capsys, stub_check_env):
    """task input 단계 진입 전 example 안내가 stdout에 출력 (회귀 차단).

    plan 008-ui-polish hot-fix: prompt 자체는 짧게 ('task> ', readline wide-char 결함 차단),
    example·도움말 안내는 별도 print 라인. capsys.out에 'example' substring 단언.
    """
    def _raise_eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(cli, "_readline_input", _raise_eof)
    rc = cli._interactive_menu()
    assert rc == 0
    out = capsys.readouterr().out
    assert "다익스트라" in out
    assert "도움말" in out


def test_interactive_menu_confirm_n_retries_task_input(monkeypatch, capsys, stub_check_env):
    """진행 확인 'n' → task 재입력 (outer 루프 continue). 빈 task도 retry. EOF로 종료.

    plan 008-ui-polish hot-fix: 'n' 거부 = 전체 종료가 아닌 task 재입력. 빈 task도
    재요청. Ctrl-C/EOF만 안전 종료.
    """
    # task → max-turns(default 1) → confirm n → 빈 task retry → EOFError 종료
    inputs = iter(["test task", "", "n", ""])

    def _seq(prompt: str = "") -> str:
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(cli, "_readline_input", _seq)
    called = {"hit": False}
    def _no_call(_args):
        called["hit"] = True
        return 99

    monkeypatch.setattr(cli.orchestrator, "run_session", _no_call)
    rc = cli._interactive_menu()
    assert rc == 0
    assert called["hit"] is False
    out = capsys.readouterr().out
    assert "취소" in out
    assert "task 재입력" in out
    # 빈 task 재요청 안내 (confirm n → outer continue → 빈 task → 재요청)
    assert "다시 입력하거나" in out


def test_interactive_menu_help_key_retries(monkeypatch, capsys, stub_check_env):
    """task input '?' → 도움말 출력 + retry. 빈 입력도 retry. EOF로 종료."""
    inputs = iter(["?", ""])  # ? → 도움말 retry, 빈 → 재요청 retry, StopIteration → EOFError 종료

    def _seq(prompt: str = "") -> str:
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(cli, "_readline_input", _seq)
    called = {"hit": False}
    def _no_call(_args):
        called["hit"] = True
        return 99

    monkeypatch.setattr(cli.orchestrator, "run_session", _no_call)
    rc = cli._interactive_menu()
    assert rc == 0
    assert called["hit"] is False
    out = capsys.readouterr().out
    assert "도움말" in out
    assert "다시 입력하거나" in out
