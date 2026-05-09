"""orchestrator critical/full mode wiring + 시그니처 확장 + helper 단위 테스트.

phase-d §5 검증 매트릭스 — 초기 가드 + mock fallback + 3 mode × 종료 분기 + helper.
회귀 0: end-only AS-IS + `_serialize_history`/`build_prompt`/`run_turn` default 호출.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src import orchestrator
from src.orchestrator import (
    MAX_TURNS_HARD_CAP,
    META_DECISION_SEQ,
    _decision_msg,
    _last_critique_msg_id,
    _last_proposal_msg_id,
    _serialize_history,
    build_prompt,
)
from src.schema import Message, Meta


# ---------------------------------------------------------------------------- #
# 공통 헬퍼
# ---------------------------------------------------------------------------- #

def _meta(workdir: Path = Path("/tmp")) -> Meta:
    return Meta(
        vendor="user", agent_cli="user", model=None,
        session_id=None, thread_id=None,
        input_tokens=0, output_tokens=0,
        cached_input_tokens=0, reasoning_output_tokens=0,
        cost_usd=None, latency_ms=0,
        is_mock=False, workdir=str(workdir),
    )


def _msg(turn_id: int, kind: str, *, seq: int = 1, content: str = "x") -> Message:
    return Message(
        ts="2026-05-09T00:00:00.000Z",
        msg_id=str(uuid4()),
        parent_id=None,
        turn_id=turn_id, seq_in_turn=seq,
        from_="implementer" if kind == "proposal"
              else "spec-reviewer" if kind == "critique" else "user",
        to="broadcast", slot=None, mode="run",
        kind=kind, content=content, directive=None,
        meta=_meta(),
    )


def _args(tmp_path, *, interactive: str, max_turns: int = 1, k: int = 1):
    return SimpleNamespace(
        workdir=str(tmp_path), task="x",
        driver="codex", reviewer="claude",
        max_turns=max_turns, mode="run",
        convergence_streak=k, interactive=interactive,
    )


def _stub_runner(monkeypatch):
    monkeypatch.setattr(
        orchestrator, "_resolve_runner",
        lambda name: SimpleNamespace(name=name, vendor="x"),
    )


# ---------------------------------------------------------------------------- #
# 시그니처 확장 회귀 0 (default False 검증)
# ---------------------------------------------------------------------------- #

def test_serialize_history_default_unchanged():
    """exclude_reviewer 미지정 시 critique 포함 (회귀 0)."""
    history = [
        _msg(1, "proposal", seq=1, content="P1"),
        _msg(1, "critique", seq=2, content="C1"),
    ]
    out = _serialize_history(history)
    assert "P1" in out
    assert "C1" in out


def test_serialize_history_exclude_reviewer_filters_critique():
    """exclude_reviewer=True 시 critique 제외, proposal 포함."""
    history = [
        _msg(1, "proposal", seq=1, content="P1"),
        _msg(1, "critique", seq=2, content="C1"),
    ]
    out = _serialize_history(history, exclude_reviewer=True)
    assert "P1" in out
    assert "C1" not in out


def test_build_prompt_default_unchanged(tmp_path, monkeypatch):
    """build_prompt default exclude_reviewer=False — _serialize_history 그대로 호출."""
    captured = {}
    def fake_serialize(history, *, exclude_reviewer=False):
        captured["exclude_reviewer"] = exclude_reviewer
        return "<history>"
    monkeypatch.setattr(orchestrator, "_serialize_history", fake_serialize)
    # role.md 부재 회피 — read_text mock
    monkeypatch.setattr(
        Path, "read_text", lambda self, encoding="utf-8": "<role>",
    )
    build_prompt("implementer", "task", [], directive=None)
    assert captured["exclude_reviewer"] is False


def test_build_prompt_propagates_exclude_reviewer(monkeypatch):
    captured = {}
    def fake_serialize(history, *, exclude_reviewer=False):
        captured["exclude_reviewer"] = exclude_reviewer
        return "<history>"
    monkeypatch.setattr(orchestrator, "_serialize_history", fake_serialize)
    monkeypatch.setattr(
        Path, "read_text", lambda self, encoding="utf-8": "<role>",
    )
    build_prompt("implementer", "task", [], directive=None, exclude_reviewer=True)
    assert captured["exclude_reviewer"] is True


# ---------------------------------------------------------------------------- #
# helper 함수 단위 테스트
# ---------------------------------------------------------------------------- #

def test_decision_msg_fields():
    """_decision_msg는 seq=97 + from=user + to=implementer + kind=decision."""
    d = _decision_msg(
        turn_id=3, key="i", directive="추가 directive",
        workdir=Path("/tmp/wd"), mode="run", parent_id="parent-x",
    )
    assert d.kind == "decision"
    assert d.seq_in_turn == META_DECISION_SEQ == 97
    assert d.from_ == "user"
    assert d.to == "implementer"
    assert d.slot is None
    assert d.content == "i"
    assert d.directive == "추가 directive"
    assert d.parent_id == "parent-x"
    assert d.meta.vendor == "user"
    assert d.meta.agent_cli == "user"
    assert d.meta.is_mock is False
    assert d.meta.cost_usd is None


def test_last_critique_msg_id_fallback_none():
    """critique 부재 → None (full s 직후 같은 패턴)."""
    history = [_msg(1, "proposal")]
    assert _last_critique_msg_id(history) is None


def test_last_critique_msg_id_returns_latest():
    p1 = _msg(1, "proposal")
    c1 = _msg(1, "critique", seq=2)
    p2 = _msg(2, "proposal")
    c2 = _msg(2, "critique", seq=2)
    assert _last_critique_msg_id([p1, c1, p2, c2]) == c2.msg_id


def test_last_proposal_msg_id_returns_latest():
    p1 = _msg(1, "proposal")
    c1 = _msg(1, "critique", seq=2)
    p2 = _msg(2, "proposal")
    assert _last_proposal_msg_id([p1, c1, p2]) == p2.msg_id


# ---------------------------------------------------------------------------- #
# 초기 가드 (P1-ε)
# ---------------------------------------------------------------------------- #

def test_run_session_initial_max_turns_clamped(monkeypatch, capsys, tmp_path):
    """args.max_turns=25 → max_turns_runtime=20 + stderr clamp 메시지."""
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    args = _args(tmp_path, interactive="end-only", max_turns=25, k=1)
    orchestrator.run_session(args)
    captured = capsys.readouterr()
    assert f"> MAX_TURNS_HARD_CAP ({MAX_TURNS_HARD_CAP})" in captured.err
    assert "clamped" in captured.err


# ---------------------------------------------------------------------------- #
# end-only 회귀 (AS-IS)
# ---------------------------------------------------------------------------- #

def test_end_only_max_turns_reached(monkeypatch, tmp_path):
    """end-only AS-IS: 1턴 후 auto-end (max-turns reached) meta append."""
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    args = _args(tmp_path, interactive="end-only", max_turns=1, k=1)
    rc = orchestrator.run_session(args)
    assert rc == 0
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    assert "max-turns reached" in msgs


# ---------------------------------------------------------------------------- #
# critical mode
# ---------------------------------------------------------------------------- #

def test_critical_last_turn_user_end(monkeypatch, tmp_path):
    """critical max-turns 도달 시 prompt → e → auto_end_user."""
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    monkeypatch.setattr(
        orchestrator, "TriggerListener",
        lambda: _NoopCM(),
    )
    monkeypatch.setattr(
        orchestrator, "_setup_sigint_handler",
        lambda listener: signal.SIG_DFL,
    )
    monkeypatch.setattr(
        orchestrator, "prompt_end_or_iterate",
        lambda turn_id, reason, **_kw: ("e", None),
    )
    args = _args(tmp_path, interactive="critical", max_turns=1, k=1)
    rc = orchestrator.run_session(args)
    assert rc == 0
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    assert "auto_end_user" in msgs


def test_critical_iterate_extends_max_turns_runtime(monkeypatch, tmp_path):
    """critical i → max_turns_runtime += 1 → 추가 1턴 진행 (P1-새-1 동적 갱신 검증).

    args.max_turns=2, turn=2(last_turn) → i 응답 → max_turns_runtime=3 →
    turn=3 진행 → turn=3에서 다시 prompt → e 응답 → auto_end_user.
    run_turn 호출 횟수로 단언 (3회).
    """
    _stub_runner(monkeypatch)
    call_counter = {"n": 0}

    def fake_run_turn(*a, **kw):
        call_counter["n"] += 1

    monkeypatch.setattr(orchestrator, "run_turn", fake_run_turn)
    monkeypatch.setattr(orchestrator, "TriggerListener", lambda: _NoopCM())
    monkeypatch.setattr(
        orchestrator, "_setup_sigint_handler",
        lambda listener: signal.SIG_DFL,
    )

    # 첫 prompt(turn=2 last_turn) → ("i", None) → max_turns_runtime=3.
    # 두 번째 prompt(turn=3 새 last_turn) → ("e", None).
    responses = iter([("i", None), ("e", None)])
    monkeypatch.setattr(
        orchestrator, "prompt_end_or_iterate",
        lambda turn_id, reason, **_kw: next(responses),
    )

    args = _args(tmp_path, interactive="critical", max_turns=2, k=1)
    rc = orchestrator.run_session(args)
    assert rc == 0
    # turn=1, 2, 3 → 3회. (turn=1은 should_prompt False, turn=2 i, turn=3 e)
    assert call_counter["n"] == 3
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    # decision i 1번 + auto_end_user 1번
    assert msgs.count('"kind": "decision"') == 1
    assert "auto_end_user" in msgs


def test_critical_iterate_with_directive_text(monkeypatch, tmp_path):
    """critical text 입력 → ("i", text) → decision msg directive 보존."""
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator, "TriggerListener", lambda: _NoopCM())
    monkeypatch.setattr(
        orchestrator, "_setup_sigint_handler",
        lambda listener: signal.SIG_DFL,
    )
    responses = iter([("i", "더 자세히"), ("e", None)])
    monkeypatch.setattr(
        orchestrator, "prompt_end_or_iterate",
        lambda turn_id, reason, **_kw: next(responses),
    )
    args = _args(tmp_path, interactive="critical", max_turns=1, k=1)
    orchestrator.run_session(args)
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    assert "더 자세히" in msgs


def test_critical_hard_cap_auto_end(monkeypatch, tmp_path):
    """critical i 반복 → max_turns_runtime > HARD_CAP → auto_end_hard_cap.

    args.max_turns=20 (=HARD_CAP), 매 턴 last_turn에서 i → max_turns_runtime=21
    → hard_cap 초과 → auto_end_hard_cap 메시지.
    """
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    monkeypatch.setattr(orchestrator, "TriggerListener", lambda: _NoopCM())
    monkeypatch.setattr(
        orchestrator, "_setup_sigint_handler",
        lambda listener: signal.SIG_DFL,
    )
    monkeypatch.setattr(
        orchestrator, "prompt_end_or_iterate",
        lambda turn_id, reason, **_kw: ("i", None),
    )
    args = _args(tmp_path, interactive="critical", max_turns=20, k=1)
    rc = orchestrator.run_session(args)
    assert rc == 0
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    assert "auto_end_hard_cap" in msgs
    assert f"max_turns_runtime > {MAX_TURNS_HARD_CAP}" in msgs


# ---------------------------------------------------------------------------- #
# full mode
# ---------------------------------------------------------------------------- #

def test_full_a_branch_exclude_reviewer_history_next(monkeypatch, tmp_path):
    """full a → 다음 턴 run_turn에 exclude_reviewer_history=True 전달."""
    _stub_runner(monkeypatch)
    captured_kw = []

    def fake_run_turn(*a, **kw):
        captured_kw.append(kw)

    monkeypatch.setattr(orchestrator, "run_turn", fake_run_turn)
    responses = iter([("a", None), ("e", None)])
    monkeypatch.setattr(
        orchestrator, "prompt_decision",
        lambda turn_id, interactive_mode: next(responses),
    )
    args = _args(tmp_path, interactive="full", max_turns=2, k=1)
    orchestrator.run_session(args)
    # 첫 턴 default False, 둘째 턴 exclude_reviewer_history=True
    assert captured_kw[0]["exclude_reviewer_history"] is False
    assert captured_kw[0]["skip_reviewer"] is False
    assert captured_kw[1]["exclude_reviewer_history"] is True


def test_full_s_branch_skip_reviewer_next(monkeypatch, tmp_path):
    """full s → 다음 턴 run_turn에 skip_reviewer=True 전달."""
    _stub_runner(monkeypatch)
    captured_kw = []

    def fake_run_turn(*a, **kw):
        captured_kw.append(kw)

    monkeypatch.setattr(orchestrator, "run_turn", fake_run_turn)
    responses = iter([("s", None), ("e", None)])
    monkeypatch.setattr(
        orchestrator, "prompt_decision",
        lambda turn_id, interactive_mode: next(responses),
    )
    args = _args(tmp_path, interactive="full", max_turns=2, k=1)
    orchestrator.run_session(args)
    assert captured_kw[1]["skip_reviewer"] is True


def test_full_s_parent_id_uses_proposal_fallback(monkeypatch, tmp_path):
    """full s 직후 다음 턴 parent_id 결정 시 _last_proposal_msg_id 호출 단언
    (P1-새-2 dead code fix 검증).
    """
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)

    proposal_call_count = {"n": 0}
    real_last_proposal = orchestrator._last_proposal_msg_id

    def spy_last_proposal(history):
        proposal_call_count["n"] += 1
        return real_last_proposal(history)

    monkeypatch.setattr(orchestrator, "_last_proposal_msg_id", spy_last_proposal)
    responses = iter([("s", None), ("e", None)])
    monkeypatch.setattr(
        orchestrator, "prompt_decision",
        lambda turn_id, interactive_mode: next(responses),
    )
    args = _args(tmp_path, interactive="full", max_turns=2, k=1)
    orchestrator.run_session(args)
    # turn=2 진입 시 skip_reviewer_next=True였으므로 _last_proposal_msg_id 1회 호출.
    assert proposal_call_count["n"] >= 1


def test_full_r_branch_auto_inject_critique_when_empty(monkeypatch, tmp_path):
    """full r + raw_directive=None → critique[:200] 자동 주입."""
    _stub_runner(monkeypatch)

    # bus에 critique 메시지 미리 적재 (run_turn에서 실제 생성 대신).
    fake_critique_text = "이 응답은 제안의 X 부분이 누락되어 있어 보완 필요"

    def fake_run_turn(turn_id, mode, **kw):
        # bus에 critique 직접 append (driver 응답까지 가짜로 시뮬레이션).
        bus = kw["bus"]
        workdir = kw["workdir"]
        proposal = Message(
            ts=orchestrator._now_ts(),
            msg_id=str(uuid4()), parent_id=None,
            turn_id=turn_id, seq_in_turn=1,
            from_="implementer", to="broadcast", slot="driver", mode=mode,
            kind="proposal", content="prop", directive=None,
            meta=_meta(workdir),
        )
        bus.append(proposal)
        critique = Message(
            ts=orchestrator._now_ts(),
            msg_id=str(uuid4()), parent_id=proposal.msg_id,
            turn_id=turn_id, seq_in_turn=2,
            from_="spec-reviewer", to="broadcast", slot="reviewer", mode=mode,
            kind="critique", content=fake_critique_text, directive=None,
            meta=_meta(workdir),
        )
        bus.append(critique)

    monkeypatch.setattr(orchestrator, "run_turn", fake_run_turn)
    responses = iter([("r", None), ("e", None)])
    monkeypatch.setattr(
        orchestrator, "prompt_decision",
        lambda turn_id, interactive_mode: next(responses),
    )
    args = _args(tmp_path, interactive="full", max_turns=2, k=1)
    orchestrator.run_session(args)
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    assert "이전 턴 reviewer 비판 강조 채택:" in msgs
    assert fake_critique_text[:50] in msgs


def test_full_r_branch_user_input_priority(monkeypatch, tmp_path):
    """full r + raw_directive 사용자 입력 → 사용자 입력 우선 (critique 자동 주입 X)."""
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    responses = iter([("r", "사용자 직권"), ("e", None)])
    monkeypatch.setattr(
        orchestrator, "prompt_decision",
        lambda turn_id, interactive_mode: next(responses),
    )
    args = _args(tmp_path, interactive="full", max_turns=2, k=1)
    orchestrator.run_session(args)
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    assert "사용자 직권" in msgs
    assert "이전 턴 reviewer 비판 강조 채택:" not in msgs


def test_full_e_auto_end_user(monkeypatch, tmp_path):
    """full e → auto_end_user."""
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    monkeypatch.setattr(
        orchestrator, "prompt_decision",
        lambda turn_id, interactive_mode: ("e", None),
    )
    args = _args(tmp_path, interactive="full", max_turns=3, k=1)
    rc = orchestrator.run_session(args)
    assert rc == 0
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    assert "auto_end_user" in msgs


def test_full_i_hard_cap_auto_end(monkeypatch, tmp_path):
    """full i 반복 → max_turns_runtime > HARD_CAP → auto_end_hard_cap."""
    _stub_runner(monkeypatch)
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    monkeypatch.setattr(
        orchestrator, "prompt_decision",
        lambda turn_id, interactive_mode: ("i", None),
    )
    args = _args(tmp_path, interactive="full", max_turns=20, k=1)
    rc = orchestrator.run_session(args)
    assert rc == 0
    msgs = (tmp_path / "logs" / "messages.jsonl").read_text(encoding="utf-8")
    assert "auto_end_hard_cap" in msgs
    assert f"max_turns_runtime > {MAX_TURNS_HARD_CAP}" in msgs


# ---------------------------------------------------------------------------- #
# mock fallback narrative (현재 vacuous, plan 007 진입 후 활성)
# ---------------------------------------------------------------------------- #

def test_mock_critical_fallback_narrative(monkeypatch, capsys, tmp_path):
    """mock + critical → end-only 강제 + stderr fallback narrative.

    현재 _resolve_runner에 mock 미등록이라 ValueError raise 시점이지만, fallback
    분기 로직 자체는 args.interactive를 'end-only'로 강제 후 _resolve_runner 호출.
    fallback 메시지 stderr 등장 + interactive 변경 단언.
    """
    # _resolve_runner stub — mock도 받도록.
    monkeypatch.setattr(
        orchestrator, "_resolve_runner",
        lambda name: SimpleNamespace(name=name, vendor="x"),
    )
    monkeypatch.setattr(orchestrator, "run_turn", lambda *a, **kw: None)
    args = _args(tmp_path, interactive="critical", max_turns=1, k=1)
    args.driver = "mock"
    orchestrator.run_session(args)
    captured = capsys.readouterr()
    assert "mock 모드는 critical/full 비호환" in captured.err
    # interactive가 강제로 end-only로 변경되어 critical 분기 진입 X.
    assert args.interactive == "end-only"


# ---------------------------------------------------------------------------- #
# SIGINT 핸들러 단위 (raw mode 복원 + sys.exit(130))
# ---------------------------------------------------------------------------- #

def test_setup_sigint_handler_restores_raw_and_exits(monkeypatch):
    """_setup_sigint_handler 등록 후 SIGINT raise → listener.__exit__ + sys.exit(130).

    이전 핸들러 반환 후 직접 핸들러 함수 호출 (signal.signal 거치지 않고)로
    sys.exit + listener __exit__ 호출 단언.
    """
    exit_called = {"n": 0}
    listener_exit_called = {"n": 0}

    class FakeListener:
        def __exit__(self, *exc):
            listener_exit_called["n"] += 1

    def fake_exit(code):
        exit_called["code"] = code
        exit_called["n"] += 1
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", fake_exit)

    listener = FakeListener()
    prev = orchestrator._setup_sigint_handler(listener)  # type: ignore[arg-type]
    try:
        # 핸들러 직접 호출 (signal.raise_signal 대신 등록된 핸들러 retrieve).
        handler = signal.getsignal(signal.SIGINT)
        with pytest.raises(SystemExit) as exc_info:
            handler(signal.SIGINT, None)  # type: ignore[misc]
        assert exc_info.value.code == 130
        assert listener_exit_called["n"] == 1
        assert exit_called["code"] == 130
    finally:
        # 핸들러 복원 — 다른 테스트 격리.
        signal.signal(signal.SIGINT, prev)


# ---------------------------------------------------------------------------- #
# Helpers — 컨텍스트 매니저 stub
# ---------------------------------------------------------------------------- #

class _NoopCM:
    """TriggerListener stub — is_set() False, 컨텍스트 매니저 + pause/resume/clear no-op.

    plan 009 hot-fix round (사용자 narrative — Ctrl+F 인식 불안정 idle window):
    cleanup-restart 패턴 폐기 + session 단위 listener (pause/resume) 도입.
    stub은 모든 메서드 no-op로 회귀 보호.
    """

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def is_set(self):
        return False

    def pause(self):
        return None

    def resume(self):
        return None

    def clear(self):
        return None
