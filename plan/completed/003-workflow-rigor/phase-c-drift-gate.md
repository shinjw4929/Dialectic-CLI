# Phase C · drift 게이트 (sync-docs → commit) — 003-workflow-rigor

## 0. 메타

- Phase ID: C
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: C·D 병렬 (영향 .md 겹침 0)
- 예상 LOC: ~12 LOC

## 1. 목표

sync-docs 결과를 commit 진입 차단 신호로 격상. 누락 .md 존재 시 commit 분류표 작성 진입 X — 사용자가 누락 갱신 후 재진입.

## 2. 입력

- `.claude/skills/sync-docs/SKILL.md:50-66` §4 누락 보고 형식 (변경 대상)
- `.claude/skills/commit/SKILL.md:21-52` §1 변경 수집 + §2 분류표 (변경 대상)
- `CLAUDE.md:87-89` Post-Implementation Checklist sync-docs 강제 표현 (변경 대상, 필수 — drift 게이트 동작과 일관)
- 사전 검증: `commit/SKILL.md:21-30` §1이 `git status` + `git diff --stat`만 수행 — sync-docs 결과 입력으로 받지 않음. `:30-52` §2가 분류표 작성 진입 시 sync-docs 점검 없음.
- 사전 검증: `CLAUDE.md:92` review-code "P0 결함 0 확인 후 commit 진행" 강제 표현 존재. sync-docs는 같은 강제 표현 없음 (`CLAUDE.md:87-89`).

## 3. 출력

### 3.1 `.claude/skills/sync-docs/SKILL.md` 변경

§4 누락 보고 형식 (line 50-66) 끝에 차단 신호 단락 추가:

```markdown
### 4.1 차단 신호

누락 항목이 1+ 존재하면 보고 끝에 마지막 줄에:

`SYNC_DOCS_STATUS: BLOCKED (n missing)`

누락 0이면:

`SYNC_DOCS_STATUS: OK`

`commit` 스킬이 본 신호를 점검 — `BLOCKED` 시 분류표 작성 진입 차단.
```

### 3.2 `.claude/skills/commit/SKILL.md` 변경

§1 변경 수집(line 21-29) 직후 §1.5 신규 섹션 추가:

```markdown
### 1.5 sync-docs 점검 (drift 게이트)

분류표 작성(§2) 진입 전:

1. **escape 경로 점검** — `git diff --cached --name-only` 결과가 단일 `docs/dev-docs/Documentation-Checklist.md`이면 sync-docs skip (사용자 통지: "Documentation-Checklist.md 자체 수정 — drift 게이트 우회"). 사용자가 broken Checklist를 고치는 시나리오 (§6.2 escape 경로).
2. `sync-docs` 자동 호출 (사용자 알림: "sync-docs 자동 점검 실행"). 캐시 X — 매번 신규 호출. 단순성 우선 (§6.1 결정).
3. `SYNC_DOCS_STATUS: BLOCKED` 시 → 분류표 작성 X. 사용자에게 누락 .md 갱신 권고 후 종료.
4. **sync-docs 자체 실패 (Documentation-Checklist 못 읽기, git 명령 실패, 스킬 자체 예외 등) 시** → 분류표 작성 X. 사용자에게 sync-docs 오류 출력 보고 + commit 차단. fail-closed 정책 (§6.2).
5. `SYNC_DOCS_STATUS: OK` 시 → §2 분류표 작성 진행.

본 게이트는 자동 우회 옵션 X (회피 통로 만들면 게이트 무력화). 사용자가 의도적 누락이면 `Documentation-Checklist.md` 매핑 자체를 수정.
```

### 3.3 `CLAUDE.md` §4 변경 (필수)

§4 Post-Implementation Checklist 1번 항목(line 87-89)을 **drift 게이트 동작에 맞춰 강제 표현으로 갱신** — 미갱신 시 미래 세션이 outdated 가이드("누락 발견 시 갱신 후 재호출", soft 표현) 따라 실제 동작과 어긋남:

```markdown
1. **`sync-docs` 스킬 호출**:
   - `docs/dev-docs/Documentation-Checklist.md` 매핑 기준으로 누락된 .md 갱신 점검
   - **누락 발견 시 갱신 후 commit. commit 스킬이 sync-docs `BLOCKED` 신호 시 분류표 진입 자동 차단.**
```

본 변경 시 `AGENTS.md` 동기화 필수 (CLAUDE.md `:193`).

## 4. 작업 단위

- [ ] `sync-docs/SKILL.md` §4.1 차단 신호 단락 추가 (~5 LOC)
- [ ] `commit/SKILL.md` §1.5 sync-docs 점검 단락 추가 (~7 LOC)
- [ ] `CLAUDE.md` §4 1번 항목 강제 표현 갱신 + `AGENTS.md` 동기화 (필수)

