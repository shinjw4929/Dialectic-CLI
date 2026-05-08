# Phase B · Schema & Lifecycle — 004-modify-mechanism

## 0. 메타

- Phase ID: B
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: A (Q22 결정 텍스트가 §6에 도장된 후 인용 + ADR-10이 architecture.md에 박힌 후 protocol.md cascade)
- 병렬 그룹: B-D 병렬 (C는 B 완료 후 직렬 진입)
- 예상 LOC: ~70 줄 추가 / ~7 줄 변경 (`outline/02-communication.md` + `docs/runtime-docs/protocol.md` 2 파일)

## 1. 목표

`outline/02-communication.md` §2.2 메시지 스키마 + §2.3 턴 라이프사이클 + §2.8 실패 모드를 search-replace 메커니즘에 정합하게 갱신. orchestrator가 patch 추출·적용·기록·실패 피드백을 수행하는 흐름을 명세화.

## 2. 입력

- AS-IS:
  - `outline/02-communication.md:44-73` §2.2 메시지 스키마 JSONC 블록 (`kind` enum 6개, `meta` 필드 11개)
  - `outline/02-communication.md:84-113` §2.3 턴 라이프사이클 mermaid (R0~R6 노드)
  - `outline/02-communication.md:218-227` §2.8 실패 모드 표 6행
  - `docs/runtime-docs/protocol.md:52` §2 메시지 스키마 헤더, `:67` `kind` enum 6개, `:216` §4 한 턴의 라이프사이클 헤더, `:223` mermaid R2 노드, `:230` 화살표 (R2 → R3 직결)
- Phase A 산출물: `outline/README.md` §6 Q22 결정 텍스트 + `docs/dev-docs/architecture.md` ADR-10 행 (인용 출처)
- 결정 사실:
  - 신규 `kind` 값 = `patch_applied`
  - 신규 `meta` 필드: `patches: [{file, search, replace}]`, `apply_status: "ok" | "failed"` (**all-or-nothing 채택**, `partial` 폐기), `apply_error: str|null`, `files_changed: [str]` (성공 시 적용된 파일 리스트, 실패 시 빈 리스트)
  - 라이프사이클 단계: R2(driver subprocess + 응답에서 patches 추출 + kind=proposal append) → R2.6(apply_patches: **all-or-nothing**, 1개라도 실패 시 전체 롤백) → R2.7(append kind=patch_applied) → 기존 R3(reviewer prompt build). patches 추출은 R2 메시지 append와 동시.
  - **path 안전성**: 각 patch의 `FILE: <path>` 경로를 `Path(workdir).resolve() / Path(file).resolve()`로 정규화 + workdir 내부인지 검사 (absolute path / `..` traversal / symlink escape 차단). 외부 경로 1개라도 발견 시 즉시 `apply_status="failed"` (R2.6 진입 전 차단). ADR-6 cwd 격리의 **쓰기 경계** 보강.
  - 실패 시: SEARCH 미일치 또는 path traversal → `apply_status="failed"`, `apply_error="search not found in <file>"` 또는 `"path outside workdir: <file>"` → 다음 턴 prompt R1 build에 피드백 주입 (driver 재시도)
  - **protocol.md cascade**: outline §2.2 + §2.3 변경과 동일 내용을 `docs/runtime-docs/protocol.md` §2(line 67 `kind` enum + meta 필드) + §4(line 223 R2 노드, line 230 화살표)에 동시 반영 — runtime SSOT 일관성 (Documentation-Checklist §1.7 ADR 정통)

## 3. 출력

### 3.1 §2.2 JSONC 블록 갱신 (line 44-73)

```jsonc
# spec
"kind": "proposal",            // task | proposal | critique | decision | error | meta | patch_applied
                                // ↑ patch_applied 추가
"meta": {
  // 기존 필드 모두 유지
  "vendor": "...",
  ...,
  "is_mock": false,
  // === 추가 필드 (search-replace 메커니즘, Q22 ✅ A2) ===
  "patches": [                  // kind=proposal일 때, driver 응답 텍스트에서 추출한 search-replace 블록을 메시지 append와 동시에 기록 (사후 보강 X — JSONL append-only 원칙 P-JSONL 준수). 응답에 patch 블록 없으면 빈 리스트 [] 또는 null
    {"file": "wave_difficulty.py", "search": "...", "replace": "..."}
  ],
  "apply_status": "ok",         // kind=patch_applied일 때만: "ok" | "failed" (all-or-nothing 채택, partial 폐기)
  "apply_error": null,          // apply_status=failed 시 사유 (예: "search not found in wave_difficulty.py", "path outside workdir: ../etc/passwd")
  "files_changed": ["wave_difficulty.py"]  // apply_status=ok 시 적용된 파일 리스트, failed 시 빈 리스트 [] (롤백되어 실 변경 0)
}
```

