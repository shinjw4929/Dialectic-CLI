# patch-apply (ADR-10 search-replace 메커니즘)

`src/patch_apply.py` (~177 LOC) 진리문서. ADR-10 (Q22 ✅ A2): driver 응답에 `FILE: <path>` + `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` 텍스트 블록 → orchestrator가 정규식 추출 후 workdir 파일에 안전 적용.

## 공개 인터페이스

| 함수/예외 | 시그니처 | 책임 |
|---|---|---|
| `validate_patch_path` | `(workdir: Path, file: str) -> Path` | `cwd-isolation.md §Layer 4` SSOT 정통 구현. Path 정규화 + workdir 부모 검사. 외부면 `PatchApplyError("path outside workdir: <file>")` |
| `extract_patches` | `(text: str) -> list[dict[str, str]]` | `_PATCH_PATTERN` 정규식 finditer로 search-replace 블록 추출. 각 dict `{"file","search","replace"}`. 매칭 0이면 `[]` |
| `apply_patches` | `(patches: list[dict], *, workdir: Path) -> tuple[str, str \| None, list[str]]` | all-or-nothing 트랜잭션 적용. `(status, error, files_changed)` — status `"ok"` / `"failed"` |
| `PatchApplyError` | (Exception) | 내부 시그널. `apply_patches` 외부에는 (status, error, files_changed) 튜플로 환원 |

`apply_patches`는 keyword-only `workdir` (`patches, *, workdir`) — 인자 순서 의존 차단 (code-conventions §5).

## `_PATCH_PATTERN` 정규식 (ADR-10 마커 1:1)

