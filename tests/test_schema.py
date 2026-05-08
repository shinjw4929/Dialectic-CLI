"""Message / Meta round-trip + ts 형식 검증 (protocol.md §2)."""

import json
import re
from datetime import datetime, timezone

from src.schema import Message, Meta

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _full_meta() -> Meta:
    return Meta(
        vendor="openai", agent_cli="codex", model="gpt-5-codex",
        session_id=None, thread_id="t-019dfd",
        input_tokens=13281, output_tokens=5, cached_input_tokens=11648,
        reasoning_output_tokens=13,
        cost_usd=0.0, latency_ms=2371, is_mock=False,
        workdir="/tmp/dialectic-abc",
        convergence_streak=1,
    )


def test_message_round_trip_full_fields():
    m = Message(
        ts="2026-05-07T12:00:00.000Z",
        msg_id="019dfd43-7a67-4a69-9d4b-aaaabbbb",
        parent_id="019dfd43-7a67-4a69-9d4b-bbbbcccc",
        turn_id=1, seq_in_turn=1,
        from_="implementer", to="broadcast",
        slot="driver", mode="run", kind="proposal",
        content="hello", directive=None,
        meta=_full_meta(),
    )
    line = json.dumps(m.to_dict(), ensure_ascii=False)
    restored = Message.from_dict(json.loads(line))
    assert restored == m
    # `from` 키 ↔ `from_` 변환 검증
    d = m.to_dict()
    assert "from" in d and "from_" not in d
    assert d["from"] == "implementer"


def test_meta_14_fields_round_trip():
    meta = _full_meta()
    d = {f: getattr(meta, f) for f in (
        "vendor", "agent_cli", "model", "session_id", "thread_id",
        "input_tokens", "output_tokens", "cached_input_tokens",
        "reasoning_output_tokens", "cost_usd", "latency_ms", "is_mock",
        "workdir", "convergence_streak",
    )}
    assert len(d) == 14
    restored = Meta(**d)
    assert restored == meta


def test_ts_regex_matches_orchestrator_format():
    """orchestrator._now_ts() 형식이 protocol.md §2 line 92 정규식 매치."""
    ts = (datetime.now(tz=timezone.utc)
          .isoformat(timespec="milliseconds")
          .replace("+00:00", "Z"))
    assert _TS_RE.match(ts), f"ts {ts!r} does not match protocol.md §2 regex"


# === ADR-10 patch_apply 메커니즘 — Meta 신 4 필드 (protocol.md §2 line 85-91) ===


def test_meta_patches_field_roundtrip():
    """kind=proposal Meta — patches list 채움 → JSON 직렬화 → from_dict 복원 후 동일."""
    patches = [
        {"file": "src/a.py", "search": "old_text", "replace": "new_text"},
        {"file": "src/b.py", "search": "foo", "replace": "bar"},
    ]
    meta = Meta(
        vendor="anthropic", agent_cli="claude", model="claude-opus",
        session_id="s-001", thread_id=None,
        input_tokens=100, output_tokens=20, cached_input_tokens=0,
        reasoning_output_tokens=0,
        cost_usd=0.01, latency_ms=1500, is_mock=False,
        workdir="/tmp/dialectic-xyz",
        patches=patches,
    )
    msg = Message(
        ts="2026-05-08T12:00:00.000Z",
        msg_id="019dfd43-7a67-4a69-9d4b-aaaa00000001",
        parent_id=None,
        turn_id=1, seq_in_turn=1,
        from_="implementer", to="broadcast",
        slot="driver", mode="implement", kind="proposal",
        content="patch proposal", directive=None,
        meta=meta,
    )
    line = json.dumps(msg.to_dict(), ensure_ascii=False)
    restored = Message.from_dict(json.loads(line))
    assert restored == msg
    assert restored.meta.patches == patches
    # 신 필드 키가 직렬화 dict에 포함됨
    assert "patches" in json.loads(line)["meta"]


