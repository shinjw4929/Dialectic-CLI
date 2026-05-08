# Phase C · Roles & Outputs — 004-modify-mechanism

## 0. 메타

- Phase ID: C
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: A (Q22 결정 텍스트 인용), **B (§2.2 `kind=patch_applied`/`apply_status`/`files_changed` 스키마를 §1.4 spec-reviewer 셀프체크에서 인용)**
- 병렬 그룹: — (B 완료 후 직렬 진입; B-D는 A 직후 병렬, C는 B 직후)
- 예상 LOC: ~30 줄 추가 / ~6 줄 변경 (`outline/01-harness-layers.md` + `outline/04-requirements-and-modes.md` 2 파일)

## 1. 목표

`outline/01-harness-layers.md` §1.3 cwd 시나리오 + §1.4 4 role 셀프체크에 search-replace 메커니즘을 반영. `outline/04-requirements-and-modes.md` §4.5.1, §4.5.3 산출물 정의를 "신규 작성 또는 search-replace 수정"으로 갱신. role 명세가 §2.2 스키마와 정합하게.

## 2. 입력

- AS-IS:
  - `outline/01-harness-layers.md:30-43` §1.3 cwd 격리 전체 (line 30=헤더, 32=위험 단락, 34=대응 헤더, 35-39=5 항목 리스트, 41=효과 헤더, 42-43=효과 본문 2 항목)
  - `outline/01-harness-layers.md:67-73` §1.4 implementer.md 셀프체크 5 항목 (line 73 = "1500자 이내인가" 마지막 항목)
  - `outline/01-harness-layers.md:75-84` §1.4 spec-reviewer.md 셀프체크 8 항목 (line 82 = regression 검사 항목, line 84 = "1500자 이내인가" 마지막)
  - `outline/04-requirements-and-modes.md:187` §4.5.1 run 모드 산출물 행 ("`<workdir>/<file>.py` (또는 task에 따라)")
  - `outline/04-requirements-and-modes.md:242` §4.5.3 implement 모드 산출물 행 ("`<workdir>/<file>.py` 등 코드")
- Phase A 산출물: Q22 결정 (search-replace 메커니즘)
- Phase B 산출물 (의존 명시됨, §0 참조): §2.2 `kind=patch_applied`, `meta.patches`/`apply_status`/`files_changed`

## 3. 출력

### 3.1 §1.3 본문 추가 (line 39 — 5 항목 리스트 끝 — 직후, line 41 "효과" 헤더 직전)

(line 39 = "5. **단위 테스트**: ..." 5 항목 리스트의 마지막. line 40 = 빈 줄. 신규 단락은 line 39 직후 빈 줄 + 본문 + 빈 줄 형태로 line 41 `**효과**:` 헤더 직전에 삽입.)

```markdown
# paste
**코드 수정 시 workdir 흐름 (Q22 ✅ A2 / ADR-10)**: `--workdir <path>`가 기존 코드 베이스를 가리키면, driver(implementer)는 워크디렉토리 파일을 **읽고** task/critique에 따라 search-replace 블록을 응답에 포함시켜 **수정 의도**를 표현한다. orchestrator가 §2.3 R2(추출) → R2.6(**all-or-nothing 트랜잭션** — 각 patch FILE 경로를 `Path.resolve()` 정규화 + workdir 내부 검사로 absolute path / `..` traversal / symlink escape 차단, 모든 SEARCH 정확 일치 검색 후 한 번에 REPLACE 치환) → R2.7(`kind=patch_applied` 기록) 흐름으로 파일을 실제 수정. 1개 patch라도 path 외부 또는 SEARCH 미일치 시 전체 롤백, `apply_status=failed`로 기록. 다음 턴 R3 reviewer prompt build 시점엔 변경된 파일(또는 롤백된 원본)이 재주입되어 reviewer가 일관된 상태를 critique. **임시 디렉토리 fallback(`tempfile.mkdtemp`) 시에는 modify 시나리오 사용 불가** — 빈 디렉토리에는 수정 대상 파일이 없어 SEARCH 미일치로 항상 실패. modify task 실행 시 `--workdir <기존 코드 경로>` 명시 필수. ADR-6 cwd 격리(읽기)에 R2.6의 쓰기 경계 검사가 보강.
```

### 3.2 §1.4 implementer.md 셀프체크 갱신 (line 67-73)

기존 5 항목 끝(line 73 "1500자 이내인가" 직전)에 3 항목 추가:

```markdown
# paste
- [ ] (코드 수정 시) search-replace 블록 형식 준수: `FILE: <path>` 헤더 + `<<<<<<< SEARCH` / `=======` / `>>>>>>> REPLACE` 마커 정확
- [ ] (코드 수정 시) SEARCH 블록은 workdir 파일에 정확히 일치하는 텍스트인가 (들여쓰기·공백·줄바꿈 포함, line number 의존 X)
- [ ] (코드 수정 시) 변경이 기존 함수 시그니처 / 호출 측 인터페이스를 깨지 않는가 (호환성 검증)
```