```python
_PATCH_PATTERN = re.compile(
    r"FILE:\s*(?P<file>\S+)\s*\n"
    r"(?:`{3}[^\n]*\n)?"
    r"<{7}\s*SEARCH\s*\n"
    r"(?:(?P<search>.+?)\n)?"
    r"={7}\s*\n"
    r"(?:(?P<replace>.+?)\n)?"
    r">{7}\s*REPLACE",
    re.DOTALL,
)
```

- 마커 카운트 7-character (`<<<<<<<` / `=======` / `>>>>>>>`) — `protocol.md §2:86` + `roles/implementer.md:78` 1:1, 변형 금지.
- named groups (`file` / `search` / `replace`) — `protocol.md §2:86` patches dict 키와 1:1. `extract_patches`에서 `match.group("search") or ""`로 None→"" 변환 (신규 파일 fence는 search 그룹 미캡처 → None 반환됨).
- **빈 SEARCH alternation** `(?:(?P<search>.+?)\n)?` — 신규 파일 의도(`<<<<<<< SEARCH\n=======\n` 직접 인접) 매칭. plan 014 Phase D end-to-end 보강(이전 정규식은 `\n={7}` 강제로 빈 SEARCH 매칭 0건 → driver 신규 파일 fence가 silent 0건 추출됨).
- **markdown fence wrapping 1단 허용** `(?:`{3}[^\n]*\n)?` — driver(LLM)가 ```` FILE:\n```\n<<<<<<< SEARCH ```` 형태로 fence 마커 외부에 markdown ` ``` ` 한 줄 끼워넣어도 흡수. 같은 fence wrapping이 REPLACE 끝에 있어도 `>{7}\s*REPLACE` 이후 무관(매칭 종료점 보존). plan 014 사용자 시연에서 발견된 driver 응답 패턴 — 셀프체크는 평문 우선이지만 정규식이 fallback으로 catch.
- non-greedy `.+?` + `re.DOTALL` — 한 응답에 다중 블록 매칭.
- `\S+` (file 경로) — 공백 포함 경로 비지원 정책. `FILE: my file.py` 같은 헤더는 패턴 매칭 실패 → 해당 블록 미포함 (silent 누락, driver self-check 책임). 향후 인용 형식(`FILE: "<path>"`)은 별도 plan으로 deferred.
- **driver self-check fallback**: `roles/implementer.md:78` 셀프체크가 강화된 형식 강제(신규 파일·기존 파일 둘 다 fence 형식 + FILE↔SEARCH 사이 markdown fence 금지). 그러나 driver가 형식 무시하고 단순 ` ```python ... ``` `만 응답하면 정규식 catch 불가 — `run_session` finally의 `files_changed=0 SystemExit`이 사용자 인지 통로.

## `apply_patches` 4 단계 (all-or-nothing)

```
(1) path validation — 모든 patch에 대해 validate_patch_path() 호출.
                     외부 1개라도 발견 시 PatchApplyError("path outside workdir").

(2) 빈 SEARCH 분기 (plan 014 Phase D 신규 파일 지원):
    - 파일 존재 + SEARCH="" → PatchApplyError("empty SEARCH not allowed in <file>")
                              (기존 정책 보존 — 적용 위치 모호)
    - 파일 부재 + SEARCH="" → 신규 파일 의도. (3) dry-run에서 originals=""/mutated=REPLACE
                              등록 + new_files set에 추가 (read 호출 X)
    - 파일 부재 + SEARCH 비어있지 X → (3) dry-run의 read에서 FileNotFoundError 또는
                                     count==0 흐름 (현 구현은 read 시점에서 raise)
    빈 REPLACE는 허용 (driver 명시적 코드 삭제 / 빈 신규 파일 의도).

(3) dry-run — 각 파일 한 번 read (기존 파일만, encoding="utf-8", R-001 P-ENCODING).
              originals: {path: original_text} (백업 전용. 신규 파일은 "")
              mutated:   {path: new_content} (in-memory 누적 치환)
              new_files: set[Path] (rollback unlink 식별용 — plan 014 Phase D)
              각 patch 입력 순서대로 처리:
                SEARCH="" + 신규 파일 → mutated[path] = REPLACE
                count = mutated[path].count(search)
                count==0 → PatchApplyError("search not found")
                count>1  → PatchApplyError("ambiguous match: ... N times")
                          (unique-match 정책 — 다중 매치 모호성 차단)
                통과 시 mutated[path] = mutated[path].replace(search, replace, 1)
              디스크 변경 0.

(4) commit — mutated[path]를 write_text(encoding="utf-8") (R-001 P-ENCODING).
             변경된 파일만 write (mutated != originals).
             신규 파일 (new_files 포함)은 resolved.parent.mkdir(parents=True, exist_ok=True) 후 write.
             write IO 실패 시 originals 백업으로 복원 (신규 파일은 unlink).
             복원 실패 시 stderr 경고 + apply_error에 합성 (best-effort).
```

## ADR-6 cwd 격리 보강 (§Layer 4)

`validate_patch_path` 시그니처는 `cwd-isolation.md:55-72` SSOT 1:1:
1. `Path(workdir).resolve() / Path(file)` 결합 → `.resolve()` 정규화 (symlink + 상대경로 해소)
2. `is_relative_to(workdir.resolve())` 검사
3. `strict=False` resolve로 symlink escape도 동일 prefix 검사
4. 외부면 `PatchApplyError("path outside workdir: " + file)`

→ ADR-6 cwd 격리(읽기 경계) 위에 **쓰기 경계** 보강. driver가 `FILE: ../etc/passwd` / 절대 경로 / symlink escape 시도 차단.

## 호출 위치 (orchestrator R2.6/R2.7)

```python
# src/orchestrator.py run_turn driver 분기
patches = extract_patches(resp1.text)
proposal_meta = dataclasses.replace(resp1.meta, patches=patches or None)
proposal = _msg(turn_id, 1, ..., meta=proposal_meta)
bus.append(proposal)

if patches:  # patches 0개면 R2.6/R2.7 skip
    status, error, files_changed = apply_patches(patches, workdir=workdir)
    summary = (f"apply_status=ok, files_changed={files_changed}"
               if status == "ok"
               else f"apply_status=failed, apply_error={error}")
    bus.append(_patch_applied_msg(
        turn_id, workdir, mode, summary,
        parent_id=proposal.msg_id,
        apply_status=status, apply_error=error, files_changed=files_changed,
    ))
```

`summary` prefix `apply_status=` 명시 — driver 다음 턴 prompt에서 `_serialize_history` system 분기로 `SYSTEM (patch_applied): apply_status=...` 직렬화. driver의 reviewer critique 오인 차단 mitigation (orchestrator.md §5.6 (2)).

## 검증 (단위 11 케이스 + 통합 2 케이스)

```bash
pytest tests/test_patch_apply.py -q                     # 11 케이스 (extract 4 + apply 6 + SSOT 1)
pytest tests/test_orchestrator_patch_integration.py -q  # 2 케이스 (happy + traversal failure)
```

`tests/test_orchestrator_patch_integration.py` happy 케이스는 `assert critique.seq_in_turn == 2` + `assert patch_applied.seq_in_turn == 98` + `assert patch_applied.content.startswith("apply_status=")` 3 mitigation 가드 포함.

## 변경 시 갱신 영향

| 코드 변경 | 갱신 대상 |
|---|---|
| `_PATCH_PATTERN` 정규식 | 본 §정규식 + `protocol.md §2:86` + `roles/implementer.md:78` |
| `apply_patches` 절차 (4 단계) | 본 §4 단계 + `protocol.md §4 R2.6` + `protocol.md §9` 실패 모드 표 |
| `validate_patch_path` 시그니처 | 본 §공개 인터페이스 + `cwd-isolation.md:55-72` SSOT (반드시 1:1) |
| 새 실패 모드 추가 | `protocol.md §9` 실패 모드 표 + 본 §4 단계 + 단위 테스트 |
| 마커 형식 변경 | 본 §정규식 + `protocol.md §2:86` + `roles/implementer.md:78` + `tests/test_patch_apply.py::test_extract_*` |

## 관련 문서

- `architecture.md` ADR-10 — search-replace 결정 정통
- `protocol.md §2:85-91` — `meta.patches` / `meta.apply_status` / `meta.apply_error` / `meta.files_changed` 스키마
- `protocol.md §4:226-248` — turn lifecycle R2 → R2.6 → R2.7 → R3 mermaid
- `protocol.md §9:359-361` — 실패 모드 (path outside / search not found / IO error)
- `cwd-isolation.md §Layer 4` — `validate_patch_path` SSOT
- `orchestrator.md §메시지 생성 헬퍼 5종` — `_patch_applied_msg` 정통
- `runtime-docs/systems/run-mode.md §2` — turn lifecycle mermaid에 R2.6/R2.7 통합
- `roles/implementer.md:78-80` — driver 셀프체크 마커 형식
