---
name: create-plan
description: 작업 의도를 받아 docs/dev-docs/Plans/plan-writing-guide.md 형식의 AS-IS/TO-BE plan 생성. Phase 분할 포함.
tier: 1
---

# create-plan

## 책임

자연어 작업 의도(예: "Codex 어댑터 작성")를 받아 `plan/<work-id>/<plan-name>.md` 형식의 plan으로 변환.

## 호출 시점

- 새 작업 시작 시 (큰 변경의 entry point)
- 사용자가 "이 작업 어떻게 진행할까" 물을 때
- 자동 chaining: 사용자가 의도 명시 → create-plan → review-plan → execute-plan

## 절차

### 1. 의도 분석

사용자 입력에서 추출:
- **작업 단위 식별**: 한 plan으로 다룰 범위 (너무 크면 사용자에게 분할 제안)
- **work-id 부여**: `001-`, `002-` 등 순차 또는 의미 단위 (`codex-adapter`, `cwd-isolation`)
- **관련 ADR/Q 검색**: `docs/dev-docs/architecture.md` ADR 표, `outline/README.md` 결정 보드에서 매칭 항목

### 2. AS-IS 조사

코드·문서 현재 상태 파악:
- `git ls-files` + `grep` / `Read` 도구로 관련 파일 식별
- 의도와 가까운 기존 코드 검토 (재사용 가능 부분)
- 사실 기준 기록 — 의견·계획은 TO-BE로

### 3. TO-BE 작성

목표 상태를 **검증 가능한 항목**으로:
- 새로 생성될 파일 + 그 안의 핵심 함수·구조
- 변경될 기존 파일 + 어떤 부분
- 단위 테스트
- 문서 갱신 (Documentation-Checklist 표 조회)

### 4. Phase 분할

병렬·직렬 가능 단위로 자르기. 의존성 그래프:
- 직렬: 한 Phase 산출이 다음 Phase 입력
- 병렬: Phase 간 의존성 0 (별도 subagent로 동시 실행 가능)

`execute-plan`이 Phase 그래프를 읽고 자동 분기.

### 5. 엣지케이스 / 비기능 요구 정리

- 의도된 범위 밖 영향 (예: 다른 어댑터에 미치는 비대칭)
- OS·환경 차이
- 보안 고려사항 (subprocess, 토큰)
- 성능 제약

### 6. 완료 기준 (Definition of Done)

체크박스 형식. 측정 가능한 항목만.

### 7. plan 파일 작성

`docs/dev-docs/Plans/plan-writing-guide.md` §2 형식 준수. 파일 경로: `plan/<work-id>/<plan-name>.md`.

### 8. 사용자 보고

작성 완료 후:
- plan 경로 알림
- 핵심 Phase·완료 기준 요약 1줄씩
- "review-plan으로 검토할까요?" 제안 (자동 chaining의 다음 단계)

## 안티패턴 회피

- **TO-BE 모호함**: "어댑터를 잘 작성한다" → "AgentRunner Protocol 준수, codex exec 호출, raw stream 캡처, AgentResponse 반환"
- **Phase 0개**: 한 덩어리는 execute-plan이 병렬화 못 함 → 최소 2개로 분할
- **AS-IS 누락**: TO-BE만 있으면 변경 분량 모름 → 항상 양쪽
- **work-id 충돌**: 기존 `outline/` 검사 후 새 ID 부여

## 본 도구 specific 도메인 매핑

create-plan이 다룰 일반적 작업 부위:
- **어댑터**: `src/agents/{codex,claude,mock}.py` — `AgentRunner` Protocol 준수, cwd 격리
- **orchestrator**: `src/orchestrator.py` — 턴 라이프사이클, 모드↔role 매핑
- **bus**: `src/bus.py` — JSONL append-only, msg_id, parent_id, meta.is_mock
- **CLI**: `src/cli.py` — 서브커맨드(run/plan/implement/compare/logs), 메뉴 fallback
- **task·녹음**: `tasks/<task>/{task.md, recordings/}`
- **하네스 .md**: `CLAUDE.md`, `AGENTS.md`, `docs/*` (Documentation-Checklist 매핑 필수)

이 매핑이 plan의 AS-IS/TO-BE 작성 시 자연스러운 frame.

## 본 스킬 자체의 변경

- 절차 변경 시 `docs/dev-docs/Plans/plan-writing-guide.md` 형식과 일관성 검증
- `.claude/skills/SKILLS.md` 한 줄 설명 갱신