### 3.3 §1.4 spec-reviewer.md 셀프체크 강화 (line 82 regression 검사 행)

기존:
```
- [ ] **regression 검사**: 직전 턴 driver fix가 새 P0/P1을 도입했는지 검증 (N≥2일 때만)
```

→ 갱신 (forward reference §2.2):
```markdown
# paste
- [ ] **regression 검사**: 직전 턴 driver fix가 새 P0/P1을 도입했는지 검증 (N≥2일 때만). 코드 수정 턴이면 직전 `kind=patch_applied` 메시지의 `apply_status` + `files_changed`를 보고 변경된 파일의 신규 회귀 검사
```

### 3.4 §1.4 spec-reviewer.md 셀프체크 추가 항목 (line 84 "1500자 이내" 직전)

```markdown
# paste
- [ ] (직전 턴 `kind=patch_applied, apply_status=failed`인 경우) driver의 SEARCH 블록이 왜 미일치였는지 critique에 포함 (LLM 자가 진단)
```

### 3.5 §4.5.1 산출물 행 갱신 (line 187)

기존:
```
| 산출물 | `<workdir>/<file>.py` (또는 task에 따라) |
```

→ 갱신:
```markdown
# paste
| 산출물 | `<workdir>/<file>.py` (신규 작성) **또는** 기존 파일 search-replace 수정 (driver 응답의 patch 블록 → orchestrator R2.6/R2.7 적용 → `meta.files_changed` 기록, Q22 ✅ A2). §2.3 라이프사이클·§2.2 스키마 참조 |
```

### 3.6 §4.5.3 산출물 행 갱신 (line 242)

§4.5.1과 동일하게 갱신.

## 4. 작업 단위

- [ ] `outline/01-harness-layers.md` §1.3에 line 39 (5 항목 리스트 끝) 직후, line 41 "효과" 헤더 직전에 "코드 수정 시 workdir 흐름" 단락 추가 (§3.1)
- [ ] `outline/01-harness-layers.md` §1.4 implementer.md 셀프체크 line 73 "1500자 이내" 직전에 3 항목 추가 (§3.2)
- [ ] `outline/01-harness-layers.md` §1.4 spec-reviewer.md 셀프체크 line 82 regression 검사 행 갱신 (§3.3)
- [ ] `outline/01-harness-layers.md` §1.4 spec-reviewer.md 셀프체크 line 84 "1500자 이내" 직전에 1 항목 추가 (§3.4)
- [ ] `outline/04-requirements-and-modes.md` §4.5.1 산출물 행 갱신 (line 187, §3.5)
- [ ] `outline/04-requirements-and-modes.md` §4.5.3 산출물 행 갱신 (line 242, §3.6)

## 5. 검증

- `grep -n "search-replace" outline/01-harness-layers.md` — §1.3 + §1.4 implementer 양쪽에 등장
- `grep -n "patch_applied" outline/01-harness-layers.md` — §1.4 spec-reviewer regression 행 + 추가 항목에 등장
- `grep -n "files_changed\|search-replace" outline/04-requirements-and-modes.md` — §4.5.1 + §4.5.3 양쪽에 등장
- `grep -n "코드 수정 시" outline/01-harness-layers.md` — implementer 셀프체크 3 항목 prefix 확인 (정확 매칭)
- 사람 검토: §1.4 implementer 셀프체크의 "search-replace 블록 형식" ↔ §2.2 `meta.patches` 필드 ↔ §2.3 R2 노드 텍스트 (응답에서 patches 추출) + R2.6 apply_patches 메커니즘 명칭 일관 (R2_5 NO-OP 제거 정책 반영)

## 6. 엣지케이스 / 위험 (Phase 한정)

- **셀프체크 항목 prefix `(코드 수정 시)`** — 신규 파일 작성 turn에서는 이 항목들이 적용 안 됨. prefix를 명시해 implementer가 자가 판단하게.
- **§4.5.1 / §4.5.3 표 셀 줄바꿈** — markdown 표 셀 안에 `**또는**` 굵은 글씨 + 인용(`§2.3`) 들어감. 표 셀 한 줄로 길어짐 — GitHub 렌더에서 읽기 OK 확인 필요.
- **B 의존 명시 (§0)** — 00-plan.md §3.1 mermaid가 `A → B → C`로 갱신됨. execute-plan은 B 완료 후에만 C 진입. C가 B의 §2.2 스키마를 인용하는 항목들이 일관 보장.
- **planner.md / plan-reviewer.md 셀프체크는 변경 없음** — plan 모드는 spec.md 산출이라 코드 수정 메커니즘과 무관. 본 phase 스코프 외.
