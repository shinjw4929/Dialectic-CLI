---
name: execute-plan
description: plan/<work-id>/ 폴더(00-plan.md + phase 파일들)를 받아 phase 파일 단위로 subagent 분기 실행. 의존성 그래프에 따라 병렬·직렬. 각 Phase 후 검증.
tier: 1
---

# execute-plan

## 책임

`plan/<work-id>/` 폴더를 입력으로 실 코드·문서 변경 수행. **Phase 파일 단위로 subagent 분기** — 00-plan.md §3.1 의존성 그래프를 따라 병렬 가능한 부분은 동시 실행, 직렬은 선행 완료 후.

## 호출 시점

- `review-plan`이 P0 결함 0 보고 후
- 사용자가 plan 승인 후 명시 호출
- 자동 chaining: create-plan → review-plan (P0=0 통과) → execute-plan

## 입력 구조 가정

`docs/dev-docs/Plans/plan-writing-guide.md` §1.1 단일 진실. 본 스킬이 가정하는 구조:

```
plan/<work-id>/
├── 00-plan.md                   # 인덱스 (메타·AS-IS·TO-BE·Phase 그래프·DoD)
├── phase-a-<slug>.md         # Phase A 본문
├── phase-b1-<slug>.md        # 병렬 phase 그룹
├── phase-b2-<slug>.md
├── phase-c-<slug>.md
└── execution-log.md          # 본 스킬이 누적 기록 (실행 시 생성)
```

본 구조가 아니면 `review-plan` 재호출 권고 후 중단 (자동 정정 X).

## 절차

### 1. 00-plan.md 읽기 + Phase 그래프 구축

`00-plan.md` §3.1 mermaid + §3.2 경로 표 파싱:
- 각 Phase의 ID, 파일 경로, 의존 Phase, 병렬 그룹 추출.
- 의존성 0인 Phase 그룹 → 병렬 가능.
- 의존성 1+인 Phase → 직렬 (선행 Phase 완료 후).

§3.2 경로 표가 가리키는 모든 phase 파일이 실제로 존재하는지 검증. 누락 시 사용자에게 보고 후 중단.

### 2. Phase 파일 단위 실행

각 Phase를 **Task tool 또는 subagent**로 분기:
- 병렬 가능한 Phase는 한 메시지에 여러 subagent 호출 (동시 실행).
- 직렬은 선행 완료 후 호출.
- **subagent 입력 = 해당 phase 파일 경로 + 00-plan.md 메타·AS-IS 발췌**.
  - phase 파일 자체가 자급자족(plan-writing-guide §3) — subagent는 phase 파일 §0~§6만 읽고도 작업 가능.
  - 00-plan.md 전체를 subagent에 전달 X (컨텍스트 비대 회피).

phase 파일 §3(출력)·§4(작업 단위)·§5(검증)을 그대로 subagent 명세로 전달.

### 3. Phase별 검증

phase 파일 §5(검증) 명령어 그대로 실행:
- `pytest tests/test_<phase>.py -q` 통과
- `python -c "import <module>"` 또는 `ast.parse()` syntax 검증
- 문서 변경이면 cross-reference 깨짐 검사 (간단한 grep)

검증 실패 시 — 다음 Phase 진행 X. 사용자에게 phase ID + 실패 명령 + 출력 보고.

### 4. execution-log 누적 기록

`plan/<work-id>/execution-log.md`에 phase 단위 추가:

```markdown
# Execution Log · 001-run-mode-core

## Phase A (foundation) — 직렬
- 시작: 2026-05-08T20:00:00
- 입력 phase 파일: phase-a-foundation.md
- 산출물: src/schema.py (+82), src/bus.py (+58), src/agents/base.py (+34)
- 검증: pytest tests/test_schema.py — 3/3 pass; import 성공
- 종료: 2026-05-08T20:18:00

## Phase B1 (codex) — 병렬 with B2
- 입력 phase 파일: phase-b1-codex.md
- ...

## Phase B2 (claude) — 병렬 with B1
- 입력 phase 파일: phase-b2-claude.md
- ...

## Phase C (orchestrator) — 직렬
- 입력 phase 파일: phase-c-orchestrator.md
- ...
```

### 5. 완료 기준 체크

`00-plan.md` §6 완료 기준 체크박스 모두 만족 검증. 각 항목의 책임 Phase가 완료됐는지 확인:
- [ ] (Phase A) 코드 + 단위 테스트 pass
- [ ] (Phase B) 어댑터 1회 실 호출 성공
- [ ] (Phase C) `dialectic run ...` exit 0
- [ ] sync-docs 누락 0
- [ ] review-code P0 = 0

