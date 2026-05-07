# Phase E · P-id 카탈로그 (validation.md §4.4) — 003-workflow-rigor

## 0. 메타

- Phase ID: E
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: A, B, C, D
  - A: `review-plan-checklist.md` 동시 수정 (A는 §1.3 라벨 검사, E는 §2 P-id 인용) — 같은 파일 충돌 회피
  - B: `review-plan/SKILL.md` 동시 수정 (B는 라벨 검사, E는 P-id 칼럼) — 같은 파일 충돌 회피
  - C, D: SKILLS.md 인덱스 갱신을 본 phase 마지막 작업으로 묶음 — 모든 SKILL.md 변경(B 3개 + C 2개 + E 2개 = 7번 수정 = 6 스킬) 완료 후 한 번에 인덱스 갱신. C·D 완료 전에 SKILLS.md 갱신하면 누락 위험.
- 병렬 그룹: —
- 예상 LOC: ~17 LOC (P-id 카탈로그 ~15 + SKILLS.md 인덱스 갱신 ~2)

## 1. 목표

validation.md §4.4 6개 패턴에 short-id (P-CWD/P-JSONL/P-MOCK/P-MODE/P-LEAK/P-VENDOR) 부여. review-code/review-plan 보고 형식에 P-id 칼럼 추가하여 결함 발견 시 패턴 추적 자동화.

## 2. 입력

- `docs/dev-docs/validation.md:89-100` §4.4 본 도구 specific 환원 패턴 6개 (변경 대상)
- `docs/dev-docs/Checklists/review-code-checklist.md:84-90` 환원 (validation.md) 섹션 (변경 대상)
- `docs/dev-docs/Checklists/review-plan-checklist.md:46-58` §2 본 도구 specific (변경 대상)
- `.claude/skills/review-code/SKILL.md` 보고 형식 (변경 대상)
- `.claude/skills/review-plan/SKILL.md` 보고 형식 (변경 대상)
- 사전 검증: validation.md §2 R-NNN 카탈로그 비어있음. §4.4 6개 패턴이 사실상 운영 시작 시 매칭 타깃.
- 관련 ADR: ADR-1·2·3·5·6·7 (각각 P-JSONL·P-VENDOR·P-MODE·P-MOCK·P-CWD/P-LEAK·P-MODE 근거 — P-MODE는 모드 정의(ADR-7) + role 정의(ADR-3) 둘 다 근거)

## 3. 출력

### 3.1 `docs/dev-docs/validation.md` 변경

§4.4 (line 89-100) 6개 패턴에 P-id 부여 + 신규 패턴 부여 절차 단락 추가:

```markdown
### 4.4 본 도구 specific 환원 패턴

본 도구 특수 영역에서 자주 발생할 수 있는 패턴 (선제 모니터링). 각 패턴에 short-id 부여 — review-code/review-plan 결함 보고 시 P-id 인용:

| P-id | 패턴 | 근거 ADR |
|---|---|---|
| **P-CWD** | cwd 격리 실수 — 어댑터마다 반복 가능성 ↑ | ADR-6 |
| **P-JSONL** | JSONL append-only 위반 — 멀티 어댑터·멀티 모드 동시 쓰기 시 위험 | ADR-1 |
| **P-MOCK** | mock vs 실 호출 비대칭 — `meta.is_mock` 누락, 출력 형식 차이 | ADR-5 |
| **P-MODE** | 모드↔role 매핑 일관성 — `MODE_ROLES` dict와 docs 사이 | ADR-3, ADR-7 |
| **P-LEAK** | 두 층 누수 — A 층 .md가 runtime prompt에 끼어듦 (cwd 격리가 막아주지만 구조 변경 시 재검증) | ADR-6 |
| **P-VENDOR** | 벤더 비대칭 — Codex만 / Claude만 갖는 옵션이 어댑터 인터페이스에 누수 | ADR-2 |

위 6가지는 본 도구 운영 초기에 1회씩 발생할 가능성이 있으므로, 발견 시 즉시 R-NNN으로 환원 권고 (1회 발견이라도). 환원된 R-NNN은 "사례" 항목에 P-id 인용 (예: `사례: P-CWD 1차 발생 — phase X에서 ...`).

### 4.5 신규 패턴 P-id 부여

§4.4 6개 외 새 패턴 발견 시:

1. 패턴 의미 단위 명명 (예: 새로운 비대칭 = `P-NEWPATTERN`).
2. 사용자가 P-id 결정 (자동 부여 X — 의미 단위 일관성 위해).
3. validation.md §4.4 표에 신규 행 추가 + 근거 ADR 명시.
4. review-code/review-plan SKILL.md 보고 형식이 본 P-id 인식.
```

