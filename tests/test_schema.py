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
