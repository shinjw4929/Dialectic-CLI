"""_detect_converged() + ADR-9 fallback warning 단위 테스트.

phase-d §3.3b 명세 — outline/02 §2.9 [CONVERGED] 마커 + ADR-9 K fallback.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.orchestrator import _detect_converged


# ---------------------------------------------------------------------------- #
# _detect_converged 4 케이스
# ---------------------------------------------------------------------------- #

def test_detect_converged_marker_alone_last_line():
    assert _detect_converged("Some critique\n[CONVERGED]") is True
    assert _detect_converged("Some critique\n[CONVERGED]\n") is True
    assert _detect_converged("Some critique\n[CONVERGED]  \n") is True


def test_detect_converged_marker_not_alone():
    assert _detect_converged("[CONVERGED] yes") is False
    assert _detect_converged("Some critique [CONVERGED]") is False
    assert _detect_converged("[CONVERGED]\nP1: more text") is False


def test_detect_converged_no_marker():
    assert _detect_converged("") is False
    assert _detect_converged("Some critique without marker") is False


# ---------------------------------------------------------------------------- #
# ADR-9 fallback warning — run_session
# ---------------------------------------------------------------------------- #

def _args(tmp_path, *, max_turns: int, k: int):
    return SimpleNamespace(
        workdir=str(tmp_path), task="x",
        driver="codex", reviewer="claude",
        max_turns=max_turns, mode="run",
        convergence_streak=k, interactive="end-only",
    )


def test_run_session_adr9_fallback_warning(monkeypatch, capsys, tmp_path):
    """K=2, max_turns=1 → stderr `K reduced to 1 (ADR-9, ...)` 등장."""
    from src import orchestrator

    # 어댑터 호출 막기 — run_turn no-op (fallback warning 검증이 목적).
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    # _resolve_runner도 무력화 (codex/claude CLI 부재 환경 대비).
    monkeypatch.setattr(
        orchestrator, "_resolve_runner",
        lambda name: SimpleNamespace(name=name, vendor="x"),
    )

    orchestrator.run_session(_args(tmp_path, max_turns=1, k=2))
    captured = capsys.readouterr()
    assert "K reduced to 1" in captured.err
    assert "ADR-9" in captured.err


def test_run_session_adr9_no_fallback_when_K_eq_1(monkeypatch, capsys, tmp_path):
    """K=1, max_turns=1 → fallback skip (K > 1 가드). stderr 메시지 부재."""
    from src import orchestrator

    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    monkeypatch.setattr(
        orchestrator, "_resolve_runner",
        lambda name: SimpleNamespace(name=name, vendor="x"),
    )

    orchestrator.run_session(_args(tmp_path, max_turns=1, k=1))
    captured = capsys.readouterr()
    assert "K reduced to 1" not in captured.err
