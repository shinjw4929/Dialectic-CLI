# Phase D · runtime ts 정책 — 003-workflow-rigor

## 0. 메타

- Phase ID: D
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: C·D 병렬 (영향 .md 겹침 0)
- 예상 LOC: ~10 LOC

## 1. 목표

protocol.md §2 메시지 스키마 ts 필드를 example만이 아닌 **정책 문장(MUST UTC ISO8601)** 으로 명시. 향후 src/schema.py·src/bus.py 작성 시 TZ-naive `datetime.now()` 사용 위험 사전 차단.

## 2. 입력

- `docs/runtime-docs/protocol.md:52-103` §2 메시지 스키마 (변경 대상)
- 사전 검증: `docs/runtime-docs/protocol.md:58` 현재 `"ts": "2026-05-06T14:32:11.482Z", // ISO-8601 UTC` example만 명시. 정책 문장 미존재. `:103` mermaid `+string ts` 자료형만.
- 사전 검증: src/schema.py·src/bus.py 미작성 (`src/` 디렉토리에 `__init__.py`, `agents/`, `cli.py`, `dev_skill_cli.py`만 존재). 정책 박는 시점이 src/schema·bus 작성 전이라 효과 큼.
- 관련 ADR: ADR-1 (JSONL bus, `architecture.md:128`)

## 3. 출력

### 3.1 `docs/runtime-docs/protocol.md` §2 변경

§2 메시지 스키마 본문 (현재 line 52-86)에 정책 단락 1개 추가. 위치: example jsonc block(line 56-86) 직후, "### 스키마 구조" (line 98) 직전.

```markdown
### 타임스탬프 정책

`ts` 필드는 **MUST UTC ISO8601 with `Z` 접미사**. `pyproject.toml` `requires-python = ">=3.10"` 기준 (3.10 호환):

- import: `from datetime import datetime, timezone`
- 생성: `datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')`
- **금지**: 
  - TZ-naive `datetime.now()` (로컬 타임존 누수)
  - `datetime.utcnow()` (Python 3.12+ deprecated, TZ-naive 반환)
  - `datetime.UTC` 상수 (Python 3.11+ alias — 3.10 호환 보장 위해 `timezone.utc` 사용)

src/schema.py에서 ts 필드를 dataclass field로 정의 시 frozen + str 타입. 검증은 `tests/test_schema.py`에서 정규식 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$` 매치 검사.

ADR-1 (JSONL bus) 정합 — 재현성·로그 비교를 위해 timezone 일관성 강제.
```

### 3.2 `docs/dev-docs/Documentation-Checklist.md` §1.2 매핑 한정 변경

`:32` §1.2 런타임 .md 매핑의 첫 행 갱신 (P1-4 게이트 충돌 해결, 00-plan.md §5.3a 참조). 본 변경은 **A 층 자산** — Phase D 작업이지만 commit 1(A 층)에 묶임.

기존:
```markdown
| `docs/runtime-docs/protocol.md` 메시지 스키마 | `src/schema.py`, `src/bus.py`, `tests/test_schema.py`, `docs/dev-docs/architecture.md` §5 인용 부분 |
```

변경 후:
```markdown
| `docs/runtime-docs/protocol.md` 메시지 스키마 **필드** 변경 (필드 추가·제거·자료형 변경) | `src/schema.py`, `src/bus.py`, `tests/test_schema.py`, `docs/dev-docs/architecture.md` §5 인용 부분 |
| `docs/runtime-docs/protocol.md` 정책 단락 추가 (MUST/SHOULD 표현, example 갱신, docstring) | (mapping 외 — sync-docs 게이트 영향 X) |
```

본 변경 후 sync-docs는 protocol.md 정책 단락 추가 commit에 src/schema.py 등 누락 보고 X → drift 게이트 BLOCKED 회피.

## 4. 작업 단위

