# Phase A · Foundation — 001-run-mode-core

## 0. 메타

- Phase ID: **A**
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: (없음, 직렬 시작점)
- 병렬 그룹: —
- 예상 LOC: ~178 (schema 83 + bus 60 + base 35) — schema 80→83: `convergence_streak: int | None = None` 1 필드 추가 + protocol.md §2 갱신 cross-link 한 줄 + Phase D §3.5.3에서 §2 갱신 시 동기 갱신 필요

## 1. 목표

`Message`/`Meta` dataclass + JSONL append-only `Bus` + `AgentRunner` Protocol·`AgentResponse` 확정. 다른 Phase의 기반.

## 2. 입력

- `docs/runtime-docs/protocol.md` §2 (`:52-194`, 메시지 스키마·필드 정의) — 본 phase 출력의 1:1 기준.
- `docs/runtime-docs/protocol.md` §8 (`:302-326`, AgentRunner Protocol 시그니처).
- `docs/dev-docs/code-conventions.md` §1 (`:7-13`, Python 표준 — `dataclass(frozen=True, slots=True)`, `Protocol`).
- `docs/dev-docs/code-conventions.md` §4 (`:61-78`, JSONL append-only·`f.flush()` 강제·`msg_id` UUID·`meta.workdir`).
- `docs/dev-docs/code-conventions.md` §5 (`:81-119`, AgentRunner — keyword-only `run`·frozen `AgentResponse`·`AgentAuthError`).

## 3. 출력

### 3.1 `src/schema.py` (신규, ~83 LOC — phase-a §0 합산과 일관: schema 83 = Meta 14 필드 + Message 12 필드 + to_dict/from_dict 시그니처)

```python
# paste
@dataclass(frozen=True, slots=True)
class Meta:
    vendor: str            # "openai" | "anthropic" | "mock"
    agent_cli: str         # "codex" | "claude" | "mock"
    model: str | None      # codex는 항상 None (이벤트에 model 필드 부재)
    session_id: str | None # claude
    thread_id: str | None  # codex
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    reasoning_output_tokens: int       # codex가 turn.completed.usage로 보고 — claude·mock은 0 (정직성: silent 손실 방지)
    cost_usd: float | None
    latency_ms: int
    is_mock: bool
    workdir: str
    convergence_streak: int | None = None   # outline/02 §2.9: reviewer [CONVERGED] 단독 마지막 줄 출력 시 1, 그 외 None. orchestrator가 매 턴 누적 → K 도달 시 auto_end_converged. default=None이라 기존 호출 영향 X (default 필드는 dataclass field 순서 마지막)

@dataclass(frozen=True, slots=True)
class Message:
    ts: str                # ISO-8601 UTC
    msg_id: str            # uuid4
    parent_id: str | None  # task 메시지만 None
    turn_id: int
    seq_in_turn: int
    from_: str             # "implementer" | "spec-reviewer" | ... | "user" | "system" (예약어 회피로 from_)
    to: str
    slot: str | None       # "driver" | "reviewer" | None (system/user)
    mode: str              # "run" | "plan" | "implement" | "compare"
    kind: str              # "task" | "proposal" | "critique" | "decision" | "error" | "meta"
    content: str
    directive: str | None
    meta: Meta

    def to_dict(self) -> dict: ...    # from_ → "from", protocol.md §2 키 1:1
    @classmethod
    def from_dict(cls, d: dict) -> "Message": ...
```

### 3.2 `src/bus.py` (신규, ~60 LOC)

```python
class Bus:
    def __init__(self, path: Path): ...
    def append(self, msg: Message) -> None:
        # open(path, "a") + json.dumps(msg.to_dict()) + "\n"
        # f.flush() 강제, fsync는 선택(범위 밖)
    def read_all(self) -> list[Message]: ...
    # 반환 list는 파일 라인 순서 보존 (append-only이므로 시간 순) —
    # orchestrator가 `bus.read_all()[-1].msg_id`로 직전 메시지 추출 시 의존.
    # 의도적으로 update / delete API 없음 (append-only)
```

### 3.3 `src/agents/base.py` (신규, ~35 LOC)

```python
# paste
@dataclass(frozen=True, slots=True)
class AgentResponse:
    text: str
    raw_path: Path
    meta: Meta            # schema.Meta 재사용

class AgentAuthError(Exception):
    """인증 실패 — orchestrator가 catch하여 README §환경설정 안내"""

class AgentRunner(Protocol):
    name: str
    vendor: str
    def run(
        self,
        prompt: str,
        *,
        raw_log_path: Path,
        timeout_s: int,
        workdir: Path,
    ) -> AgentResponse: ...
```

## 4. 작업 단위

- [ ] `src/schema.py` 생성 — `Meta`·`Message` dataclass + `to_dict`/`from_dict` (key `from_` ↔ `"from"` 변환).
- [ ] `src/bus.py` 생성 — `Bus(path)` + `append(msg)` (open `"a"` + json.dumps + flush) + `read_all()`. 수정/삭제 API 미노출.
- [ ] `src/agents/base.py` 생성 — `AgentResponse` (frozen) + `AgentRunner` Protocol (keyword-only) + `AgentAuthError`.
- [ ] `src/agents/__init__.py` 갱신 — `from .base import AgentResponse, AgentRunner, AgentAuthError` re-export.

## 5. 검증

- `python -c "from src.schema import Message, Meta; from src.bus import Bus; from src.agents.base import AgentResponse, AgentRunner, AgentAuthError"` exit 0.
- 즉석 round-trip 검증 (Phase D test_schema.py에서 정식화):
  ```python
  m = Message(ts="2026-05-07T12:00:00Z", msg_id="t0", parent_id=None, turn_id=0, seq_in_turn=1, from_="system", to="broadcast", slot=None, mode="run", kind="task", content="x", directive=None, meta=Meta(vendor="mock", agent_cli="mock", model=None, session_id=None, thread_id=None, input_tokens=0, output_tokens=0, cached_input_tokens=0, reasoning_output_tokens=0, cost_usd=None, latency_ms=0, is_mock=True, workdir="/tmp"))
  assert Message.from_dict(m.to_dict()) == m
  ```
- `src/schema.py` 자체 일관성 인지 — Message 12 필드 + Meta 14 필드 (`reasoning_output_tokens` + `convergence_streak: int | None = None` 포함). schema는 phase A 작성 시점 protocol.md §2 (12 필드)의 **superset**으로 의도된 확장. Phase D §3.5.3 실행 후 protocol.md §2도 14 필드로 갱신됨 → schema ↔ protocol.md §2 동기화 완료. 1:1 grep 일치 검증은 Phase D §5 책임.

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **`from`은 Python 예약어** — dataclass 필드명을 `from_`로 두고 `to_dict()`에서 `"from"` 키로 변환. `from_dict()`도 역변환. 누락 시 JSONL 라인이 파이썬 코드와 키 불일치.
2. **`Meta` 필드 누락** — protocol.md §2의 12 필드 모두 dataclass에 매핑. 빠지면 어댑터에서 `meta=Meta(...)` 호출 실패.
3. **`Message` 동일성 비교** — `frozen=True` + `Meta`도 frozen이라 동등성 자동. 단 `Meta.workdir`이 `Path`가 아닌 `str`(직렬화 안전)로 두는 점 검증.
4. **`Bus.append` flush 누락 시 프로세스 죽으면 부분 기록 손실** (P-JSONL) — `f.flush()` 강제 (`code-conventions.md` §4).
5. **`Bus.read_all()`이 비어 있는 파일에서 fail 안 함** — 빈 파일 → `[]` 반환.