미달 항목이 있으면 사용자에게 보고. 자동으로 다른 스킬 호출 X (단 sync-docs는 phase 끝마다 자동 호출 가능).

### 6. 사용자 보고

```markdown
## execute-plan 완료

대상: plan/001-run-mode-core/ (4 phase 파일)
실행 시간: 2026-05-08T20:00 ~ 22:42

### 변경
- src/schema.py (+82), src/bus.py (+58), src/agents/base.py (+34)
- src/agents/codex.py (+95), src/agents/claude.py (+78)
- src/orchestrator.py (+128), src/cli.py (수정 +60), src/env_check.py (+45)
- tests/test_schema.py (+18), tests/test_bus_append.py (+22), tests/test_cwd_isolation.py (+34)
- docs/runtime-docs/protocol.md §10 갱신

### Phase 진행
- A · foundation: ✓ (직렬)
- B1 · codex / B2 · claude: ✓ ✓ (병렬)
- C · orchestrator: ✓ (직렬)
- D · tests: ✓ (직렬)

### 검증
- pytest 9/9 pass
- sync-docs 누락 0
- 완료 기준 체크박스 5/5 만족

### 권고
`commit` 호출하여 의미 단위 커밋. review-code도 1회 권장.
```

## 본 도구 specific 패턴

### Phase 파일 = subagent 단위

Phase 분리 자체가 컨텍스트 격리 메커니즘:
- 각 subagent는 자기 phase 파일 + 참조 .md만 읽음.
- 00-plan.md 전체·다른 phase 파일은 안 읽음 → 토큰 절약 + 책임 경계 명확.
- 본 도구의 4계층 narrative와 정렬: phase 파일이 작업 단위 Knowledge.

### Phase 병렬 subagent

본 스킬의 Phase 병렬 패턴은 Dialectic-CLI의 `compare` 모드 (병렬 비교)와 같은 사고 모델:
- compare: 같은 task에 다른 매핑을 병렬 실행.
- execute-plan: 같은 plan에 다른 phase 파일을 병렬 실행.
- 둘 다 subagent를 ThreadPoolExecutor 또는 asyncio.gather로 동시 실행.

dev-time 도구가 runtime 도구의 사고 패턴을 그대로 시연 — 본 도구의 self-consistency.

### 검증 자동화

각 Phase 완료 후 가능한 검증 (phase 파일 §5에 명령어 명시):
- syntax: `python -c "import <module>"` 또는 `ast.parse()`.
- 단위 테스트: pytest 해당 파일.
- cwd 격리: 어댑터 변경 시 자동으로 `tests/test_cwd_isolation.py` 호출.
- JSONL append-only: bus 변경 시 자동으로 `tests/test_bus_append.py` 호출.

## 안전장치

- **Phase 검증 실패 시 즉시 중단** — 다음 Phase 안 감.
- **subagent 출력 다시 메인이 검증** — subagent가 거짓 보고할 수 있음.
- **자동 commit 안 함** — execute-plan 완료 후 commit은 사용자가 별도 호출.
- **plan 수정 안 함** — 실행 중 plan과 다른 방향이 더 나아 보이면 사용자에게 보고만 (plan 수정은 사용자가 직접 phase 파일 또는 00-plan.md 편집).
- **폴더 구조 자동 정정 X** — phase 파일 부재·00-plan.md 경로 표 누락이면 review-plan 재호출 권고 후 중단.

## 한계

- subagent의 도메인 지식이 부족하면 본 도구 specific 패턴(cwd 격리, JSONL append-only) 위반 가능 → review-code가 사후 검증.
- 외부 시스템(API 호출, 네트워크)이 필요한 Phase는 본 스킬 범위 X — 사용자가 별도 처리.
- Phase 그래프가 너무 세분화면 오버헤드 — 보통 2-5 Phase가 적절.
- phase 파일 §4 작업 단위가 모호하면 subagent가 자유 해석 — review-plan 사전 검증이 1차 방어선.

## 본 스킬 자체의 변경

- plan 형식 변경 시 본 스킬 + create-plan + review-plan + plan-writing-guide.md + review-plan-checklist.md 5개 동기화 필수.
- 검증 자동화 항목 추가 시 `docs/dev-docs/code-conventions.md` §9 (테스트) 동기화.
- Phase 병렬 패턴 변경 시 `docs/dev-docs/architecture.md` §4 (4 모드 데이터 흐름, compare narrative 포함) 영향 검토.
