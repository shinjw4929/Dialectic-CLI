---
name: create-plan
description: 작업 의도를 받아 docs/dev-docs/Plans/plan-writing-guide.md 형식의 plan을 생성. 00-plan.md(인덱스) + Phase별 .md(본문) 분리 작성.
tier: 1
---

# create-plan

## 책임

자연어 작업 의도(예: "Codex 어댑터 작성")를 받아 `plan/<work-id>/` 폴더 단위의 plan으로 변환. **00-plan.md(인덱스)** + **phase-<id>-<slug>.md(Phase 본문)** 분리 산출.

## 호출 시점

- 새 작업 시작 시 (큰 변경의 entry point)
- 사용자가 "이 작업 어떻게 진행할까" 물을 때
- 자동 chaining: 사용자가 의도 명시 → create-plan → review-plan → execute-plan

## 산출물 구조

`docs/dev-docs/Plans/plan-writing-guide.md` §1 단일 진실. 요약:

```
plan/<work-id>/
├── 00-plan.md                    # 메타 + AS-IS/TO-BE + Phase 인덱스 + DoD
├── phase-a-<slug>.md          # Phase A 본문 (목표·입력·출력·작업 단위·검증·엣지케이스)
├── phase-b-<slug>.md          # Phase B (병렬이면 phase-b1·phase-b2)
└── phase-c-<slug>.md          # ...
```

**00-plan.md는 인덱스만**. Phase 본문은 별도 파일. 00-plan.md에서 §3.2 표로 phase 파일 경로 명시.

## 절차

### 1. 의도 분석

사용자 입력에서 추출:
- **작업 단위 식별**: 한 plan으로 다룰 범위 (너무 크면 사용자에게 분할 제안)
- **work-id 부여**: `001-`, `002-` 등 순차 또는 의미 단위 (`codex-adapter`, `cwd-isolation`). 충돌 검사 시 **`plan/` 루트뿐 아니라 `plan/completed/` 하위까지 모두 조회** — 완수된 plan ID도 재사용 금지 (commit history 추적 모호 차단). `ls plan/ plan/completed/` 또는 `find plan -maxdepth 2 -type d` 사용.
- **관련 ADR/Q 검색**: `docs/dev-docs/architecture.md` ADR 표, `outline/README.md` 결정 보드에서 매칭 항목.

### 2. AS-IS 조사

코드·문서 현재 상태 파악:
- `git ls-files` + `grep` / `Read` 도구로 관련 파일 식별.
- 의도와 가까운 기존 코드 검토 (재사용 가능 부분).
- **사용자가 언급한 미검증 사실**(CLI 옵션 존재 여부 등)을 직접 검증 (`--help`, dry-run 등) — 검증 결과는 plan AS-IS에 인라인.
- 사실 기준 기록 — 의견·계획은 TO-BE로.
- 인용은 **파일 + 줄 번호**까지.

### 3. TO-BE 작성

목표 상태를 **검증 가능한 항목**으로:
- 새로 생성될 파일 + 그 안의 핵심 함수·구조 (시그니처 수준).
- 변경될 기존 파일 + 어떤 부분.
- 단위 테스트.
- 문서 갱신 (`docs/dev-docs/Documentation-Checklist.md` 표 조회).

### 4. Phase 분할 + 의존성 그래프

병렬·직렬 가능 단위로 자르기:
- **직렬**: 한 Phase 산출이 다음 Phase 입력.
- **병렬**: Phase 간 의존성 0 (별도 subagent로 동시 실행 가능). 같은 알파벳 + 숫자 명명 (`phase-b1-codex.md`, `phase-b2-claude.md`).

mermaid 의존성 그래프 작성 — 00-plan.md §3.1에 들어감.

`execute-plan`이 본 그래프를 읽고 자동 분기. **최소 2 Phase**로 분할 (1 Phase면 plan 분리 가치 X).

### 5. 엣지케이스 / 비기능 요구 정리

- **plan 횡단 위험**: 00-plan.md §5에.
- **Phase 한정 위험**: 해당 phase 파일 §6에.
- 의도된 범위 밖 영향, OS·환경 차이, 보안, 성능, 외부 의존성 추가 여부.

### 6. 완료 기준 (Definition of Done)

체크박스 형식, 측정 가능 항목만. 각 항목 옆에 책임 Phase 명시 — `- [ ] (Phase A) ...`. 00-plan.md §6에.

### 7. 파일 작성

`plan-writing-guide.md` §2(00-plan.md 형식) + §3(phase 파일 형식) 준수.

#### 7.1 00-plan.md (인덱스)

