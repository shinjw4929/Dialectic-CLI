# review-plan Checklist — Dialectic-CLI

> `review-plan` 스킬이 plan 검토 시 사용하는 항목 표. 각 항목은 명확한 검사 가능 표현. 본 표에 없는 항목은 검사 사각지대 — 발견 시 추가.

---

## 1. 형식 (`docs/dev-docs/Plans/plan-writing-guide.md` 준수)

| 항목 | 검사 | 위반 시 |
|---|---|---|
| 메타 섹션 존재 | `## 0. 메타`, work-id·의도·관련 ADR/Q 명시 | P0 |
| AS-IS 섹션 존재 | `## 1. AS-IS`, 사실 기준 + 인용 근거 (파일·줄 번호) | P0 |
| TO-BE 섹션 존재 | `## 2. TO-BE`, 검증 가능 항목 | P0 |
| Phase 분할 | `## 3. 단계 (Phase)`, 최소 2 Phase, 의존성 명시 | P0 (1 Phase면) / P1 (의존성 누락) |
| 엣지케이스 | `## 4. 엣지케이스 / 위험`, 1개 이상 | P1 (0개) / P2 (표면적) |
| 비기능 요구 | `## 5. 비기능 요구`, 성능·의존성·보안 검토 | P2 (해당 없음 명시 OK) |
| 완료 기준 | `## 6. 완료 기준`, 측정 가능 체크박스 | P0 (모호) / P1 (체크박스 형식 X) |

## 2. 본 도구 specific (Dialectic-CLI 도메인)

| 항목 | 검사 | 위반 시 |
|---|---|---|
| 어댑터 일관성 | 어댑터 변경 시 AgentRunner Protocol 준수 명시? keyword-only 인자? | P0 |
| JSONL 스키마 무결성 | 메시지 구조 변경 시 msg_id/parent_id/is_mock/workdir 등 영향 명시? | P0 |
| cwd 격리 (ADR-6) | subprocess 호출 변경 시 `cwd=resolved_workdir` 명시? `tempfile.mkdtemp` fallback? | P0 |
| prompt 누수 차단 | 런타임 prompt 변경 시 개발용 .md 누수 방지 검토? | P0 |
| 4섹션 prompt 형식 | 런타임 변경 시 ROLE/TASK/HISTORY/YOUR TURN 섹션 영향? | P1 |
| mock 동치성 | mock 어댑터 영향 변경 시 실 호출 결과와 구조 일치 검증 명시? | P1 |
| 모드↔role 매핑 | 모드 추가/변경 시 MODE_ROLES dict + role.md + architecture.md §4 모두 명시? | P0 |
| Documentation-Checklist 매핑 | 새 변경 유형이면 §1에 매핑 추가 명시? | P1 |
| 두 층 분리 (A/B) | plan이 dev-time 자산인지 runtime 자산인지 명확? 두 층 모두 영향이면 분리 plan 권고 | P1 |

## 3. 4계층 매핑 일관성

| 항목 | 검사 | 위반 시 |
|---|---|---|
| Context 계층 | plan이 CLAUDE.md/AGENTS.md 변경 포함 시 두 파일 동기화 명시? | P1 |
| Knowledge 계층 | plan이 docs/Systems 또는 architecture/protocol/roles 변경 시 영향 범위 명시? | P1 |
| Protocol 계층 | plan이 Documentation-Checklist 또는 skills 변경 시 매핑 동기화 명시? | P1 |
| Validation 계층 | plan에 결함 패턴 환원 (validation.md 갱신) 명시? | P2 |

## 4. 실행 가능성

| 항목 | 검사 | 위반 시 |
|---|---|---|
| Phase 의존성 그래프 일관 | 직렬·병렬 분류가 입력·출력 필드와 일치? | P0 |
| Phase 검증 방식 명시 | 각 Phase 끝에서 어떻게 완료 확인? (pytest, syntax 등) | P1 |
| 외부 시스템 의존 | API·네트워크·외부 도구 필요 시 사전 명시? | P1 |
| 전체 분량 추정 | LOC, 영향 파일 수 등 정성적 규모 명시 | P2 |

## 5. ADR / 결정 보드 일관성

| 항목 | 검사 | 위반 시 |
|---|---|---|
| 관련 ADR 인용 | plan이 기존 ADR을 따르는지 또는 위반하는지 명시? | P1 |
| 새 ADR 필요 | 결정 영향이 큰 변경(외부 의존성, 아키텍처 변형)이면 ADR 추가 명시? | P0 (필요한데 누락) / P1 (모호) |
| Q번호 일관 | outline/README.md 결정 보드 Q번호와 일치? | P2 |

---

## 사용 방법 (review-plan 스킬에서)

1. plan 파일 읽기
2. 본 표 §1~5 항목별 순회
3. 각 항목별 ✓/✗/△ + 코멘트 + (위반 시) P 라벨
4. 결과 표를 review-plan 보고 형식으로 출력 (스킬 SKILL.md §5 참조)

## 본 표 자체의 변경

- 새 항목 추가 시 어느 §에 속하는지·왜 누락이었는지 명시
- 본 도구의 새 패턴(예: 새 모드, 새 ADR) 도입 시 §2·§5에 반영
- `docs/dev-docs/Documentation-Checklist.md` §1.4 매핑 갱신 (review-plan-checklist.md → review-plan SKILL.md)
