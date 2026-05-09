"""`dialectic logs` 서브커맨드 단위 테스트 — plan 010 Phase A.

§3.3 sub-checkbox 9건 1:1 cover.
"""

import argparse
import json
import time
from pathlib import Path

import pytest

from src.cli import _logs_entry
from src.logs import (
    _SESSION_TS_PATTERN,
    find_latest_session_dir,
    format_full,
    format_summary,
    render_logs,
    resolve_session_dir,
)


def _msg_dict(
    *, turn_id: int = 1, seq: int = 1, kind: str = "proposal",
    from_: str = "implementer", slot: str | None = "driver",
    content: str = "hello",
) -> dict:
    return {
        "ts": "2026-05-09T12:00:00.000Z",
        "msg_id": f"id-{turn_id}-{seq}",
        "parent_id": None,
        "turn_id": turn_id,
        "seq_in_turn": seq,
        "from": from_,
        "to": "broadcast",
        "slot": slot,
        "mode": "run",
        "kind": kind,
        "content": content,
        "directive": None,
        "meta": {
            "vendor": "mock", "agent_cli": "mock",
            "model": None, "session_id": None, "thread_id": None,
            "input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0,
            "reasoning_output_tokens": 0, "cost_usd": None, "latency_ms": 0,
            "is_mock": True, "workdir": "/tmp/x",
        },
    }