## 5. 검증

- `grep -n "SYNC_DOCS_STATUS" .claude/skills/sync-docs/SKILL.md` → 2+ 매치 (BLOCKED, OK)
- `grep -n "SYNC_DOCS_STATUS\|drift 게이트" .claude/skills/commit/SKILL.md` → 매치
- `grep -n "BLOCKED" CLAUDE.md AGENTS.md` → 양쪽 동일 횟수 (필수 — drift 게이트 동작 표현 일치)
- **mock sync-docs 시나리오 검증** (실작동 검증):
  ```bash
  # 1) sync-docs SKILL.md가 BLOCKED 신호 출력 시 commit SKILL §1.5 분기가 어떻게 차단하는지 확인
  # mock 시나리오: 누락 항목 1+ 가정 — sync-docs §4 출력 markdown에 "SYNC_DOCS_STATUS: BLOCKED (1 missing)" 마지막 줄
  # commit §1.5 절차상 본 신호 인식 후 분류표 작성 진입 X 검증
  echo "SYNC_DOCS_STATUS: BLOCKED (1 missing)" | grep -c "BLOCKED"  # 1 (인식)
  
  # 2) OK 신호 시 정상 진입 검증
  echo "SYNC_DOCS_STATUS: OK" | grep -c "BLOCKED"  # 0 (정상 진입)
  ```
- 시나리오 검토: 가상 시나리오로 commit 호출 → sync-docs `BLOCKED` 신호 → 분류표 작성 차단 흐름 markdown 추적 (실 동작은 다음 plan에서 코드 작성 시)

## 6. 엣지케이스 / 위험 (Phase 한정)

### 6.1 sync-docs 캐시 X — 단순성 결정

본 phase는 **캐시 X**로 결정 (§3.2 §1.5 1번에 명시). 매번 sync-docs 자동 호출.

대안(향후 도입 검토): 같은 git HEAD + staged/unstaged 변경 hash 동일이면 재사용. 도입 시 "캐시 무효화 = HEAD 변경 또는 staged/unstaged hash 차이" 판정 로직 추가 필요. 본 plan에서는 단순성 우선으로 도입 X.

### 6.2 sync-docs 자체 실패 + Documentation-Checklist 자체 수정 escape 경로

sync-docs가 `Documentation-Checklist.md` 표 못 읽거나 git 명령 실패 시 → commit 차단? 통과?

차단: §1.5에 "sync-docs 실패 시 commit 차단 + 사용자 보고" 명시. fail-closed 정책.

**escape 경로 (필수)**: 사용자가 broken `Documentation-Checklist.md` 자체를 고치려 commit하는 시나리오 → sync-docs가 그 파일을 읽다 또 실패 → 영구 차단. 회피:

- **단일 파일 예외**: commit 분류표가 `Documentation-Checklist.md` 1개 파일만 포함하면 sync-docs 게이트 skip (사용자 통지: "Documentation-Checklist.md 자체 수정 — drift 게이트 우회").
- 다른 파일과 섞이면 게이트 정상 동작 (의도적 mass commit 차단).
- 본 escape 경로는 commit SKILL.md §1.5에 명시: 분류표 작성 전 `git diff --cached --name-only` 결과가 단일 `docs/dev-docs/Documentation-Checklist.md`이면 sync-docs skip.

### 6.3 CLAUDE.md ↔ AGENTS.md 동기화 실패

§3.3 필수 작업이므로 CLAUDE.md만 갱신하고 AGENTS.md 미갱신 → 두 파일 어긋남 (CLAUDE.md `:193` 위반).

차단: 본 phase 작업 단위에 양쪽 갱신 1쌍으로 묶음. 한 commit에 동시 포함.

### 6.4 review-code도 같은 게이트 필요?

대칭성: sync-docs `BLOCKED` 시 차단이면, review-code `P0 != 0` 시 차단도 같은 형식? 현재 CLAUDE.md `:92`에 강제 표현 있음. SKILL.md에는 명시적 차단 신호 부재.

판정: 본 phase 범위 외 (Phase C는 sync-docs 한정). review-code 게이트는 별도 작업 (plan 003 후속).

### 6.5 회피 통로 부재 (자동 우회 옵션 X) 결정

§3.2 §1.5에 "본 게이트는 자동 우회 옵션 X" 명시. 사용자가 긴급 commit이 필요한 경우(예: 핫픽스)에도 sync-docs 통과 강제 → 사용자 경험 ↓.

차단: 긴급 commit은 사용자가 `Documentation-Checklist.md` 매핑 자체를 수정하거나 (의도적 매핑 제거), 누락 .md를 placeholder로 갱신 후 commit. 회피 통로 만들지 X — thesis "사용자=synthesis 생성자" 정합 (사용자 결정 강제).