- §0 메타 (work-id, 의도, ADR/Q, 영향 범위, LOC 추정)
- §1 AS-IS (전체)
- §2 TO-BE (전체 모듈 목록)
- §3 Phase 인덱스 (mermaid + 경로 표)
- §4 비기능 요구
- §5 위험 (Phase 횡단)
- §6 완료 기준 (체크박스 + 책임 Phase)
- §7 참조 .md

#### 7.2 phase-<id>-<slug>.md (각 Phase)

각 Phase 파일은 **자급자족** — 본 파일만 보고도 작업 가능해야 함. 00-plan.md 다시 안 읽도록 §0에 00-plan.md 경로·의존 Phase 명시.

- §0 메타 (Phase ID, 00-plan.md 경로, 의존 Phase, 병렬 그룹, LOC)
- §1 목표 (Phase 끝나면 무엇이 되는지)
- §2 입력 (의존 산출물·참조 .md·사전 검증 사실)
- §3 출력 (생성·변경 파일 + 핵심 시그니처)
  - 코드 블록 의도가 "그대로 paste" 인 정의(상수·dataclass·MODE_ROLES 등)는 펜스 직후 `# paste` 명시. 시그니처+docstring 명세는 라벨 생략(default=spec) 또는 `# spec` 명시. 자세히는 `plan-writing-guide.md` §3.1.
- §4 작업 단위 (체크박스, execute-plan이 그대로 실행 가능)
- §5 검증 (Phase 완료 확인 명령어)
- §6 엣지케이스 / 위험 (Phase 한정)

### 8. 사용자 보고

작성 완료 후:
- 폴더 경로 + 파일 목록(00-plan.md + phase-*.md 개수).
- 핵심 Phase·완료 기준 요약 1줄씩.
- "review-plan으로 검토할까요?" 제안 (자동 chaining의 다음 단계).

## 안티패턴 회피

- **TO-BE 모호함**: "어댑터를 잘 작성한다" → "AgentRunner Protocol 준수, codex exec 호출, raw stream 캡처, AgentResponse 반환".
- **Phase 0~1개**: 한 덩어리는 execute-plan이 병렬화 못 함 → 최소 2 Phase로 분할.
- **00-plan.md만 있고 phase 파일 없음**: 본 가이드 §1.1 위반. execute-plan 컨텍스트 비대 → 반드시 phase 파일 분리.
- **00-plan.md §3.2 경로 표 누락**: 인덱스 단절 → 사용자·도구 모두 phase 파일 못 찾음.
- **phase 파일이 00-plan.md를 인용 안 함**: phase §0 메타에 00-plan.md 경로 필수.
- **AS-IS 누락 또는 줄 번호 부재**: TO-BE만 있으면 변경 분량 모름. 인용은 파일·줄 번호까지.
- **work-id 충돌**: 기존 `plan/` 폴더 검사 후 새 ID 부여.
- **절대 날짜·요일 라벨**: plan 본문에 `2026-05-08`, `5/9 토`, `목요일` 같은 표기 금지. 외부 calendar와 어긋나면 plan 신뢰성 균열. Day index + 가용 시간 + 마일스톤 추상 표현만. 자세히는 `plan-writing-guide.md` §5.
- **시간 추정 (`~30분`, `~1.5h`)**: 사용자 가용 변동성으로 ETA 무의미. LOC·단계 수로 정성 표현.

## 본 도구 specific 도메인 매핑

create-plan이 다룰 일반적 작업 부위:
- **어댑터**: `src/agents/{codex,claude,mock}.py` — `AgentRunner` Protocol 준수, cwd 격리.
- **orchestrator**: `src/orchestrator.py` — 턴 라이프사이클, 모드↔role 매핑.
- **bus**: `src/bus.py` — JSONL append-only, msg_id, parent_id, meta.is_mock.
- **CLI**: `src/cli.py` — 서브커맨드(run/plan/implement/compare/logs), 메뉴 fallback.
- **task·녹음**: `tasks/<task>/{task.md, recordings/}`.
- **하네스 .md**: `CLAUDE.md`, `AGENTS.md`, `docs/*` (Documentation-Checklist 매핑 필수).

이 매핑이 00-plan.md AS-IS/TO-BE + phase 분할 시 자연스러운 frame.

## 본 스킬 자체의 변경

- 절차 변경 시 `docs/dev-docs/Plans/plan-writing-guide.md` 형식과 일관성 검증 (단일 진실).
- 본 스킬은 review-plan / execute-plan과 **동일 형식 가정**으로 동작 — 형식 변경 시 세 스킬 + 가이드 + 체크리스트 4개 동기화 필수.
- `.claude/skills/SKILLS.md` 한 줄 설명 갱신.
