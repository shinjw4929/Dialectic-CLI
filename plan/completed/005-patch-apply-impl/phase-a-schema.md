# Phase A · Schema (Meta 4 필드 확장) — 005-patch-apply-impl

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A-B (Phase B와 동시 실행 가능 — schema와 patch_apply는 import 의존 0)
- 예상 LOC: 코드 ~10 / 테스트 ~30

## 1. 목표

`src/schema.py` `Meta` dataclass에 `patches` / `apply_status` / `apply_error` / `files_changed` 4 필드를 default=None으로 추가하여 protocol.md §2 line 85-91 명세를 Python 측에 반영. 기존 `Meta(...)` 직접 인스턴스화 코드(어댑터, SENTINEL_META, 모든 테스트)는 회귀 0이어야 함.

## 2. 입력

- `docs/runtime-docs/protocol.md:85-91` — Meta 4 신 필드 명세 (kind=proposal일 때 patches, kind=patch_applied일 때 apply_status/apply_error/files_changed)
- `docs/runtime-docs/protocol.md:67` — kind enum에 `patch_applied` 포함 (이미 cascade 완료, 본 Phase는 검증만)
- `src/schema.py:19-34` — 기존 Meta 14 필드 (수정 진입점)
- `src/schema.py:65-114` — `to_dict()` / `from_dict()` (`fields(self.meta)` 자동 iteration이라 신 필드 자동 picked up — 수정 불요)
- `tests/test_schema.py` — 기존 테스트 패턴 (Meta 직접 인스턴스화 + ts 형식 검증)
- 사전 검증된 사실:
  - Python 3.10+ dataclass `frozen=True, slots=True` + default=None 조합은 정상 작동 (slots는 default 값과 무관 — `__slots__` 튜플만 결정).
  - `from_dict`이 `Meta(**meta_d)` 호출 — meta_d에 신 필드 키가 없으면 default=None로 채워짐 (기존 JSONL 라인 호환).

## 3. 출력

### 3.1 `src/schema.py` 변경 (수정)

`Meta` dataclass의 `convergence_streak` 필드(`:34`) 직후에 4 필드 추가:

```python
# paste
    # === ADR-10 patch_apply 메커니즘 (protocol.md §2 line 85-91) ===
    patches: list[dict[str, str]] | None = None
    apply_status: str | None = None
    apply_error: str | None = None
    files_changed: list[str] | None = None
```

위 4 줄은 `convergence_streak: int | None = None` 직후(`src/schema.py:34`)에 그대로 paste — 식별자·타입·default 모두 명세 1:1 (protocol.md §2 line 86~91 키 이름과 일치 필수). Meta 클래스 헤더와 기존 14 필드는 변경 0.

- 4 필드 모두 default=None — 기존 호출자 인자 무영향.
- 타입: `list[dict[str, str]]`은 patch 객체 형식 `{"file":..., "search":..., "replace":...}`. JSONL 직렬화/역직렬화 시 dict로 그대로 흐름 (`json.dumps`/`json.loads`).
- list 기본값 mutable default 함정 회피: `default=None` (빈 리스트 default factory 불요 — None일관 채택, 01-plan.md §5.4 위험 대응).

### 3.2 `tests/test_schema.py` 추가 (수정)

신 필드 to_dict/from_dict 왕복 테스트 — 4 함수:

```python
# spec
def test_meta_patches_field_roundtrip():
    """kind=proposal Meta — patches list 채움."""
    # Meta(..., patches=[{"file":"a.py","search":"x","replace":"y"}]) → to_dict → from_dict → 동일

def test_meta_apply_status_ok_roundtrip():
    """kind=patch_applied Meta — apply_status="ok", files_changed=["a.py"]."""

def test_meta_apply_status_failed_roundtrip():
    """kind=patch_applied Meta — apply_status="failed", apply_error 채움, files_changed=[]."""

def test_meta_default_none_for_new_fields():
    """기존 호출자(어댑터·SENTINEL_META)가 14 필드만 전달 시 신 필드는 default=None."""
```

## 4. 작업 단위

- [ ] `src/schema.py:34` 직후 4 필드 추가 (patches / apply_status / apply_error / files_changed, default=None)
- [ ] `python -c "from src.schema import Meta, Message; m = Meta(vendor='x', agent_cli='x', model=None, session_id=None, thread_id=None, input_tokens=0, output_tokens=0, cached_input_tokens=0, reasoning_output_tokens=0, cost_usd=None, latency_ms=0, is_mock=False, workdir='/tmp'); assert m.patches is None"` smoke import 성공 검증 (slots+default 호환)
- [ ] `tests/test_schema.py`에 4 테스트 함수 추가 (TO-BE §3.2 명세대로)
- [ ] `pytest tests/test_schema.py -q` pass
- [ ] `pytest tests/ -q` 전체 (6 파일) pass — 회귀 0 (어댑터 응답 생성, SENTINEL_META, orchestrator 메시지 생성 모두 영향 없음)

## 5. 검증

- `python -c "from src.schema import Meta; print([f.name for f in Meta.__dataclass_fields__.values()])"` 출력에 18 필드 확인 (기존 14 + 신 4).
- `pytest tests/test_schema.py -q` pass.
- `pytest tests/ -q` pass — 6 파일 모두 회귀 0 (특히 `test_orchestrator_converge.py` — Meta 인스턴스화 다수 포함).
- to_dict의 JSONL 직렬화 라인 1줄에 신 필드 4개가 모두 포함됨을 from_dict 왕복으로 확인.

## 6. 엣지케이스 / 위험 (Phase 한정)

- **slots+default=None 조합**: Python 3.10 dataclass의 알려진 제약은 default가 mutable일 때만 — None은 immutable, 무영향. import smoke 1회로 검증.
- **`fields(self.meta)` 자동 iteration**: `to_dict`(`:67`)이 dataclass `fields()` 사용 → 신 필드 자동 포함. `from_dict`은 `Meta(**meta_d)` (`:93`) — 키 부재 시 default=None로 채움. 기존 JSONL 라인(14 필드만 포함) 역호환 보장. 별도 마이그레이션 0.
- **테스트 fixture 공유 변수**: 신 테스트가 기존 `_make_meta()` 헬퍼(있다면) 재사용 가능한지 검토. 없으면 인라인 fixture로.
- **Meta 직렬화 키 순서**: JSON 라인의 키 순서는 dict insertion order — Python 3.7+ 보장. 신 필드 4개가 마지막에 추가됨을 to_dict 출력 첫 라인 확인 (외부 도구 의존 시 영향 가능 — 본 도구는 키-기반 read-back이라 무관).
- **Phase B와의 격리**: 본 Phase는 `src/patch_apply.py`를 import하지 않음 — A·B 병렬 실행 시 두 phase가 같은 파일 수정 0. Phase C에서만 둘을 합침.
