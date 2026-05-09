"""Message / Meta dataclasses — JSONL bus 라인 1:1 매핑.

protocol.md §2 (메시지 스키마)의 superset. `convergence_streak` 1 필드는
phase A 시점에 schema에 선반영, protocol.md §2 동기 갱신은 Phase D §3.5.3 책임.

- frozen=True, slots=True: 한 번 작성 후 변경 불가 (append-only 정합).
- `from`은 Python 예약어 → 필드명 `from_`. to_dict()/from_dict()에서 `"from"` 키로 변환.
"""

import re
from dataclasses import dataclass, fields
from typing import Any

# protocol.md §2 line 92 ts 형식 정규식 — `2026-05-08T12:00:00.000Z` 형태 강제.
# orchestrator._now_ts() + 어댑터·테스트 직접 인스턴스 생성 경로 모두 방어 (frozen __post_init__ self-가드).
_TS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


@dataclass(frozen=True, slots=True)
class Meta:
    vendor: str            # "openai" | "anthropic" | "mock" | "user" | "system"
    agent_cli: str         # "codex" | "claude" | "mock" | "user" | "system"
    model: str | None      # codex는 항상 None (이벤트에 model 필드 부재)
    session_id: str | None  # claude
    thread_id: str | None   # codex
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    reasoning_output_tokens: int       # codex가 turn.completed.usage로 보고 — claude·mock은 0
    cost_usd: float | None
    latency_ms: int
    is_mock: bool
    workdir: str
    convergence_streak: int | None = None  # reviewer [CONVERGED] 단독 마지막 줄 출력 시 1, 그 외 None
    # === ADR-10 patch_apply 메커니즘 (protocol.md §2 line 85-91) ===
    patches: list[dict[str, str]] | None = None
    apply_status: str | None = None
    apply_error: str | None = None
    files_changed: list[str] | None = None


@dataclass(frozen=True, slots=True)
class Message:
    ts: str                # ISO-8601 UTC
    msg_id: str            # uuid4
    parent_id: str | None  # task 메시지만 None
    turn_id: int
    seq_in_turn: int
    from_: str             # "implementer" | "spec-reviewer" | ... | "user" | "system"
    to: str
    slot: str | None       # "driver" | "reviewer" | None (system/user)
    mode: str              # "run" | "plan" | "implement" | "compare"
    kind: str              # "task" | "proposal" | "critique" | "decision" | "error" | "meta" | "patch_applied"
    content: str
    directive: str | None
    meta: Meta

    def __post_init__(self) -> None:
        """frozen invariant self-가드 — protocol.md §2 line 92 ts 형식 강제.

        orchestrator `_now_ts()`는 형식을 보장하지만 어댑터·테스트가 직접 `Message(ts=...)`로
        인스턴스 생성하는 경로에서는 자기 검증이 1차 안전망. 위반 시 ValueError raise.
        """
        if not _TS_PATTERN.match(self.ts):
            raise ValueError(
                f"Message.ts 형식 위반 (protocol.md §2 line 92): {self.ts!r} — "
                f"기대: 'YYYY-MM-DDTHH:MM:SS.mmmZ' (밀리초 3자리 + Z 접미사)"
            )

    def to_dict(self) -> dict[str, Any]:
        """JSONL 라인 dict로 직렬화. `from_` → `"from"` 키 변환, protocol.md §2 키 1:1."""
        meta_dict = {f.name: getattr(self.meta, f.name) for f in fields(self.meta)}
        return {
            "ts": self.ts,
            "msg_id": self.msg_id,
            "parent_id": self.parent_id,
            "turn_id": self.turn_id,
            "seq_in_turn": self.seq_in_turn,
            "from": self.from_,
            "to": self.to,
            "slot": self.slot,
            "mode": self.mode,
            "kind": self.kind,
            "content": self.content,
            "directive": self.directive,
            "meta": meta_dict,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Message":
        """JSONL 라인 dict에서 복원. `"from"` → `from_` 키 역변환.

        손상된 dict (필수 키 누락 또는 Meta 필드 부족) 시 친절 ValueError + raw 보존:
        ValueError 메시지에 원본 dict 일부를 담아 caller가 디버깅 가능 (P-JSONL 정직성).
        """
        try:
            meta_d = dict(d["meta"])
            meta = Meta(**meta_d)
            return cls(
                ts=d["ts"],
                msg_id=d["msg_id"],
                parent_id=d["parent_id"],
                turn_id=d["turn_id"],
                seq_in_turn=d["seq_in_turn"],
                from_=d["from"],
                to=d["to"],
                slot=d["slot"],
                mode=d["mode"],
                kind=d["kind"],
                content=d["content"],
                directive=d["directive"],
                meta=meta,
            )
        except (KeyError, TypeError) as exc:
            keys = sorted(d.keys()) if isinstance(d, dict) else "<not-dict>"
            raise ValueError(
                f"Message.from_dict 손상 dict — {type(exc).__name__}: {exc}. "
                f"keys={keys}"
            ) from exc
