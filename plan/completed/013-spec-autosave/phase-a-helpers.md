# Phase A · helpers (slug + path resolve) — 013-spec-autosave

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: —
- 예상 LOC: ~45 (코드) + ~50 (테스트)

## 1. 목표

`src/orchestrator.py`에 `_task_to_slug` + `_resolve_spec_path` 2개 helper 신규 추가. 자유 텍스트 task content를 안전한 파일명 slug로 변환하고, `<workdir>/specs/<slug>.md` 경로를 결정 (충돌 시 timestamp 접미사 fallback). 단위 테스트로 영문/한글/특수문자/장문/충돌 케이스 검증.

## 2. 입력

- [`src/orchestrator.py`](../../src/orchestrator.py) — helper 추가 위치 (`MODE_ROLES` 정의부 근처 또는 모듈 상단의 utility 영역. 기존 `_now_ts` `:82-84` 패턴 참고). **plan 010 Phase C가 같은 영역에 `_resolve_workdir` 추가 가능 — 010 선행 시 본 helper들은 `_resolve_workdir` 직후 또는 `_now_ts` 직후 배치, narrative 충돌 0**
- [`docs/dev-docs/code-conventions.md`](../../docs/dev-docs/code-conventions.md) §2 — 외부 의존성 0 규칙 (표준 라이브러리 `re` / `pathlib` / `datetime`만 사용)
- 사전 검증 사실: WSL/Linux UTF-8 default → 한글 파일명 정합 (본 도구 환경 가정)
- 사전 검증 사실: Phase A는 `tmp_path` fixture만 사용 — plan 010 Phase C 산출 `_resolve_workdir` 의존 0. 단위 테스트 회귀 0 (010 진행 여부 무관)
- 슬러그 정책 (사용자 결정 a):
  - 첫 50 char (max_len) 추출
  - lowercase
  - 영숫자(`[a-z0-9]`) + 한글(`[가-힣]`) + 하이픈/언더스코어 유지
  - 그 외(공백·특수문자) → 단일 hyphen
  - 연속 hyphen → 단일 hyphen
  - 양끝 hyphen 제거
  - 빈 결과 → fallback "task"

## 3. 출력

### 3.1 `src/orchestrator.py` 신규 helper 2개

`_task_to_slug` 함수 신규:

```python
# spec
def _task_to_slug(task: str, *, max_len: int = 50) -> str:
    """자유 텍스트 task content → 안전한 파일명 slug.

    정책:
    - 첫 max_len char 추출 후 lowercase
    - 영숫자 + 한글 + '-' + '_' 만 유지, 그 외 → '-'
    - 연속 '-' → 단일, 양끝 '-' 제거
    - 빈 결과 → "task" fallback (사용자 결정 a — task content가 모두 특수문자인 경우)

    UTF-8 가정 (WSL/Linux). macOS NFD/Windows 미지원.
    """
```

`_resolve_spec_path` 함수 신규:

```python
# spec
def _resolve_spec_path(workdir: Path, task: str, *, session_ts: str) -> Path:
    """`<workdir>/specs/<slug>.md` 경로 결정.

    - `_task_to_slug(task)` → slug
    - `<workdir>/specs/` 디렉토리 mkdir(parents=True, exist_ok=True)
    - 기본 경로: `<workdir>/specs/<slug>.md`
    - 충돌 시 (이미 존재) → `<workdir>/specs/<slug>-<session_ts>.md` 접미사 fallback
      (run_session `:662` 산출 `session_ts` (`%Y%m%dT%H%M%SZ` 형식) 재사용 — filename-safe 보장,
      별도 timestamp 변환 불필요. session_dir 디렉토리명과 1:1 매핑 → 디버깅 정합)
    - spec.md 위치는 SSOT narrative(outline/04 `:199`/planner.md `:11`) 정합으로 top-level
      `<workdir>/specs/` 유지. session 격리(`:662-666`)는 messages.jsonl/sessions/raw 한정.
    """
```

### 3.2 신규 단위 테스트 — `tests/test_spec_autosave.py`

```python
# spec
# _task_to_slug 케이스 ≥6
def test_slug_english_simple():
    """'Add a, b function' → 'add-a-b-function'"""

def test_slug_korean():
    """'덧셈 함수 작성' → '덧셈-함수-작성'"""

def test_slug_special_chars():
    """'Find max(a, b) — return larger' → 'find-max-a-b-return-larger'"""

def test_slug_long_truncate():
    """50 char 초과 task → 50 char로 truncate + 양끝 hyphen 정리"""

def test_slug_empty():
    """'' → 'task' fallback"""

def test_slug_all_special():
    """'!!! ??? ###' → 'task' fallback"""

# _resolve_spec_path 케이스 ≥4
def test_resolve_spec_path_basic(tmp_path):
    """기본: <workdir>/specs/<slug>.md 경로 + specs/ 자동 생성 (session_ts 무관)"""

def test_resolve_spec_path_collision_session_ts(tmp_path):
    """기존 specs/<slug>.md 존재 시 <slug>-<session_ts>.md 접미사 (session_ts="20260509T123456Z" 등 인자 그대로 사용)"""

def test_resolve_spec_path_specs_mkdir(tmp_path):
    """specs/ 디렉토리 미존재 시 자동 생성 (parents=True). spec.md는 top-level — <workdir>/<session_ts>/specs/ 아님 검증"""

def test_resolve_spec_path_absolute(tmp_path):
    """반환 경로가 절대 경로 (workdir resolve 정합)"""
```