§2.2 부가 필드 타당성 목록(line 75-80)에 행 추가:
```markdown
# paste
- `kind=patch_applied` + `meta.apply_status` → search-replace 적용 성공/실패 명시. 실패 시 `apply_error`가 다음 턴 prompt 피드백으로 재주입 → driver 재시도 (Q22 ✅ A2)
- `meta.patches` (kind=proposal) ↔ `meta.files_changed` (kind=patch_applied) → 의도된 수정과 실제 적용 결과 1:1 추적. **append-only 일관**: orchestrator는 driver subprocess 응답을 받으면 (1) 응답 텍스트에서 patch 블록 추출, (2) `meta.patches`를 채운 단일 `kind=proposal` 메시지를 append, (3) 별도로 `kind=patch_applied` 메시지 append. 기존 메시지의 meta 사후 수정 없음 (P-JSONL)
```

### 3.2 §2.3 턴 라이프사이클 mermaid 갱신 (line 84-113)

기존 R2 → R3 직결을 R2 → R2.6 → R2.7 → R3로 변경. R2 노드 텍스트는 patches 추출 명시로 갱신 (R2_5 NO-OP 노드는 제거 — patches 추출은 R2 메시지 append와 동시이라 별도 단계 두지 않음). mermaid 노드 추가 (펜스 안 본문만 옮기고 `# paste` 라벨 주석은 제외):

```mermaid
# paste
R2["**2.** subprocess: codex exec --json<br/>cwd = resolved_workdir (§1.3)<br/>응답 텍스트에서 patches 추출<br/>append messages.jsonl<br/>kind=proposal, slot=driver, meta.patches=[...]"]
R2_6["**2.6.** apply_patches(workdir) — all-or-nothing<br/>각 patch FILE 경로를 workdir 내부로 강제<br/>(Path.resolve() + 외부 경로 차단)<br/>각 patch의 SEARCH를 파일에서<br/>정확 일치 검색 → REPLACE 치환<br/>1개라도 실패 시 전체 롤백"]
R2_7{"**2.7.** apply 성공?"}
R2_7a["**2.7a.** append kind=patch_applied<br/>apply_status=ok, files_changed=[...]"]
R2_7b["**2.7b.** append kind=patch_applied<br/>apply_status=failed, apply_error=...<br/>(다음 턴 R1 prompt에 피드백 주입)"]
R3["**3.** build_prompt(slot=reviewer)<br/>변경된 파일 내용 재주입"]

R2 --> R2_6 --> R2_7
R2_7 -- yes --> R2_7a --> R3
R2_7 -- no --> R2_7b --> R3
```

본문에 1단락 추가 (mermaid 직후):
```markdown
# paste
**R2.6~R2.7 (Q22 ✅ A2 / ADR-10)**: driver 응답이 코드 수정을 포함하면 텍스트 본문에 `FILE: <path>` 헤더 + `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` 블록이 들어 있다. R2 단계에서 응답 처리 시 정규식으로 patches를 추출해 `meta.patches`에 함께 기록(append-only 일관, P-JSONL). R2.6는 **all-or-nothing 트랜잭션** — (1) 각 patch의 `FILE` 경로를 `Path.resolve()`로 정규화 + `resolved_workdir` 내부인지 검사, 외부 경로 1개라도 발견 시 즉시 실패(ADR-6 cwd 격리의 쓰기 경계 보강); (2) 각 SEARCH를 workdir 파일에서 정확 일치로 검색, 1개라도 미일치 시 실패; (3) 모든 검사 통과 시 한 번에 REPLACE 치환. R2.7에서 결과를 `kind=patch_applied`로 별도 append (성공: `apply_status=ok, files_changed=[...]` / 실패: `apply_status=failed, apply_error=..., files_changed=[]`). 실패 시 다음 턴 driver R1 prompt에 `apply_error`를 피드백으로 주입 — driver 재시도. R3 reviewer prompt build 시점에는 변경된 파일 내용(또는 롤백된 원본)이 workdir에 반영되어 있어 reviewer는 항상 일관된 상태를 본다.
```

### 3.3 §2.8 실패 모드 표 갱신 (line 220-227)