### 3.2 `docs/dev-docs/Checklists/review-code-checklist.md` 변경

`:84-90` "환원 (validation.md)" 섹션에 1행 추가:

```markdown
- 결함 발견 시 `validation.md` §4.4 P-id 표 조회 → 매치하면 P-id 인용 (예: `P-CWD`). 매치 X면 빈 칸 (신규 패턴 발견 신호 — §4.5 절차 따라 부여 검토).
```

### 3.3 `docs/dev-docs/Checklists/review-plan-checklist.md` 변경

`:46-58` §2 본 도구 specific 표에 1행 추가 (P-id는 본 도구 specific 자산 — §3 4계층 매핑(Context/Knowledge/Protocol/Validation 4 row)에 5번째 row로 추가하면 framing 깨짐):

```markdown
| P-id 인용 | plan이 §4.4 패턴(P-CWD/P-JSONL 등) 영역 변경 시 plan 본문에 P-id 명시? | P2 (인용 부재) |
```

### 3.4 `.claude/skills/review-code/SKILL.md` 변경

review-code 보고 형식에 P-id 칼럼 추가. 결함 보고 표 형식:

```markdown
| 도메인 | 위치 | 결함 | 심각도 | P-id |
|---|---|---|---|---|
| 안전성 | src/agents/codex.py:42 | subprocess.run에 cwd 누락 | P0 | P-CWD |
| 안전성 | src/bus.py:18 | datetime.now() TZ-naive (JSONL bus 무결성 위협, Phase D ts 정책 위반) | P0 | P-JSONL |
```

### 3.5 `.claude/skills/review-plan/SKILL.md` 변경

review-plan 보고 형식 §7에 P-id 칼럼 추가. 결함 보고 표:

```markdown
| Priority | 위치 | 결함 | P-id |
|---|---|---|---|
| P0 | plan 본문 §X | AS-IS 사실 오류 — `cwd=` 누락 인용 (실제는 명시됨) | P-CWD |
| P1 | phase Y §3 | 코드 블록 라벨 부재 — paste 의도인 dataclass에 라벨 없음 | (해당 없음) |
| P2 | 00-plan §1 | AS-IS 줄 번호 부재 (인용 권고) | (해당 없음) |
```

### 3.6 `.claude/skills/SKILLS.md` 인덱스 갱신 (마지막 작업, P1-2 fix)

`Documentation-Checklist.md:50` 매핑: `.claude/skills/<skill>/SKILL.md` 본문 변경 시 `SKILLS.md` 인덱스 한 줄 설명 동기화 필수.

본 plan에서 변경된 6 SKILL.md (create-plan, review-plan, execute-plan, sync-docs, commit, review-code) 각각의 한 줄 설명이 본 plan의 변경 사항을 반영하는지 검토 후 갱신. 어긋난 항목만 수정 (자동 모든 6개 갱신 X).

예시 갱신:
- `commit`: 기존 → "분류 → 사용자 확인 → 의미 단위 순차 commit. **sync-docs `BLOCKED` 시 분류표 진입 자동 차단** 추가." (Phase C 게이트 반영)
- `review-code` / `review-plan`: 기존 → "안전성·인터페이스·컨벤션 3 도메인 검사. **결함 보고 시 P-id 인용** 추가." (Phase E P-id 반영)

본 phase의 가장 마지막 작업 — 모든 SKILL.md 변경(Phase B·C·E) 완료 후 1회 갱신.

P-id는 결함이 §4.4 패턴 6개 중 매치 시 인용. 매치 X면 빈 칸 또는 "(해당 없음)" — 신규 패턴 발견 신호 (§4.5 절차 따라 P-id 부여 검토). 본 변경은 출력 형식 추가만 — 입력 인터페이스 변경 0.

## 4. 작업 단위

- [ ] `validation.md` §4.4 표로 재구성 + P-id 부여 (~10 LOC)
- [ ] `validation.md` §4.5 신규 패턴 P-id 부여 절차 단락 추가 (~5 LOC)
- [ ] `review-code-checklist.md` 환원 §에 P-id 인용 1행 추가 (~2 LOC)
- [ ] `review-plan-checklist.md` §2 본 도구 specific 표에 P-id 인용 1행 추가 (~2 LOC)
- [ ] `review-code/SKILL.md` 보고 형식 표에 P-id 칼럼 추가
- [ ] `review-plan/SKILL.md` 보고 형식 표에 P-id 칼럼 추가
- [ ] 6 P-id의 ADR 근거 cross-check (architecture.md §6 ADR 표와 일관 — `architecture.md:128-135` 인용)
- [ ] **(마지막) `.claude/skills/SKILLS.md` 인덱스 한 줄 설명 갱신** — 본 phase 다른 작업 + Phase B·C SKILL.md 변경 모두 통합 후 1회. `commit`, `review-code`, `review-plan` 항목이 본 plan 변경 사항(drift 게이트, P-id 인용) 반영하는지 검토. 어긋난 행만 수정.

