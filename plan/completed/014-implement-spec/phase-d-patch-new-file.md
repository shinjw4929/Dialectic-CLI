# Phase D · apply_patches 신규 파일 지원 — 014-implement-spec

## 0. 메타

- Phase ID: D
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음) — A·D 병렬 가능. C가 본 phase 산출 의존
- 병렬 그룹: A·D
- 예상 LOC: ~30 (코드) + ~40 (테스트)

## 1. 목표

`src/patch_apply.py:apply_patches`에 **신규 파일 생성 분기** 추가 — `SEARCH=""` + 파일 부재 시 REPLACE 본문을 신규 파일로 write. `architecture.md:137` ADR-10 narrative "신규 파일·기존 파일 둘 다 동일 흐름"이 wiring으로 충족됨. `roles/implementer.md:78` 셀프체크에 신규 파일 형식 항목 추가. dijkstra 등 빈 workdir 시나리오가 `meta.apply_status="ok"`로 작동.

## 2. 입력

- [`src/patch_apply.py:97-99`](../../src/patch_apply.py) — 빈 SEARCH 차단 AS-IS (`PatchApplyError("empty SEARCH not allowed in <file>")`). 본 plan에서 분기 보강
- [`src/patch_apply.py:103-127`](../../src/patch_apply.py) — dry-run 단계 (originals/mutated 누적 치환 + count 검사). `read_text(:109)`가 FileNotFoundError raise 시 catch 0
- [`src/patch_apply.py:129-145`](../../src/patch_apply.py) — commit 단계 (write_text). 신규 파일은 parent dir mkdir 필요
- [`src/patch_apply.py:146-173`](../../src/patch_apply.py) — best-effort rollback. 신규 파일은 unlink 필요 (write_text(originals[resolved]) = write_text("") 시 빈 파일 잔재)
- [`docs/dev-docs/architecture.md:137`](../../docs/dev-docs/architecture.md) ADR-10 — narrative "신규 파일·기존 파일 둘 다 동일 흐름" SSOT
- [`docs/runtime-docs/roles/implementer.md:70-83`](../../docs/runtime-docs/roles/implementer.md) — 응답 전 셀프체크 항목 (`:78` search-replace 형식)
- 사전 검증 사실: `Path.exists()`는 `is_file()` + `is_dir()` 모두 True 반환 — 본 분기는 `not exists()` 즉 부재만 분기 진입
- 사전 검증 사실: `validate_patch_path` (`:90-93`)는 신규 파일에도 동작 (resolved 경로 검증은 부모 디렉토리 + workdir 부모 검사로 충분, 파일 자체 존재 X)

## 3. 출력

### 3.1 `src/patch_apply.py` `apply_patches` 신규 파일 분기