표 끝에 3 행 추가 (all-or-nothing 트랜잭션 — partial 폐기, 모두 failed로 통합):
```markdown
# paste
| Patch SEARCH 미일치 | apply_status=failed 기록, 전체 롤백, 다음 턴 driver R1 prompt에 `apply_error` 피드백 주입 후 재시도 | `kind=patch_applied, apply_status=failed, apply_error="search not found in <file>", files_changed=[]` |
| Patch FILE 경로가 workdir 외부 (absolute path / `..` traversal / symlink escape) | R2.6 진입 직전 차단, apply_status=failed 기록 (ADR-6 cwd 격리 쓰기 경계) | `kind=patch_applied, apply_status=failed, apply_error="path outside workdir: <file>", files_changed=[]` |
| Patch REPLACE 적용 중 파일 IO 실패 (권한·디스크) | 이미 부분 적용된 patch 롤백 시도 후 apply_status=failed (best-effort 롤백, 실패 시 stderr 경고 + 사용자 보고) | `kind=patch_applied, apply_status=failed, apply_error="io error on <file>: <errno>", files_changed=[]` |
```

## 4. 작업 단위

### 4.1 outline/02-communication.md 갱신
- [ ] §2.2 JSONC 블록의 `"kind":` 라인을 `"kind": "proposal", // task | proposal | critique | decision | error | meta | patch_applied` 로 갱신
- [ ] §2.2 JSONC 블록의 `"meta": {` 블록 끝 (`is_mock` 직후)에 `patches`/`apply_status`/`apply_error`/`files_changed` 4 필드 추가 (apply_status enum = `"ok" | "failed"`만, partial 폐기)
- [ ] §2.2 부가 필드 타당성 bullet 목록에 2 행 추가 (P-JSONL append-only 일관 명시 포함)
- [ ] §2.3 mermaid에서 기존 R2 노드 텍스트를 §3.2의 새 텍스트("응답 텍스트에서 patches 추출 / kind=proposal, slot=driver, meta.patches=[...]")로 갱신
- [ ] §2.3 mermaid에 R2_6/R2_7/R2_7a/R2_7b 4 노드 추가 (R2_6 노드 텍스트에 path resolve + workdir 내부 검사 + all-or-nothing 명시), 기존 R2→R3 화살표 제거 + 새 화살표 R2→R2_6→R2_7→{R2_7a,R2_7b}→R3 추가
- [ ] §2.3 mermaid에서 기존 R3 노드 텍스트를 §3.2의 새 텍스트("build_prompt(slot=reviewer) / 변경된 파일 내용 재주입")로 갱신
- [ ] §2.3 mermaid 직후 단락 추가 (R2.6~R2.7 흐름 설명, all-or-nothing + path 검증 명시)
- [ ] §2.8 실패 모드 표에 3 행 추가: "Patch SEARCH 미일치", "Patch FILE 경로 workdir 외부", "Patch REPLACE IO 실패" (모두 apply_status=failed, partial 폐기 반영)

### 4.2 docs/runtime-docs/protocol.md cascade (ADR-10 정합성)
- [ ] protocol.md line 67 `"kind"` enum 행에 `patch_applied` 추가 (outline §2.2와 1:1 일치)
- [ ] protocol.md §2 메시지 스키마 본문에 `meta.patches`/`apply_status`/`apply_error`/`files_changed` 4 필드 추가 (outline §2.2 신규 필드와 1:1)
- [ ] protocol.md `### kind 값별 의미` 섹션(line 104-)에 `patch_applied` 항목 추가
- [ ] protocol.md line 223 R2 노드 텍스트 갱신 (outline §2.3 R2와 일치 — patches 추출 명시)
- [ ] protocol.md line 230 화살표를 `R0 → R1 → R2 → R2_6 → R2_7 → {R2_7a, R2_7b} → R3 → ...`로 갱신 (R2_6/R2_7/R2_7a/R2_7b 4 노드 추가, R2 → R3 직결 제거)
- [ ] protocol.md §9 실패 모드(line 333-)에 outline §2.8과 동일한 3 행 추가

## 5. 검증

