# Phase B · Patch Apply 모듈 (extract / validate / apply / rollback) — 005-patch-apply-impl

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A-B (Phase A와 동시 실행 가능 — schema와 patch_apply는 import 의존 0)
- 예상 LOC: 코드 ~70 / 테스트 ~80

## 1. 목표

`src/patch_apply.py` 신규 모듈에서 driver 응답 텍스트의 search-replace 블록을 추출(`extract_patches`)하고 workdir에 안전하게 적용(`apply_patches`)하는 함수 2개를 표준 라이브러리만으로 구현. **path traversal 차단 + all-or-nothing 트랜잭션 + best-effort 롤백**이 핵심 책임. orchestrator 통합은 Phase C에서.

## 2. 입력

- `docs/runtime-docs/protocol.md:85-91` — patches dict 형식 `{"file":..., "search":..., "replace":...}` + apply_status `"ok"` | `"failed"` 명세
- `docs/runtime-docs/protocol.md:359-361` — 실패 모드 3행 (SEARCH 미일치 / path 외부 / IO 실패) + apply_error 메시지 형식
- `docs/runtime-docs/protocol.md:232` — R2.6 흐름 텍스트 (`Path.resolve() + 외부 경로 차단 → SEARCH 정확 일치 검색 → REPLACE 치환 → 1개라도 실패 시 전체 롤백`)
- `docs/runtime-docs/roles/implementer.md:78` — driver가 출력하는 search-replace 마커 형식: `FILE: <path>` 헤더 + `<<<<<<< SEARCH` / `=======` / `>>>>>>> REPLACE`
- `docs/dev-docs/code-conventions.md` §2 (외부 의존성 0) / §3 (subprocess 안전 — 본 모듈은 subprocess 사용 X)
- 사전 검증된 사실:
  - Python `re.DOTALL` 플래그로 `.+?`이 줄바꿈 포함 매칭 가능.
  - `Path.resolve()`은 symlink 해소 + 절대 경로 정규화 — Linux/WSL 기준 traversal 차단에 충분.
  - `Path.is_relative_to(other)` Python 3.9+ — workdir 내부 검사 1줄.

## 3. 출력

### 3.1 `src/patch_apply.py` (신규)

**module skeleton (혼합 — 정규식 패턴은 paste, 함수 본문은 spec)**:

```python
# paste
"""ADR-10 search-replace patch — extract + safe apply.

protocol.md §2 line 85-91 (patches/apply_status/...) + §4 line 232 R2.6 (all-or-nothing) +
§9 line 359-361 (실패 3행) 정합. orchestrator는 본 모듈의 두 공개 함수만 호출.

표준 라이브러리만 (re, pathlib.Path) — code-conventions §2.
"""

import re
from pathlib import Path

# protocol.md §2 line 86 patches dict 형식 + role implementer.md:78 마커 형식
# 마커 카운트 7-character (`<<<<<<<` / `=======` / `>>>>>>>`) + named groups
# (`file` / `search` / `replace`)는 ADR-10 명세 1:1 — 변형 금지.
# 정책: file 경로는 `\S+` (공백 포함 경로 비지원) — driver 응답 형식이 한 줄 헤더이고
# 공백 포함 파일명은 본 도구 사용 사례에 부재 (Python 코드베이스 기준). 향후 필요 시
# `FILE: "<path with space>"` 인용 형식을 별도 plan에서 도입.
_PATCH_PATTERN = re.compile(
    r"FILE:\s*(?P<file>\S+)\s*\n"
    r"<{7}\s*SEARCH\s*\n"
    r"(?P<search>.*?)"
    r"\n={7}\s*\n"
    r"(?P<replace>.*?)"
    r"\n>{7}\s*REPLACE",
    re.DOTALL,
)


class PatchApplyError(Exception):
    """내부 시그널 — apply_patches 외부에는 (status, error, files_changed) 튜플로 환원.

    path traversal / SEARCH 미일치 / SEARCH 다중 매치 / IO 실패 단일 catch 가능."""


def validate_patch_path(workdir: Path, file: str) -> Path:  # 시그니처 paste, 본문 spec
    """cwd-isolation.md:55-72 §Layer 4 SSOT 정통 구현 (이전엔 spec만, 코드 부재).

    cwd-isolation.md:64 spec 1:1:
    1. Path(workdir).resolve() / Path(file) 결합 → .resolve()로 정규화
    2. 결과가 workdir.resolve()의 자손인지 .is_relative_to() 검사
    3. symlink escape도 strict=False resolve 후 동일 prefix 검사
    4. 외부면 PatchApplyError("path outside workdir: " + file)
    """
```