```python
# spec — 변경 위치: 기존 단계 (1)~(4) 흐름 보강

# (2) 빈 SEARCH 차단 → 분기 보강
for patch, resolved in zip(patches, resolved_paths):
    if not patch["search"]:
        if resolved.exists():
            # 기존 정책: 빈 SEARCH는 모호 (파일 어디에 적용할지 알 수 없음)
            raise PatchApplyError("empty SEARCH not allowed in " + patch["file"])
        # 신규 파일 의도 — 본 plan 추가 분기. (3) dry-run에서 처리

# (3) dry-run — 각 파일 한 번 read 또는 신규 파일 등록
originals: dict[Path, str] = {}
mutated: dict[Path, str] = {}
new_files: set[Path] = set()  # rollback unlink 식별용
for patch, resolved in zip(patches, resolved_paths):
    if resolved not in originals:
        if resolved.exists():
            # 기존 흐름
            original_text = resolved.read_text(encoding="utf-8")
            originals[resolved] = original_text
            mutated[resolved] = original_text
        else:
            # 신규 파일 분기 — SEARCH=""인 patch만 도달 (위 (2) 검증 정합)
            originals[resolved] = ""
            mutated[resolved] = ""
            new_files.add(resolved)

    search = patch["search"]
    current = mutated[resolved]
    if not search:
        # 신규 파일 + SEARCH="" — REPLACE를 그대로 mutated에 등록
        mutated[resolved] = patch["replace"]
        continue
    # 기존 흐름 (SEARCH 비어있지 X)
    count = current.count(search)
    if count == 0:
        raise PatchApplyError("search not found in " + patch["file"])
    if count > 1:
        raise PatchApplyError("ambiguous match: search appears " + str(count) + " times in " + patch["file"])
    mutated[resolved] = current.replace(search, patch["replace"], 1)

# (4) commit — 신규 파일은 parent mkdir 추가
written: list[Path] = []
files_changed: list[str] = []
try:
    for resolved in originals:
        if mutated[resolved] != originals[resolved]:
            if resolved in new_files:
                # 신규 파일 — parent mkdir 보장
                resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(mutated[resolved], encoding="utf-8")
            written.append(resolved)
            workdir_resolved = Path(workdir).resolve()
            try:
                rel = resolved.relative_to(workdir_resolved)
                files_changed.append(str(rel))
            except ValueError:
                files_changed.append(str(resolved))
except OSError as exc:
    # rollback — 신규 파일은 unlink, 기존 파일은 originals 복원
    rollback_failures: list[str] = []
    for resolved in written:
        try:
            if resolved in new_files:
                resolved.unlink()
            else:
                resolved.write_text(originals[resolved], encoding="utf-8")
        except OSError as restore_exc:
            rollback_failures.append(str(resolved) + ": " + str(restore_exc))
    # ... 기존 msg 환원 흐름 그대로
```

### 3.2 `roles/implementer.md:78` 셀프체크 항목 추가

```python
# spec — 기존 :78 다음 줄로 삽입 또는 동일 항목 보강
- [ ] (코드 수정 시) search-replace 블록 형식 준수: `FILE: <path>` 헤더 + `<<<<<<< SEARCH` / `=======` / `>>>>>>> REPLACE` 마커 정확 (ADR-10)
+ [ ] (신규 파일 생성 시) SEARCH 블록은 빈 문자열 (`<<<<<<< SEARCH\n=======\n` 사이 본문 0). REPLACE 블록에 신규 파일 전체 본문 (ADR-10 신규 파일 분기, plan 014)
+ [ ] (신규 파일 생성 시) `FILE: <path>`의 path는 workdir 기준 상대 경로 (`/`, `..` 시작 금지 — `validate_patch_path` 차단)
```

### 3.3 `docs/dev-docs/systems/patch-apply.md` narrative 보강

```
# spec — `apply_patches 4 단계` 단락에 신규 파일 분기 추가
(2) 빈 SEARCH 분기:
    - 파일 부재 + SEARCH="" → 신규 파일 의도. (3) dry-run에서 originals=""/mutated=REPLACE 등록 (read 호출 X), new_files set에 추가
    - 파일 존재 + SEARCH="" → 기존 정책 PatchApplyError ("empty SEARCH not allowed")
    - 파일 부재 + SEARCH 비어있지 X → PatchApplyError ("search not found")

(4) commit 신규 파일 처리:
    - resolved.parent.mkdir(parents=True, exist_ok=True) 호출 후 write_text
    - rollback: 신규 파일은 unlink, 기존 파일은 originals 복원 (분기 식별 = new_files set)
```

### 3.4 신규 단위 테스트 — `tests/test_patch_apply.py` 확장