### 5.1 outline/02-communication.md 검증
- `grep -n "patch_applied" outline/02-communication.md` — §2.2 kind enum, §2.2 부가 필드, §2.3 mermaid, §2.8 표 4곳 이상 등장
- `grep -n "apply_status" outline/02-communication.md` — §2.2 + §2.8 양쪽에 등장
- `grep -n "R2_6\|R2_7" outline/02-communication.md` — mermaid 노드 정의 + 화살표
- `grep -n "all-or-nothing\|workdir 내부\|path outside" outline/02-communication.md` — R2.6 노드 + §2.8 표에 path 검증 + 트랜잭션 명시 확인
- `grep -c "partial" outline/02-communication.md` — 0건 (partial 폐기 검증)
- mermaid 렌더링: R0~R6 + R2_6/R2_7/R2_7a/R2_7b (R2_5 없음)
- §2.2 `meta.patches` ↔ §2.3 R2 노드 + R2.6 apply_patches ↔ §2.8 3 행 — 메커니즘 명칭 일관

### 5.2 protocol.md cascade 검증
- `grep -n "patch_applied" docs/runtime-docs/protocol.md` — §2 kind enum + §2 본문 + §kind 값별 의미 + §4 mermaid + §9 실패 모드 5곳 이상
- `grep -n "R2_6\|R2_7" docs/runtime-docs/protocol.md` — §4 mermaid 노드 + 화살표
- outline/02-communication.md ↔ protocol.md kind enum 1:1 diff 검증 (둘 다 7개 값으로 동일)
- outline/02-communication.md ↔ protocol.md mermaid R2/R2_6/R2_7 노드 텍스트 1:1 일치

## 6. 엣지케이스 / 위험 (Phase 한정)

- **mermaid 노드 ID 충돌** — 기존 mermaid가 `R0~R6`, `R4a~R4d`, `R5a~R5b` 사용. `R2_6`/`R2_7`/`R2_7a`/`R2_7b`는 충돌 없음. underscore 표기 통일 (mermaid가 dot 비허용 케이스 회피).
- **JSONC 블록 들여쓰기** — 기존 `meta` 필드들이 2-space 들여쓰기. 추가 필드도 2-space 유지.
- **실패 모드 표 너무 길어짐** — 기존 6행 + 신규 2행 = 8행. 가독성 OK. 9행 넘어가면 §2.8 안에 sub-section 분리 검토 (현 plan 스코프 외).
- **all-or-nothing 트랜잭션 (partial 폐기)** — 여러 patch 일부 적용 후 실패 시 partial 상태가 JSONL ↔ 실 파일 정합성을 깨뜨리는 risk를 차단하기 위해 partial 폐기. R2.6는 (1) 모든 patch path 검사, (2) 모든 SEARCH 검색, (3) 모두 통과 시 한 번에 REPLACE를 원자적으로 적용. 실패 시 부분 적용된 변경은 best-effort 롤백 (백업 파일 또는 인메모리 원본 복원). 롤백 자체 실패 시 stderr 경고 + 사용자 보고. apply_status enum은 `ok`/`failed` 2 값만.
- **path 안전성 (cwd 격리 쓰기 경계)** — driver 응답에 `FILE: ../etc/passwd` 또는 `FILE: /tmp/foo` 같은 외부 경로가 들어올 위험. R2.6 진입 전 `Path(workdir).resolve()` ↔ `Path(file).resolve()` `is_relative_to` 또는 prefix 검사로 차단. symlink escape도 `Path.resolve(strict=False)` 후 동일 검사. 위반 시 즉시 `apply_status=failed, apply_error="path outside workdir: <file>"`. ADR-6 cwd 격리(읽기 경계)의 쓰기 경계 보강.
- **protocol.md cascade 작업 분량** — Phase B가 outline + protocol.md 양쪽 갱신이라 LOC ~70/~7로 증가. mermaid 노드 텍스트는 두 파일 모두 1:1 일치해야 — 한 쪽만 갱신 시 균열. §5.2 cross-check 필수.
- **JSONL append-only 일관 (P-JSONL)** — `meta.patches`는 driver `kind=proposal` 메시지 append와 동시에 기록 (응답 텍스트에서 추출 → meta 채움 → append 한 호출). 기존 메시지 사후 보강 없음. mermaid에 R2_5 노드를 두지 않는 이유는 추출이 R2 메시지 append와 동시이라 별도 단계가 아니기 때문. R2.6 적용 후 R2.7에서 `kind=patch_applied`로 별도 메시지 append.
- **`# paste` 라벨 위치** — JSONC/mermaid 펜스 직후 첫 줄에 `# paste`. mermaid 본문은 `#` 주석을 노드로 해석하지 않음(mermaid는 `%%` 주석). execute-plan은 라벨 주석을 제외하고 펜스 본문만 outline에 옮긴다 — Phase 작업 단위에서 명시.
