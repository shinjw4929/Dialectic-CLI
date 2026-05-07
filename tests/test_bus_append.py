"""JSONL append-only — 두 번 append + 수정 메서드 부재 + 재오픈 라인 보존."""

from src.bus import Bus
from src.schema import Message, Meta


def _msg(turn_id: int, seq: int, content: str) -> Message:
    return Message(
        ts="2026-05-07T12:00:00.000Z",
        msg_id=f"id-{turn_id}-{seq}", parent_id=None,
        turn_id=turn_id, seq_in_turn=seq,
        from_="system", to="broadcast",
        slot=None, mode="run", kind="task",
        content=content, directive=None,
        meta=Meta(
            vendor="system", agent_cli="system",
            model=None, session_id=None, thread_id=None,
            input_tokens=0, output_tokens=0, cached_input_tokens=0,
            reasoning_output_tokens=0, cost_usd=None, latency_ms=0,
            is_mock=False, workdir="/tmp/x",
        ),
    )


def test_append_twice_yields_two_lines(tmp_path):
    bus = Bus(tmp_path / "messages.jsonl")
    bus.append(_msg(0, 1, "first"))
    bus.append(_msg(1, 1, "second"))
    msgs = bus.read_all()
    assert len(msgs) == 2
    assert msgs[0].content == "first"
    assert msgs[1].content == "second"


def test_bus_has_no_mutation_methods():
    """append-only 보장 — update/delete/truncate 메서드 미노출."""
    for name in ("update", "delete", "truncate"):
        assert not hasattr(Bus, name), f"Bus must not expose {name!r}"


def test_reopen_preserves_existing_lines(tmp_path):
    path = tmp_path / "messages.jsonl"
    Bus(path).append(_msg(0, 1, "first"))
    # 새 Bus 인스턴스로 재오픈
    bus2 = Bus(path)
    bus2.append(_msg(1, 1, "second"))
    msgs = bus2.read_all()
    assert len(msgs) == 2
    assert msgs[0].content == "first"
    assert msgs[1].content == "second"