```python
# spec — Phase D 케이스 (≥4)
def test_apply_patches_new_file_basic(tmp_path):
    """SEARCH="" + 파일 부재 → REPLACE를 신규 파일로 write."""
    patches = [{"file": "new.py", "search": "", "replace": "def f(): pass\n"}]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)
    assert status == "ok"
    assert files_changed == ["new.py"]
    assert (tmp_path / "new.py").read_text(encoding="utf-8") == "def f(): pass\n"

def test_apply_patches_new_file_with_subdir(tmp_path):
    """SEARCH="" + path with subdir → parent mkdir + write."""
    patches = [{"file": "pkg/mod.py", "search": "", "replace": "x = 1\n"}]
    status, _, files_changed = apply_patches(patches, workdir=tmp_path)
    assert status == "ok"
    assert (tmp_path / "pkg" / "mod.py").exists()
    assert "pkg/mod.py" in files_changed

def test_apply_patches_new_and_existing_mixed(tmp_path):
    """한 응답에 신규 파일 + 기존 파일 patch 혼합."""
    (tmp_path / "old.py").write_text("def old(): return 1\n", encoding="utf-8")
    patches = [
        {"file": "new.py", "search": "", "replace": "def new(): pass\n"},
        {"file": "old.py", "search": "return 1", "replace": "return 2"},
    ]
    status, _, files_changed = apply_patches(patches, workdir=tmp_path)
    assert status == "ok"
    assert set(files_changed) == {"new.py", "old.py"}
    assert (tmp_path / "new.py").read_text(encoding="utf-8") == "def new(): pass\n"
    assert (tmp_path / "old.py").read_text(encoding="utf-8") == "def old(): return 2\n"

def test_apply_patches_existing_file_empty_search_rejected(tmp_path):
    """기존 정책 보존 — 파일 존재 + SEARCH="" → PatchApplyError."""
    (tmp_path / "x.py").write_text("body", encoding="utf-8")
    patches = [{"file": "x.py", "search": "", "replace": "new body"}]
    status, error, _ = apply_patches(patches, workdir=tmp_path)
    assert status == "failed"
    assert "empty SEARCH not allowed" in error

def test_apply_patches_new_file_rollback_unlink(tmp_path, monkeypatch):
    """신규 파일 commit 후 후속 patch 실패 → 신규 파일 unlink (rollback 정합).

    patch 2건: 첫 신규 파일 정상 → 두 번째에서 OSError mock 발생 →
    rollback 시 첫 신규 파일이 disk에 남아있지 않은지 검증.
    """
    patches = [
        {"file": "new.py", "search": "", "replace": "def f(): pass\n"},
        {"file": "broken.py", "search": "", "replace": "raise"},
    ]
    # commit 단계 두 번째 write_text에서 OSError 유발 (monkeypatch)
    # ... mock detail은 execute-plan 시 결정, 핵심은 rollback 후 (tmp_path / "new.py") not exists
    # status == "failed" 가정, (tmp_path / "new.py").exists() is False 단언
```

총 ≥5 케이스 (basic / subdir / mixed / existing-file-rejected / rollback unlink). DoD 4 케이스(`01-plan.md §6 :297`)에 정책 보존 1건 추가 — 합 ≥5.

## 4. 작업 단위

- [ ] (Pre-execute) `grep -n "PatchApplyError\|read_text\|write_text\|mutated\[resolved\]\|originals\[resolved\]" src/patch_apply.py`로 본 phase 인용 줄 재확인
- [ ] `src/patch_apply.py` (2) 빈 SEARCH 차단 분기 보강 — 파일 부재 시 신규 파일 의도로 (3) dry-run 위임
- [ ] `src/patch_apply.py` (3) dry-run 단계 — `resolved.exists()` 분기 추가 + `new_files: set[Path]` 추적
- [ ] `src/patch_apply.py` (3) `if not search:` 분기 — 신규 파일 SEARCH="" 처리 (mutated[resolved] = patch["replace"])
- [ ] `src/patch_apply.py` (4) commit — 신규 파일 시 `resolved.parent.mkdir(parents=True, exist_ok=True)` 호출
- [ ] `src/patch_apply.py` (4) rollback — `if resolved in new_files: resolved.unlink()` 분기 추가
- [ ] `docs/runtime-docs/roles/implementer.md:78~80` 셀프체크 항목 보강 (위 §3.2 spec)
- [ ] `docs/dev-docs/systems/patch-apply.md` `apply_patches 4 단계` 단락 갱신 (위 §3.3 spec)
- [ ] `tests/test_patch_apply.py`에 신규 파일 케이스 4건 추가 (위 §3.4 spec)
- [ ] `pytest -q tests/test_patch_apply.py` 전체 회귀 0 (기존 cases + 신규 4건 모두 pass)
- [ ] `pytest -q tests/test_orchestrator_patch_integration.py` 회귀 0 (R2.6/R2.7 기존 동작 보존)