위 블록(module docstring · import · `_PATCH_PATTERN` 정규식 · `PatchApplyError` 클래스 + `validate_patch_path` 함수 시그니처)은 그대로 paste. 정규식 마커 카운트와 named group 이름(`file` / `search` / `replace`)은 protocol.md §2 line 86 patches dict 키 + role implementer.md:78 마커 형식과 1:1 일치 필수. `validate_patch_path` 함수명·시그니처는 cwd-isolation.md:55-72 SSOT와 1:1 일치 필수 (SSOT 균열 차단 — review-plan P1).

```python
# spec
def extract_patches(text: str) -> list[dict[str, str]]:
    """driver 응답 텍스트에서 search-replace 블록 추출.

    반환 각 dict: {"file": str, "search": str, "replace": str}. 매칭 0개면 [].
    non-greedy + re.DOTALL — 한 응답에 여러 블록 가능.
    """


def apply_patches(
    patches: list[dict[str, str]], workdir: Path
) -> tuple[str, str | None, list[str]]:
    """all-or-nothing 트랜잭션으로 patches를 workdir에 적용.

    반환: (status, error, files_changed)
    - status="ok" / error=None / files_changed=[변경된 상대 경로]
    - status="failed" / error=사유 / files_changed=[]

    절차:
    1) path validation — `validate_patch_path(workdir, file)` (cwd-isolation.md §Layer 4 SSOT)
       호출. 외부 1개라도 발견 시 PatchApplyError("path outside workdir: <file>").
    2) 빈 SEARCH 차단 — search="" 인 patch가 1개라도 있으면
       PatchApplyError("empty SEARCH not allowed in <file>") (ambiguous 극단 형태,
       어떤 위치 매칭도 결정 불가). 빈 REPLACE는 허용 (driver 명시적 코드 삭제 의도).
    3) dry-run — 각 파일을 한 번 read (encoding="utf-8") → originals/mutated dict에 보존.
       SEARCH 검사: count==0 → PatchApplyError("search not found in <file>"),
       count>1 → PatchApplyError("ambiguous match: search appears N times in <file>")
       (unique-match 정책 — 다중 매치 모호성 차단). 디스크 변경 0.
    4) commit — dry-run의 mutated를 write (encoding="utf-8"). IO 실패 시 originals로
       복원. 복원 실패 시 stderr 경고 + apply_error에 합성 (best-effort).
    """
```

함수 시그니처/반환 타입은 paste 의도, 함수 **본문은 spec** — execute-plan subagent가 정규식 본문(예: 다중 patch 누적 in-memory dry-run 알고리즘) / 내부 헬퍼 함수 분할 / 백업 dict 자료구조는 자유 해석 가능. **`Path.read_text` / `Path.write_text` 호출 시 `encoding="utf-8"` 명시는 paste 의무** (validation.md §2 R-001 P0).

### 3.2 `tests/test_patch_apply.py` (신규)

```python
# spec
"""tests/test_patch_apply.py — extract + apply 단위 검증.

tmp_path fixture로 workdir 격리 — 본 repo cwd 오염 0.
"""

# 테스트 케이스 11 함수:
def test_extract_single_block(): ...      # FILE/SEARCH/REPLACE 1 블록
def test_extract_multiple_blocks(): ...   # 같은 응답에 N 블록 (N=2~3)
def test_extract_zero_when_marker_missing(): ...  # ======= 부재 → []

def test_apply_happy_path(tmp_path): ...  # 단일 파일 SEARCH/REPLACE 적용 검증
def test_apply_path_traversal_blocked(tmp_path): ...  # ../etc/passwd, 절대경로, symlink escape → status="failed", 변경 0
def test_apply_search_not_found_rollback(tmp_path): ...  # count==0 → status="failed", 다른 파일 변경 0
def test_apply_search_ambiguous_blocked(tmp_path): ...  # SEARCH가 파일에 N>1회 → status="failed", apply_error에 N 포함, 변경 0 (unique-match)
def test_apply_multi_file_all_or_nothing(tmp_path): ...  # 2 파일, 두번째 SEARCH 미일치 → 첫번째 미변경
def test_validate_patch_path_ssot(tmp_path): ...  # cwd-isolation §Layer 4 SSOT 시그니처 1:1 — symlink escape 차단 확인
def test_apply_empty_search_blocked(tmp_path): ...  # search="" → status="failed", apply_error="empty SEARCH not allowed" (P1-X4)
def test_extract_blank_line_in_search(): ...  # SEARCH 본문에 빈 줄 포함 시 정규식이 정확히 매칭 (P2-X5)
```