def test_meta_apply_status_ok_roundtrip():
    """kind=patch_applied Meta — apply_status="ok", files_changed 채움."""
    meta = Meta(
        vendor="mock", agent_cli="mock", model=None,
        session_id=None, thread_id=None,
        input_tokens=0, output_tokens=0, cached_input_tokens=0,
        reasoning_output_tokens=0,
        cost_usd=None, latency_ms=0, is_mock=True,
        workdir="/tmp/dialectic-applied",
        apply_status="ok",
        apply_error=None,
        files_changed=["src/a.py"],
    )
    msg = Message(
        ts="2026-05-08T12:00:01.000Z",
        msg_id="019dfd43-7a67-4a69-9d4b-aaaa00000002",
        parent_id="019dfd43-7a67-4a69-9d4b-aaaa00000001",
        turn_id=1, seq_in_turn=2,
        from_="system", to="broadcast",
        slot=None, mode="implement", kind="patch_applied",
        content="applied 1 file", directive=None,
        meta=meta,
    )
    line = json.dumps(msg.to_dict(), ensure_ascii=False)
    restored = Message.from_dict(json.loads(line))
    assert restored == msg
    assert restored.meta.apply_status == "ok"
    assert restored.meta.apply_error is None
    assert restored.meta.files_changed == ["src/a.py"]


def test_meta_apply_status_failed_roundtrip():
    """kind=patch_applied Meta — apply_status="failed", apply_error 채움, files_changed=[]."""
    meta = Meta(
        vendor="mock", agent_cli="mock", model=None,
        session_id=None, thread_id=None,
        input_tokens=0, output_tokens=0, cached_input_tokens=0,
        reasoning_output_tokens=0,
        cost_usd=None, latency_ms=0, is_mock=True,
        workdir="/tmp/dialectic-failed",
        apply_status="failed",
        apply_error="search text not found in src/a.py",
        files_changed=[],
    )
    msg = Message(
        ts="2026-05-08T12:00:02.000Z",
        msg_id="019dfd43-7a67-4a69-9d4b-aaaa00000003",
        parent_id="019dfd43-7a67-4a69-9d4b-aaaa00000001",
        turn_id=1, seq_in_turn=2,
        from_="system", to="broadcast",
        slot=None, mode="implement", kind="patch_applied",
        content="apply failed", directive=None,
        meta=meta,
    )
    line = json.dumps(msg.to_dict(), ensure_ascii=False)
    restored = Message.from_dict(json.loads(line))
    assert restored == msg
    assert restored.meta.apply_status == "failed"
    assert restored.meta.apply_error == "search text not found in src/a.py"
    assert restored.meta.files_changed == []


def test_meta_default_none_for_new_fields():
    """기존 호출자(어댑터·SENTINEL_META)가 14 필드만 전달 시 신 4 필드는 default=None.

    Meta(...) 인자 14개 + convergence_streak default 사용 — 신 4 필드 직접 전달 0.
    """
    meta = Meta(
        vendor="openai", agent_cli="codex", model=None,
        session_id=None, thread_id=None,
        input_tokens=0, output_tokens=0, cached_input_tokens=0,
        reasoning_output_tokens=0,
        cost_usd=None, latency_ms=0, is_mock=False,
        workdir="/tmp/dialectic-legacy",
    )
    assert meta.patches is None
    assert meta.apply_status is None
    assert meta.apply_error is None
    assert meta.files_changed is None
    assert meta.convergence_streak is None
    # to_dict 직렬화 후에도 신 4 키가 존재하며 값은 None
    msg = Message(
        ts="2026-05-08T12:00:03.000Z",
        msg_id="019dfd43-7a67-4a69-9d4b-aaaa00000004",
        parent_id=None,
        turn_id=1, seq_in_turn=1,
        from_="implementer", to="broadcast",
        slot="driver", mode="run", kind="proposal",
        content="legacy", directive=None,
        meta=meta,
    )
    meta_d = msg.to_dict()["meta"]
    for key in ("patches", "apply_status", "apply_error", "files_changed"):
        assert key in meta_d, f"신 필드 {key!r} 누락"
        assert meta_d[key] is None
    # from_dict 왕복 — 키 4개 모두 None로 보존
    restored = Message.from_dict(json.loads(json.dumps(msg.to_dict(), ensure_ascii=False)))
    assert restored == msg