## 4. 작업 단위

- [ ] `src/orchestrator.py`에 `_task_to_slug` 함수 추가 (위치: `_now_ts` `:82-84` 직후 또는 utility 영역)
- [ ] `import re` 모듈 상단 추가 (이미 있으면 X)
- [ ] slug 변환 로직 (6단계): `s = task[:max_len]` (truncate 먼저 — UTF-8 char 단위, byte 아님) → `s = s.lower()` → `re.sub(r'[^a-z0-9가-힣\-_]', '-', s)` → `re.sub(r'-+', '-', s)` → `s.strip('-')` → 빈 결과 시 `"task"` fallback
- [ ] `src/orchestrator.py`에 `_resolve_spec_path` 함수 추가 (`_task_to_slug` 직후) — 시그니처 `(workdir: Path, task: str, *, session_ts: str) -> Path`
- [ ] `<workdir>/specs/` (top-level — NOT `<workdir>/<session_ts>/specs/`) mkdir(parents=True, exist_ok=True) — 기존 `:665` `sessions_dir.mkdir` 패턴 재사용
- [ ] 충돌 fallback: 인자 `session_ts` 그대로 접미사로 사용 (`f"{slug}-{session_ts}.md"`) — filename-safe 이미 보장(`%Y%m%dT%H%M%SZ`)
- [ ] `tests/test_spec_autosave.py` 신규 작성 — `_task_to_slug` 6 케이스 + `_resolve_spec_path` 4 케이스
- [ ] mock 패턴 미사용 (helper는 순수 함수/파일 시스템만 — `tmp_path` fixture 활용)

## 5. 검증

- `python -c "from src.orchestrator import _task_to_slug, _resolve_spec_path; print(_task_to_slug('Hello World!'))"` 성공 (`hello-world` 출력)
- `python -c "from pathlib import Path; from src.orchestrator import _resolve_spec_path; print(_resolve_spec_path(Path('/tmp/x'), 'task', session_ts='20260509T120000Z'))"` 성공 (절대 경로 출력)
- `pytest -q tests/test_spec_autosave.py` 신규 ≥10 케이스 pass
- `pytest -q` 전체 회귀 0 (특히 plan 011 산출 + plan 009 산출 회귀)
- 한글 파일 생성 검증: `pytest`가 한글 slug로 실제 파일 생성 → `Path.exists()` 통과 확인 (WSL/Linux UTF-8 정합)

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **한글 정규식 범위**
   - `[가-힣]` 범위는 한글 음절 11,172자 (완성형). 자모(`ㄱ-ㅎ`/`ㅏ-ㅣ`) 포함 X — 실 사용 자유 task에 자모 단독 등장 가능성 낮음
   - 한자(`[一-龥]`)·일본어 등 다른 CJK 문자는 `-`로 치환됨 (의도된 단순화)
   - 향후 확장 필요 시 별도 plan

2. **timestamp 접미사 형식 — `session_ts` 재사용 (NEW)**
   - 로그 레이아웃 변경(`:662-666`)으로 run_session이 이미 `session_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")` 산출 — filename-safe `:`/`.` 미포함
   - `_resolve_spec_path` 인자로 `session_ts` 받아 그대로 접미사 사용 — 별도 timestamp 변환·regex sub 불필요
   - 부수효과: spec.md 충돌 fallback 파일명(`<slug>-<session_ts>.md`)이 messages.jsonl 디렉토리(`<workdir>/<session_ts>/`)와 1:1 매핑 — 디버깅 시 어느 session 산출인지 즉각 식별

3. **specs/ 디렉토리 권한**
   - workdir이 사용자 제공 디렉토리(plan 011 직접 입력)일 때 권한 부족하면 `OSError` raise
   - `_resolve_spec_path`는 mkdir 실패 시 그대로 propagate — 호출자(`run_session`)가 try/except 처리
   - Phase B에서 wiring 시 try/except 또는 ADR-6 SystemExit과 정합 검토

4. **slug 충돌 race condition**
   - `_resolve_spec_path` exists 체크 → 같은 ms에 다른 호출이 같은 timestamp 생성 가능 (이론상)
   - 본 도구 단일 프로세스 + 동기 호출 → race 0 (방어 불필요)
   - 향후 병렬 (compare 모드 등) 진입 시 별도 plan

5. **max_len 정책**
   - 50 char가 충분한지 (long task content 가독성 vs 파일명 길이)
   - `len(slug.encode('utf-8'))` 기준이 아닌 char 기준 — UTF-8 한글은 3 byte이므로 실제 파일명 byte 길이는 ~150 byte. ext4 max 255 byte 한도 내
   - 별도 정책 변경 필요 시 `max_len` 파라미터로 조정 가능