def _write_jsonl(path: Path, msgs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for m in msgs:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


# === format_summary / format_full ===

def test_format_summary_with_slot_none_prints_dash():
    msg = _msg_dict(turn_id=2, seq=3, kind="critique", from_="user", slot=None)
    out = format_summary(msg)
    assert out == "[turn=2 seq=3] kind=critique from=user slot=-"


def test_format_summary_with_slot_value():
    msg = _msg_dict(turn_id=1, seq=1, kind="proposal", from_="implementer", slot="driver")
    assert format_summary(msg) == "[turn=1 seq=1] kind=proposal from=implementer slot=driver"


def test_format_full_preserves_multiline_and_emits_separator():
    msg = _msg_dict(content="line1\nline2\nline3")
    out = format_full(msg)
    # summary 1줄 + content 3줄 + '---' 구분자 + 줄바꿈은 splitlines로 검증.
    lines = out.split("\n")
    assert lines[0] == format_summary(msg)
    assert lines[1] == "line1"
    assert lines[2] == "line2"
    assert lines[3] == "line3"
    assert lines[4] == "---"


# === render_logs(--tail / --kind / --full) ===

def test_render_logs_tail_n_emits_last_n_only(tmp_path, capsys):
    session = tmp_path / "20260509T120000Z"
    session.mkdir()
    msgs = [_msg_dict(turn_id=i, seq=1, content=f"m{i}") for i in range(1, 6)]
    _write_jsonl(session / "messages.jsonl", msgs)

    rc = render_logs(session_dir=session, tail=3, follow=False, kind_filter=None, full=False)
    assert rc == 0
    out_lines = capsys.readouterr().out.strip().split("\n")
    assert len(out_lines) == 3
    # 마지막 3개(turn 3,4,5)
    assert "turn=3" in out_lines[0]
    assert "turn=5" in out_lines[2]


def test_render_logs_kind_filter_with_full(tmp_path, capsys):
    session = tmp_path / "20260509T120100Z"
    session.mkdir()
    msgs = [
        _msg_dict(turn_id=1, seq=1, kind="proposal", content="P body"),
        _msg_dict(turn_id=1, seq=2, kind="critique", content="C body\nmulti"),
        _msg_dict(turn_id=1, seq=3, kind="decision", content="D body"),
    ]
    _write_jsonl(session / "messages.jsonl", msgs)

    rc = render_logs(
        session_dir=session, tail=None, follow=False,
        kind_filter="critique", full=True,
    )
    assert rc == 0
    captured = capsys.readouterr().out
    assert "kind=critique" in captured
    assert "C body" in captured
    assert "multi" in captured  # multiline 보존
    assert "---" in captured
    # 다른 kind는 제외
    assert "kind=proposal" not in captured
    assert "kind=decision" not in captured


def test_render_logs_malformed_line_skip_with_stderr(tmp_path, capsys):
    session = tmp_path / "20260509T120200Z"
    session.mkdir()
    path = session / "messages.jsonl"
    valid = json.dumps(_msg_dict(content="ok"), ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(valid + "\n")
        f.write("{this is not json\n")  # malformed
        f.write(valid + "\n")

    rc = render_logs(session_dir=session, tail=None, follow=False, kind_filter=None, full=False)
    assert rc == 0
    captured = capsys.readouterr()
    # stderr에 경고 1줄 + raw 보존 안내
    assert "JSONDecodeError" in captured.err
    # 정상 line 2개 출력
    out_lines = [ln for ln in captured.out.strip().split("\n") if ln]
    assert len(out_lines) == 2


# === find_latest_session_dir (2-tier 탐색 + DIALECTIC_RUNS_DIR override) ===

def test_find_latest_session_dir_uses_dialectic_runs_dir(tmp_path, monkeypatch, capsys):
    base = tmp_path / "runs"
    workdir = base / "20260509-120000-Ab3CdEfG"
    session_old = workdir / "20260509T100000Z"
    session_new = workdir / "20260509T110000Z"
    for s in (session_old, session_new):
        s.mkdir(parents=True)
        (s / "messages.jsonl").write_text(
            json.dumps(_msg_dict(content="x")) + "\n", encoding="utf-8",
        )
    # mtime을 명시적으로 차등
    old_t = time.time() - 100
    new_t = time.time() - 10
    import os
    os.utime(session_old, (old_t, old_t))
    os.utime(session_new, (new_t, new_t))

    monkeypatch.setenv("DIALECTIC_RUNS_DIR", str(base))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    found = find_latest_session_dir()
    assert found == session_new


def test_find_latest_session_dir_returns_none_when_base_missing(tmp_path, monkeypatch):
    missing = tmp_path / "no-such-dir"
    monkeypatch.setenv("DIALECTIC_RUNS_DIR", str(missing))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert find_latest_session_dir() is None


# === resolve_session_dir ===

def test_resolve_session_dir_workdir_level_picks_latest_session(tmp_path):
    workdir = tmp_path / "wd"
    s1 = workdir / "20260509T100000Z"
    s2 = workdir / "20260509T110000Z"
    for s in (s1, s2):
        s.mkdir(parents=True)
        (s / "messages.jsonl").write_text("\n", encoding="utf-8")
    import os
    os.utime(s1, (time.time() - 100, time.time() - 100))
    os.utime(s2, (time.time() - 10, time.time() - 10))

    found = resolve_session_dir(workdir)
    assert found == s2


def test_resolve_session_dir_session_dir_direct_returned_as_is(tmp_path):
    session = tmp_path / "20260509T120000Z"
    session.mkdir()
    (session / "messages.jsonl").write_text("\n", encoding="utf-8")
    found = resolve_session_dir(session)
    assert found == session


def test_resolve_session_dir_none_when_no_children(tmp_path):
    workdir = tmp_path / "empty-wd"
    workdir.mkdir()
    assert resolve_session_dir(workdir) is None


# === _logs_entry (CLI Namespace 분기) ===

def test_logs_entry_explicit_workdir_session(tmp_path, capsys):
    workdir = tmp_path / "wd"
    session_ts = "20260509T120000Z"
    session = workdir / session_ts
    session.mkdir(parents=True)
    _write_jsonl(session / "messages.jsonl", [_msg_dict(content="ok")])

    args = argparse.Namespace(
        workdir=str(workdir), session=session_ts,
        tail=None, follow=False, kind=None, full=False,
    )
    rc = _logs_entry(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "kind=proposal" in out


def test_logs_entry_explicit_session_missing_returns_1(tmp_path, capsys):
    workdir = tmp_path / "wd"
    workdir.mkdir()
    args = argparse.Namespace(
        workdir=str(workdir), session="20260509T999999Z",
        tail=None, follow=False, kind=None, full=False,
    )
    rc = _logs_entry(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert "messages.jsonl 미존재" in err


def test_logs_entry_workdir_with_no_children_returns_1(tmp_path, capsys):
    workdir = tmp_path / "empty-wd"
    workdir.mkdir()
    args = argparse.Namespace(
        workdir=str(workdir), session=None,
        tail=None, follow=False, kind=None, full=False,
    )
    rc = _logs_entry(args)
    assert rc == 1
    err = capsys.readouterr().err
    assert "session 미발견" in err


def test_session_ts_pattern_constant():
    """`_SESSION_TS_PATTERN`은 `%Y%m%dT%H%M%SZ` 형식만 매칭."""
    assert _SESSION_TS_PATTERN.match("20260509T071838Z")
    assert not _SESSION_TS_PATTERN.match("2026-05-09T07:18:38Z")
    assert not _SESSION_TS_PATTERN.match("20260509T071838")