- [ ] `protocol.md` §2 example 직후 "### 타임스탬프 정책" 신규 sub-section 추가 (~10 LOC, 코드 예시 포함)
- [ ] markdown 헤더 번호 충돌 검사 — 현재 §2에 "### `kind` 값별 의미" (line 87), "### 스키마 구조" (line 98), "### 부가 필드의 타당성" (line 170) 존재. 본 신규 섹션은 § "스키마 구조" 직전 또는 example 직후 자연스러운 위치.
- [ ] **`Documentation-Checklist.md:32` §1.2 매핑 한정 갱신** (P1-4 게이트 충돌 해결, 00-plan.md §5.3a 참조). 변경 부위 행 `docs/runtime-docs/protocol.md` 메시지 스키마 → `docs/runtime-docs/protocol.md` 메시지 스키마 **필드** 변경 (필드 추가·제거·자료형 변경 시). "정책 단락 추가"는 mapping 외 — 본 phase 작업이 sync-docs 게이트에 BLOCKED 안 되도록.

## 5. 검증

- `grep -n "타임스탬프 정책\|MUST UTC ISO8601\|timezone.utc" docs/runtime-docs/protocol.md` → 매치
- `grep -n "datetime.utcnow\|TZ-naive\|datetime.UTC" docs/runtime-docs/protocol.md` → 금지 표현 매치 (정책에 명시됐는지)
- §2 헤더 구조 확인: `grep -n "^### " docs/runtime-docs/protocol.md | head -10` — 신규 섹션 추가됐는지
- Documentation-Checklist 매핑 한정 검증: `grep -n "메시지 스키마.*필드" docs/dev-docs/Documentation-Checklist.md` → 매치 (P1-4 해결 확인)

## 6. 엣지케이스 / 위험 (Phase 한정)

### 6.1 src 미작성 시점에 정책 박힘 — code-conventions.md 보강 검토

src/schema.py·bus.py 작성자가 protocol.md만 보고 작성하면 정책 인지. 그러나 **code-conventions.md**가 Python 코드 컨벤션 단일 진실이라 ts 처리 단락도 거기에 1줄 추가가 안전.

차단: 본 phase 범위 확장? 또는 plan 003 후속? **본 plan 범위 외**로 둠 — Phase D는 protocol.md 한정. code-conventions.md 갱신은 src/schema.py 작성 시점에 함께 (별도 plan 또는 plan 001-run-mode-core/ 내 phase 보강).

### 6.2 Python 3.10 호환 — `timezone.utc` 사용 (`datetime.UTC` 금지)

`pyproject.toml:9` `requires-python = ">=3.10"`. `datetime.UTC` 상수는 Python 3.11+ 추가 — 3.10 환경에서 `from datetime import UTC` ImportError. `datetime.utcnow()`는 Python 3.12+ deprecated.

3.10 호환 보장 패턴: `from datetime import datetime, timezone` + `datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')`. 본 phase §3.1 정책 코드는 본 패턴으로 작성됨.

차단: pyproject.toml `requires-python` 변경(3.11+ 격상) 시 `datetime.UTC` 사용 가능. 단 격상은 별도 ADR 필요 (현재 외부 의존성 0 정책 영향 0).

### 6.3 milliseconds vs microseconds 정밀도 결정

example `2026-05-06T14:32:11.482Z`는 millisecond 정밀도. `datetime.now(tz=timezone.utc).isoformat()`은 default microsecond. `timespec='milliseconds'` 명시 필요.

차단: 정책 단락에 `timespec='milliseconds'` 명시. tests/test_schema.py 정규식도 `\.\d{3}Z` (3자리) 강제.

### 6.4 Python `+00:00` → `Z` 변환

`datetime.now(tz=timezone.utc).isoformat()`는 `+00:00` 접미사 출력. example의 `Z` 접미사로 변환은 `.replace('+00:00', 'Z')` 또는 `.strftime()` 사용.

차단: 정책 단락에 변환 코드 명시 (위 §3.1).
