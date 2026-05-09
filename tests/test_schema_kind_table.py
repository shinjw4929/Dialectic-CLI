"""schema kind 표 7종 + Meta.vendor 4종 round-trip 단언 (plan 009 Phase E).

protocol.md §2 line 67 kind comment 7종 (`task | proposal | critique | decision |
error | meta | patch_applied`) + line 71 vendor 4종 (`openai | anthropic | mock |
user`) 정합. _decision_msg helper와 동일 vendor="user" / agent_cli="user".
"""

import json

from src.schema import Message, Meta


def _meta_user(workdir: str = "/tmp/dialectic-decision") -> Meta:
    """decision kind 메시지의 Meta (vendor="user", LLM 호출 0 정직성)."""
    return Meta(
        vendor="user", agent_cli="user", model=None,
        session_id=None, thread_id=None,
        input_tokens=0, output_tokens=0, cached_input_tokens=0,
        reasoning_output_tokens=0,
        cost_usd=None, latency_ms=0, is_mock=False,
        workdir=workdir,
    )


def test_kind_patch_applied_round_trip():
    """schema.py:53 kind docstring 7종 (patch_applied 포함) — round-trip 단언."""
    meta = Meta(
        vendor="mock", agent_cli="mock", model=None,
        session_id=None, thread_id=None,
        input_tokens=0, output_tokens=0, cached_input_tokens=0,
        reasoning_output_tokens=0,
        cost_usd=None, latency_ms=0, is_mock=True,
        workdir="/tmp/dialectic-pa",
        apply_status="ok", apply_error=None, files_changed=["src/x.py"],
    )
    msg = Message(
        ts="2026-05-09T12:00:00.000Z",
        msg_id="019dfd43-7a67-4a69-9d4b-aaaa00000010",
        parent_id="019dfd43-7a67-4a69-9d4b-aaaa00000009",
        turn_id=1, seq_in_turn=98,
        from_="system", to="broadcast",
        slot=None, mode="run", kind="patch_applied",
        content="apply_status=ok, files_changed=['src/x.py']",
        directive=None, meta=meta,
    )
    line = json.dumps(msg.to_dict(), ensure_ascii=False)
    restored = Message.from_dict(json.loads(line))
    assert restored == msg
    assert restored.kind == "patch_applied"


def test_kind_decision_with_directive_round_trip():
    """decision kind + directive 본문 round-trip (Phase D _decision_msg 정합)."""
    msg = Message(
        ts="2026-05-09T12:00:01.000Z",
        msg_id="019dfd43-7a67-4a69-9d4b-aaaa00000011",
        parent_id="019dfd43-7a67-4a69-9d4b-aaaa00000010",
        turn_id=1, seq_in_turn=97,
        from_="user", to="implementer",
        slot=None, mode="run", kind="decision",
        content="i",
        directive="11+ 웨이브 가속 곡선은 wave^1.3 적용",
        meta=_meta_user(),
    )
    line = json.dumps(msg.to_dict(), ensure_ascii=False)
    restored = Message.from_dict(json.loads(line))
    assert restored == msg
    assert restored.kind == "decision"
    assert restored.content == "i"
    assert restored.directive == "11+ 웨이브 가속 곡선은 wave^1.3 적용"
    assert restored.seq_in_turn == 97  # META_DECISION_SEQ


def test_meta_vendor_user_round_trip():
    """Meta vendor="user" + agent_cli="user" round-trip (schema.py:21 4종 정합)."""
    meta = _meta_user(workdir="/tmp/dialectic-vendor-user")
    d = {f: getattr(meta, f) for f in (
        "vendor", "agent_cli", "model", "session_id", "thread_id",
        "input_tokens", "output_tokens", "cached_input_tokens",
        "reasoning_output_tokens", "cost_usd", "latency_ms", "is_mock",
        "workdir",
    )}
    restored = Meta(**d)
    assert restored == meta
    assert restored.vendor == "user"
    assert restored.agent_cli == "user"
    assert restored.cost_usd is None  # LLM 호출 0 정직성
    assert restored.is_mock is False  # 사용자 입력은 실 행위
