# Phase B · plan 스킬 3종 동기화 — 003-workflow-rigor

## 0. 메타

- Phase ID: B
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: A (가이드 형식이 단일 진실)
- 병렬 그룹: —
- 예상 LOC: ~10 LOC

## 1. 목표

Phase A의 spec/paste 라벨 규칙을 create-plan / review-plan / execute-plan 3 스킬 SKILL.md에 반영. create-plan은 작성 가이드, review-plan은 검사, execute-plan은 paste 분기 처리.

## 2. 입력

- Phase A 산출물: `docs/dev-docs/Plans/plan-writing-guide.md` §3.1 라벨 규칙 단락 (단일 진실)
- `.claude/skills/create-plan/SKILL.md` (변경 대상)
- `.claude/skills/review-plan/SKILL.md` (변경 대상)
- `.claude/skills/execute-plan/SKILL.md` (변경 대상)
- 사전 검증: `execute-plan/SKILL.md:55` "phase §3·§4·§5을 그대로 subagent 명세로 전달", `:173` "phase §4 모호하면 subagent 자유 해석" — 라벨 분기 추가의 자연스러운 자리

## 3. 출력

### 3.1 `.claude/skills/create-plan/SKILL.md` 변경

§7.2 `phase-<id>-<slug>.md (각 Phase)` §3 출력 항목에 1행 추가 (Phase A의 라벨 규칙이 phase 파일 §3에 작용하므로 일관):

```markdown
- 코드 블록 의도가 "그대로 paste" 인 정의(상수·dataclass·MODE_ROLES 등)는 펜스 직후 `# paste` 명시. 시그니처+docstring 명세는 라벨 생략(default=spec) 또는 `# spec` 명시. 자세히는 `plan-writing-guide.md` §3.1.
```

### 3.2 `.claude/skills/review-plan/SKILL.md` 변경

review-plan 검사 항목 절차 부분(`review-plan-checklist.md` §1.3 인용 위치)에 1줄 추가:

```markdown
- phase 파일 §3 코드 블록의 paste/spec 라벨 검사 (review-plan-checklist §1.3 "§3 코드 블록 라벨" 행) — paste 의도인 정의에 라벨 없으면 P1 보고.
```

### 3.3 `.claude/skills/execute-plan/SKILL.md` 변경

§2 Phase 파일 단위 실행 절차 부분(현재 line ~46-55)에 paste 분기 처리 단락 추가:

```markdown
### 2.1 코드 블록 라벨 처리

phase 파일 §3 출력의 코드 블록 라벨에 따라 subagent 지시:
- **`# paste`** (펜스 직후 첫 줄): 들여쓰기·식별자·값 **그대로 복사**. 변형 금지. subagent에게 "이 블록은 paste — 코드에 그대로 삽입" 지시.
- **`# spec`** 또는 라벨 부재 (default): 시그니처·docstring·예시 명세 — 의도 보존하며 자유 해석. 함수 본문·타입·docstring은 subagent가 결정. subagent에게 "이 블록은 spec — 시그니처·docstring 보존하고 본문 작성" 지시.

라벨이 펜스 직후 첫 줄에 없으면 spec으로 해석. 자세히는 `plan-writing-guide.md` §3.1.
```

## 4. 작업 단위

- [ ] `create-plan/SKILL.md` §7.2 §3 출력 항목에 라벨 가이드 1행 추가
- [ ] `review-plan/SKILL.md` 검사 항목에 라벨 검사 1행 추가
- [ ] `execute-plan/SKILL.md` §2에 §2.1 paste 분기 처리 단락 추가 (~6 LOC)
- [ ] 3 SKILL.md가 plan-writing-guide §3.1을 단일 진실로 인용 — 본문 중복 X

## 5. 검증

- `grep -n "paste\|spec" .claude/skills/create-plan/SKILL.md` → 1+ 매치
- `grep -n "코드 블록 라벨\|paste/spec" .claude/skills/review-plan/SKILL.md` → 1+ 매치
- `grep -n "# paste\|# spec\|라벨 처리" .claude/skills/execute-plan/SKILL.md` → 매치
- 3 SKILL.md 모두 `plan-writing-guide.md §3.1` 또는 `plan-writing-guide §3.1` 인용 확인 (단일 진실 위반 X)

## 6. 엣지케이스 / 위험 (Phase 한정)

### 6.1 단일 진실 위반

3 SKILL.md에 라벨 규칙 본문 중복 작성 시 plan-writing-guide와 어긋남 → 추후 형식 변경 시 4파일 동기화 부담. **각 SKILL.md는 가이드를 인용만**, 본문 중복 X.

차단: §3 출력 명세에 "단일 진실은 plan-writing-guide.md §3.1" 명시.

### 6.2 review-plan SKILL.md 동시 수정 충돌 (Phase E와)

`review-plan/SKILL.md`는 본 Phase B(라벨 검사)와 Phase E(P-id 칼럼) 둘 다 수정. 직렬 의존 (B → E) 명시.

차단: Phase E 의존 그래프에 B → E 명시 (00-plan.md §3.1).

### 6.3 execute-plan §2.1 신규 섹션 번호 충돌

현재 `execute-plan/SKILL.md`는 §2가 "Phase 파일 단위 실행" 단일. §2.1 신설 시 기존 §3·§4·§5 번호 영향 0 (§2 내부 sub-section 신규).

차단: §2.1로 신설, 기존 §3 이후 번호 변경 X.