## 4. 작업 단위

- [ ] `src/patch_apply.py` 신규 — module docstring + `_PATCH_PATTERN` 정규식 + `PatchApplyError` 예외 + `extract_patches` 함수 정의
- [ ] `extract_patches`: `_PATCH_PATTERN.finditer(text)` → 각 match의 named group → dict list 반환. 마커 1개라도 없으면 매칭 자체 실패 → `[]`
- [ ] `apply_patches`: 4 단계 분리 구현 (P1-X4 fix — 빈 SEARCH 차단을 (2) 단계로 명시)
  - [ ] (1) path validation — **`cwd-isolation.md:55-72` SSOT의 `validate_patch_path(workdir, file)` 함수**를 **본 모듈(`src/patch_apply.py`) 내부에 정의** (별도 모듈 분리 X — SSOT는 현재 spec만 코드 0 → 본 Phase가 정통 코드 위치). 외부 → `PatchApplyError("path outside workdir: " + file)`. SSOT spec 1:1 준수: `Path(workdir).resolve() / Path(file)` 결합 → `.resolve()` → `is_relative_to(workdir.resolve())` 검사 (cwd-isolation.md:64 표기와 동일)
  - [ ] (2) **빈 SEARCH 차단** — 모든 patch에 대해 `if not patch["search"]: raise PatchApplyError("empty SEARCH not allowed in " + patch["file"])`. ambiguous 극단 형태로 매칭 위치 결정 불가. 빈 REPLACE는 검사 안 함 (코드 삭제 의도 허용)
  - [ ] (3) dry-run — 각 파일을 `Path.read_text(encoding="utf-8")`로 **한 번**만 read (R-001 P-ENCODING 준수, 누락 시 review-code P0) → 두 dict에 결과 보존: `originals: {path: original_text}`(백업, IO 0회 추가), `mutated: {path: new_content}`(in-memory 치환 결과 누적). 각 patch를 입력 순서대로 처리: SEARCH 검사는 **`mutated[path].count(search)`** 기준 (이전 patch 적용 결과 위에서 검색 — 순서 의존 가시화). `count == 0` 시 `PatchApplyError("search not found in " + file)`, `count > 1` 시 `PatchApplyError("ambiguous match: search appears " + N + " times in " + file)` (unique-match 정책 — 다중 매치는 모호성 차단). 통과 시 `mutated[path] = mutated[path].replace(search, replace, 1)` 누적. **`originals`는 commit 단계의 백업 전용**, dry-run의 SEARCH 검색에는 사용 X
  - [ ] (4) commit — dry-run 통과 후, 이미 `originals` dict가 채워진 상태(별도 read 없음). 각 파일에 `mutated[path]`를 `Path.write_text(content, encoding="utf-8")`로 write (R-001 P-ENCODING 준수). write IO 실패 시 `originals` dict의 백업으로 복원 (`write_text(originals[path], encoding="utf-8")`) + `PatchApplyError("io error on " + file + ": " + str(exc))`. **백업은 dry-run 단계의 `originals`를 그대로 재사용 — 별도 read 0회**
- [ ] 외부 인터페이스: `try: ...; return ("ok", None, files_changed)` / `except PatchApplyError as exc: return ("failed", str(exc), [])`
- [ ] `tests/test_patch_apply.py` 신규 — 11 케이스 작성 (TO-BE §3.2 함수 11개 1:1, extract 4 + apply 7)
- [ ] `pytest tests/test_patch_apply.py -q` pass

## 5. 검증

