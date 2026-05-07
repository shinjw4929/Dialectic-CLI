# schema + jsonl-bus

`src/schema.py` (`Message`/`Meta` dataclass) + `src/bus.py` (append-only JSONL) 진리문서.

## schema

### Message — 12 필드 (frozen=True, slots=True)

| 필드 | 타입 | 설명 |
|---|---|---|
| `ts` | `str` | ISO-8601 UTC `2026-05-08T14:51:05.457Z` (`protocol.md §2:92` 1:1) |
| `msg_id` | `str` | uuid4 hex (정확히 36자 dash-form) |
| `parent_id` | `str \| None` | task만 None, 그 외 직전 메시지 msg_id (DAG 무결성) |
| `turn_id` | `int` | 0=task, 1+=N번째 턴 |
| `seq_in_turn` | `int` | driver=1, reviewer=2, user=3, meta=99 (`META_SEQ_SENTINEL`) |
| `from_` | `str` | "system"/"user"/"implementer"/"spec-reviewer"/"planner"/"plan-reviewer". `from`은 Python 예약어이라 `from_` 필드 사용, `to_dict()`에서 `"from"` 키로 변환 |
| `to` | `str` | "broadcast" 또는 role |
| `slot` | `str \| None` | "driver"/"reviewer"/None (system/user) |
| `mode` | `str` | "run"/"plan"/"implement"/"compare" |
| `kind` | `str` | "task"/"proposal"/"critique"/"decision"/"error"/"meta" |
| `content` | `str` | 본문 |
| `directive` | `str \| None` | 사용자 directive (kind=decision일 때) |
| `meta` | `Meta` | 14 필드 dataclass (아래) |

### Meta — 14 필드 (frozen=True, slots=True)

13 default-없는 + 1 default (`convergence_streak`).

| 필드 | 타입 | 설명 |
|---|---|---|
| `vendor` | `str` | "openai"/"anthropic"/"system"/"mock" |
| `agent_cli` | `str` | "codex"/"claude"/"system"/"mock" |
| `model` | `str \| None` | claude만 (`payload.get("model")`), codex 미보고 |
| `session_id` | `str \| None` | claude OAuth session |
| `thread_id` | `str \| None` | codex `thread.started.thread_id` |
| `input_tokens` | `int` | usage |
| `output_tokens` | `int` | usage |
| `cached_input_tokens` | `int` | claude=`cache_read_input_tokens`, codex=`cached_input_tokens` |
| `reasoning_output_tokens` | `int` | codex만 보고, claude=0 (정직성 — silent loss 차단) |
| `cost_usd` | `float \| None` | claude=`total_cost_usd`, codex=None |
| `latency_ms` | `int` | subprocess 소요 |
| `is_mock` | `bool` | 실 호출=False, mock 재생=True |
| `workdir` | `str` | resolved cwd (재현성) |
| `convergence_streak` | `int \| None = None` | reviewer `[CONVERGED]` 1, 그 외 None. auto_end_converged 메시지에 K 박힘 |

### to_dict / from_dict

- `to_dict()`: `from_` → `"from"` 키 변환. nested Meta → dict.
- `from_dict(d)`: 역변환. `convergence_streak` 누락 시 default None.

round-trip 동치 보장: `Message.from_dict(m.to_dict()) == m` (frozen dataclass `__eq__` 자동).

## bus

### Bus(path: Path) — append-only JSONL writer

```python
class Bus:
    def __init__(self, path: Path) -> None: ...

    def append(self, msg: Message) -> None:
        # open(path, "a", encoding="utf-8") + json.dumps(msg.to_dict()) + "\n"
        # f.flush() 강제 (code-conventions §4)

    def read_all(self) -> list[Message]:
        # 파일 라인 순서 보존 (시간 순) — orchestrator가 [-1]로 직전 메시지 추출 시 의존
        # 빈 파일 → [] 반환
```

### 의도적 부재 (P-JSONL 차단)

- `update`/`delete`/`truncate` 메서드 미노출 — 기존 라인 절대 수정 X
- 정정은 새 메시지 (`kind=meta` 또는 `kind=error`)로 append

`hasattr(bus, "update")` False 단언이 `tests/test_bus_append.py`의 reflection 검증.

### 동시성 (Day 2 범위 외)

단일 프로세스라 file lock 미사용. compare 모드(Day 4) 병렬 실행 시 P-JSONL 위험 ↑ — 그 시점에 fcntl lock 또는 분리 bus 검토.

## 변경 시 갱신 영향

| 코드 변경 | 갱신 대상 |
|---|---|
| Meta 필드 추가/제거 | 본 §Meta 표 + `protocol.md §2` JSONC + classDiagram + `tests/test_schema.py` round-trip 단언 |
| Message 필드 추가/제거 | 본 §Message 표 + `protocol.md §2` + `tests/test_schema.py` |
| `Bus.append/read_all` 시그니처 | 본 §bus + `tests/test_bus_append.py` |
| ts 형식 (`isoformat` 옵션) | `orchestrator._now_ts()` + `protocol.md §2:92` + `tests/test_schema.py` 정규식 단언 |
| `from_/to_dict` 키 변환 | 본 §to_dict/from_dict + `tests/test_schema.py` |

## 관련 문서

- `architecture.md` ADR-1 (JSONL bus + 풀 트랜스크립트 주입)
- `protocol.md §2` (메시지 스키마 단일 진실 — schema.py가 superset)
- `code-conventions.md` §4 (JSONL append-only 규칙)
- `validation.md` P-JSONL (반복 가능 결함 패턴)