## 5. 검증

- `python3 -c "from src.patch_apply import apply_patches; from pathlib import Path; import tempfile; w = Path(tempfile.mkdtemp()); s, _, fc = apply_patches([{'file': 'x.py', 'search': '', 'replace': 'print(1)\n'}], workdir=w); print(s, fc); print((w / 'x.py').read_text())"` → `ok ['x.py'] print(1)` 출력
- `pytest -q tests/test_patch_apply.py` Phase D 신규 4건 + 기존 모두 pass
- `pytest -q tests/test_orchestrator_patch_integration.py` 회귀 0
- ADR-10 narrative cross-check — `architecture.md:137` "신규 파일·기존 파일 둘 다 동일 흐름" wiring 충족 (narrative 변경 X)

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **신규 파일 + 기존 파일 같은 응답 — 입력 순서 의존**
   - 신규 파일 patch가 먼저 처리 → originals/mutated 등록 → 기존 파일 patch 처리 → 둘 다 ok
   - 반대 순서 동일 — 입력 순서대로 처리, 동일 파일 multi-patch만 순서 의존 (`patch_apply.py:106` narrative)
   - **mitigation**: §3.4 test_apply_patches_new_and_existing_mixed로 검증

2. **신규 파일 path traversal — `validate_patch_path` 차단 정합**
   - `FILE: ../etc/passwd` 같은 시도 → `validate_patch_path`가 PatchApplyError raise (`:90-93`)
   - 본 plan 변경 0 — 기존 차단 그대로 신규 파일에도 적용 ✓

3. **신규 파일 parent dir 권한 부족**
   - `mkdir(parents=True, exist_ok=True)`가 PermissionError raise → commit 단계 OSError catch 진입 → rollback (신규 파일 unlink)
   - mkdir 자체 실패 시 written 비어 있음 → unlink 0건. PatchApplyError 환원 OK
   - **mitigation**: 1차 plan 외 (사용자 권한 이슈는 명확한 traceback)

4. **rollback 시 신규 파일 unlink — 부분 mkdir된 디렉토리 잔재**
   - `mkdir(parents=True)`로 만든 부모 디렉토리는 unlink 시 삭제 X (파일만 삭제)
   - 빈 디렉토리 잔재 — 기능 영향 0이지만 cleanup 깔끔함 ↓
   - **mitigation**: 본 plan 외. 향후 plan 016에서 디렉토리 cleanup 정책 결정

5. **같은 파일에 신규 patch + 후속 SEARCH patch 혼합**
   - 첫 patch SEARCH="" + REPLACE="def f(): pass\n" → mutated[resolved] = "def f(): pass\n"
   - 두 번째 patch SEARCH="def f(): pass" + REPLACE="def f():\n    return 1" → mutated count==1 → 정상 치환
   - 동작 정합 — 같은 응답 내 신규 파일 작성 후 즉시 수정 가능
   - **mitigation**: 1차 plan 외 (테스트 ≥1 추가 권고, optional)

6. **빈 REPLACE + SEARCH="" — 빈 신규 파일 생성**
   - `mutated[resolved] = ""` (REPLACE="") → write_text("") → 빈 파일 생성
   - 기능 정합이지만 의미 모호 (빈 파일을 왜 만드는가?)
   - 1차 plan은 차단 안 함 — driver 의도 존중. 향후 driver self-check (implementer.md `:78`)에서 권고

7. **driver가 `SEARCH=""`로 기존 파일 의도 명시 시 (사용자 실수)**
   - 본 plan 분기: 파일 존재 시 PatchApplyError("empty SEARCH not allowed") — 기존 정책 보존
   - driver self-check (implementer.md `:78`) 항목으로 차단 (신규 파일은 부재 명시)
   - 사용자 실수면 reviewer P0 지적 대상