## 5. 검증

- `grep -n "P-CWD\|P-JSONL\|P-MOCK\|P-MODE\|P-LEAK\|P-VENDOR" docs/dev-docs/validation.md` → 6+ 매치
- `grep -n "P-id\|§4.4 P-id" docs/dev-docs/Checklists/review-code-checklist.md docs/dev-docs/Checklists/review-plan-checklist.md` → 양쪽 1+ 매치
- `grep -n "P-id" .claude/skills/review-code/SKILL.md .claude/skills/review-plan/SKILL.md` → 양쪽 매치
- ADR cross-check: 각 P-id의 근거 ADR이 `architecture.md:128-135` 표에 실제 존재하는지 1:1 검증

## 6. 엣지케이스 / 위험 (Phase 한정)

### 6.1 review-plan-checklist.md 동시 수정 충돌 (Phase A와)

`review-plan-checklist.md`가 본 Phase E (P-id 인용 §2)와 Phase A (§1.3 라벨 검사) 둘 다 수정. 직렬 의존 (A → E) 명시로 충돌 회피.

차단: 00-plan.md §3.1 의존성 그래프에 A → E 명시. execute-plan이 본 의존성 따름.

### 6.2 review-plan SKILL.md 동시 수정 충돌 (Phase B와)

`review-plan/SKILL.md`가 본 Phase E (P-id 칼럼)와 Phase B (라벨 검사) 둘 다 수정. 직렬 의존 (B → E) 명시.

차단: 동일.

### 6.2a Phase E의 추가 의존 (C, D — SKILLS.md 인덱스)

본 phase는 SKILLS.md 인덱스 갱신을 마지막 작업으로 포함 (§3.6). C·D 완료 전에 갱신하면 sync-docs/commit SKILL.md 변경이 인덱스에 미반영. 따라서 C → E, D → E 의존 추가 (00-plan.md §3.1 mermaid + §3.2 표).

차단: execute-plan은 본 의존성 그래프 따라 E를 마지막에 진행. C·D는 시작 시점부터 A와 독립 병렬 시작 가능 — E의 시작 시점만 모든 의존 phase 완료 후로 강제.

### 6.3 P-id 인용 위치 결정 (§2 본 도구 specific)

`review-plan-checklist.md` 후보 위치:
- §1.3 phase 본문 검사 — phase 단위 결함만 검사. P-id는 phase 외 plan 전체 적용
- §3 4계층 매핑 — Context/Knowledge/Protocol/Validation 4 row 구조. 5번째 row 추가 시 framing 깨짐
- **§2 본 도구 specific** — P-id는 본 도구 specific 자산 (cwd 격리·JSONL append-only 등 본 도구 고유 결함). framing 깨짐 X

판정: **§2 본 도구 specific에 추가** (`review-plan-checklist.md:46-58`).

### 6.4 신규 패턴 ID 명명 일관성

§3.1 §4.5에 "사용자가 P-id 결정"이라 했지만, 명명 컨벤션 부재 시 분기 가능 (예: `P-NEWPATTERN` vs `P-ASYNC_RACE` vs `P-async-race`). 일관성 위해 컨벤션 명시 권장.

차단: §4.5에 P-id 컨벤션 명시:
- 형식: `P-` + 영문 대문자 단어
- 단어 1개: underscore 없음 (`P-CWD`, `P-JSONL`, `P-MOCK`, `P-MODE`, `P-LEAK`, `P-VENDOR`)
- 단어 2개: UPPER_SNAKE underscore 구분 (`P-ASYNC_RACE`, `P-RETRY_LIMIT`)
- 단어 3개+: 기각 — 의미 단위 짧게. 더 짧은 표현으로 재명명

### 6.5 review-code/SKILL.md 보고 형식 변경의 하위 호환

기존 review-code 호출 결과(이미 작성된 보고)는 P-id 칼럼 없음. 신규 호출만 칼럼 적용. 하위 호환 OK.

차단: 본 변경은 출력 형식 추가만, 입력 인터페이스 변경 0. 자연스러운 호환.