- `python -c "from src.patch_apply import extract_patches, apply_patches, validate_patch_path, PatchApplyError"` import smoke 성공.
- `pytest tests/test_patch_apply.py -q` 11 케이스 pass.
- 정규식 검증: `extract_patches` happy path 출력 dict가 protocol.md §2 line 86 형식과 1:1 일치 (`{"file":..., "search":..., "replace":...}` 키 3개).
- traversal 차단 검증: `apply_patches([{"file":"../foo","search":"x","replace":"y"}], tmp_path)` 호출 결과 `("failed", "path outside workdir: ../foo", [])` 또는 그 의미적 동치.
- all-or-nothing 검증: 두 파일 patch 중 한 파일의 SEARCH가 미일치할 때, 일치하는 다른 파일의 디스크 내용이 변경되지 않음을 `Path.read_text()` 비교로 확인.

## 6. 엣지케이스 / 위험 (Phase 한정)

- **정규식 그리디 매칭** (01-plan.md §5.3 위험 대응): `.+?` non-greedy + `re.DOTALL` 사용. 다중 블록 케이스(`test_extract_multiple_blocks`)에서 첫 블록의 `>>>>>>> REPLACE`까지만 매칭됨을 검증.
- **빈 SEARCH / 빈 REPLACE**: 마커 사이 본문이 빈 문자열인 case의 정책 — **빈 SEARCH는 PatchApplyError("empty SEARCH not allowed in <file>") 차단** (어떤 위치 매칭도 결정 불가, ambiguous의 극단 형태). **빈 REPLACE는 허용** (driver가 명시적으로 코드 삭제 의도). subagent 자율 영역 X — 정책 명시. §3.1 spec docstring (2) 단계 + §3.2 `test_apply_empty_search_blocked` + §4 작업 단위 (2)에 모두 반영 (P1-X4 fix).
- **CRLF vs LF**: workdir 파일이 CRLF로 저장된 경우 SEARCH 매칭 실패 가능. 본 plan은 LF 가정 (Linux/WSL 기준). CRLF 정규화는 별도 plan으로 deferred — `apply_error` 메시지에 "search not found in <file>"이 자연 표시되어 driver가 다음 턴에 자가 수정.
- **R-001 encoding="utf-8" 위반**: validation.md §2 R-001은 모든 `read_text`/`write_text`/`open` 호출에 `encoding="utf-8"` 명시 필수 (위반 P0, review-code 차단). 본 모듈이 신규 파일 read/write를 도입하므로 작업 단위 (2)·(3) 모두 명시. 누락 시 한국어 코드베이스 patch 시 UnicodeDecodeError → all-or-nothing 트랜잭션 실패로 포장되어 driver가 원인 오인 가능.
- **공백 포함 파일 경로 비지원**: `_PATCH_PATTERN` `\S+`는 공백 미허용 — driver가 `FILE: my file.py` 출력 시 `my`만 매칭되어 SEARCH 단계에서 "search not found in my" 오류로 환원. 본 도구 사용 사례(Python 코드베이스, snake_case)에서는 발생 0이지만 향후 `<path with space>` 인용 형식 도입은 별도 plan으로 deferred.
- **symlink escape (Linux)**: `Path.resolve()`은 symlink 해소 후 검사하므로 `workdir/link → /etc`이라도 차단됨. WSL 기준 검증 충분, Windows native는 Phase 외.
- **multi-patch same-file 순서**: 같은 파일에 2개 patch 모두 적용 시 첫 patch가 두번째 SEARCH의 매칭 텍스트를 변경할 수 있음. dry-run 단계에서 in-memory 누적 치환으로 검증 (작업 단위 (2)). 그래도 driver가 의도하지 않은 순서 의존 case는 driver self-check 책임.
- **백업 복원 실패**: commit 단계 IO 실패 시 백업으로 write 복원도 IO 실패할 가능성 (디스크 fall, permission). best-effort — `try: restore; except: stderr.write` 패턴. apply_error에 "io error on X (rollback also failed: Y)" 합성. 사용자가 workdir 점검 필요 (복원 불가).
- **Phase A 미통합**: 본 Phase는 `src/schema.py`를 import하지 않음 — A·B 병렬 시 의존 0. `apply_patches` 반환 튜플이 Phase C에서 Meta 필드로 매핑됨 (분리 책임).
