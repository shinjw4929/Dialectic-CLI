# review-plan Checklist — Dialectic-CLI

> `review-plan` 스킬이 plan 검토 시 사용하는 항목 표. 각 항목은 명확한 검사 가능 표현. 본 표에 없는 항목은 검사 사각지대 — 발견 시 추가.

---

## 1. 폴더 구조 + 00-summary.md / 01-plan.md 형식 (`docs/dev-docs/Plans/plan-writing-guide.md` 준수)

### 1.1 폴더 구조 (digest + 인덱스 + Phase 분리)

| 항목 | 검사 | 위반 시 |
|---|---|---|
| `plan/<work-id>/00-summary.md` 존재 | 폴더당 1개 (digest) | P0 |
| `plan/<work-id>/01-plan.md` 존재 | 폴더당 1개 | P0 |
| `phase-<id>-<slug>.md` 존재 | 1개 이상 (한 덩어리 plan 금지) | P0 (0개) |
| 명명 규칙 일관 | mermaid Phase ID(`A`/`B1`) ↔ 파일명(`phase-a-...`/`phase-b1-...`) 대응 | P1 |
| 01-plan.md §3.2 경로 표 | 모든 phase 파일을 정확한 상대 경로로 가리킴 | P0 (누락) / P1 (경로 오타) |
| phase 파일 §0 ↔ 01-plan.md 역참조 | 각 phase의 `소속 plan` 경로가 01-plan.md 가리킴 | P0 (단절) |
| 의존·병렬 그룹 일관 | phase §0의 의존·병렬 그룹 ↔ 01-plan.md §3.1 mermaid 일치 | P0 (모순) / P1 (느슨) |

### 1.2 00-summary.md 본문 (digest)

| 항목 | 검사 | 위반 시 |
|---|---|---|
| 분량 | 30~80줄 권장 (10줄 이하면 부실, 150줄 초과면 본문화) | P1 |
| §의도 | 2~3줄, 무엇을 만들/바꾸는가 | P1 (부재) |
| §배경/동기 | 왜 지금 필요한가, ADR/Q번호 인용 권고 | P2 |
| §Phase 흐름 | 텍스트 1줄 또는 mermaid. 01-plan.md §3.1과 위상 일치 | P1 (모순) |
| §핵심 의사결정 | 1줄 단위 3~5개. 01-plan.md AS-IS/TO-BE의 비자명한 결정 | P2 (부재) |
| §핵심 위험 | 1줄 + 차단/완화. 01-plan.md §5와 일치 | P1 (모순) |
| §DoD 요약 | 01-plan.md §6 핵심 3~6개 발췌, 본문과 충돌 없음 | P1 (모순) |
| 본문 링크 | `→ 상세: [01-plan.md](01-plan.md)` 또는 동등 | P2 |
| 동기화 | 본문(01-plan.md, phase-*.md) 갱신 시 summary 동기화? | P1 (어긋남) |

summary는 본문의 **발췌**이므로 본문에 있는 항목이 summary에 없는 건 OK. 하지만 **summary가 본문과 어긋나면** P1 (digest 목적 역행).

### 1.3 01-plan.md 본문 (인덱스)

| 항목 | 검사 | 위반 시 |
|---|---|---|
| 메타 섹션 존재 | `## 0. 메타`, work-id·의도·관련 ADR/Q·LOC 명시 | P0 |
| AS-IS 섹션 존재 | `## 1. AS-IS`, 사실 기준 + 인용 근거 (파일·줄 번호) | P0 (사실 오류) / P2 (줄 번호 부재) |
| TO-BE 섹션 존재 | `## 2. TO-BE`, 검증 가능 항목 | P0 (모호) |
| Phase 인덱스 | `## 3. Phase 인덱스`, mermaid + §3.2 경로 표 | P0 |
| 비기능 요구 | `## 4. 비기능 요구`, 성능·의존성·보안 | P2 (해당 없음 명시 OK) |
| 횡단 위험 | `## 5. 위험`, plan 차원 위험 1개 이상 | P1 (0개) / P2 (표면적) |
| 완료 기준 | `## 6. 완료 기준`, 측정 가능 체크박스 + 책임 Phase 명시 | P0 (모호) / P1 (책임 Phase 부재) |
| 참조 .md | `## 7. 참조`, 검증·실행 시 참조할 문서 | P2 |

### 1.4 phase-<id>-<slug>.md 본문 (각 Phase)

| 항목 | 검사 | 위반 시 |
|---|---|---|
| §0 메타 | Phase ID·01-plan.md 경로·의존·병렬 그룹·LOC | P0 |
| §1 목표 | 한 문장 (Phase 끝나면 무엇이 되는지) | P1 (모호) |
| §2 입력 | 의존 산출물·참조 .md(줄 번호 권고)·사전 검증 사실 | P0 (의존 누락) / P2 (줄 번호 부재) |
| §3 출력 | 생성·변경 파일 + 시그니처 수준 명세 | P0 (시그니처 부재) |
| §3 코드 블록 라벨 | paste 의도인 정의(상수·dataclass)는 `# paste` 라벨 명시? (자세히는 `plan-writing-guide.md` §4.1) | P1 (라벨 부재) |
| §4 작업 단위 | 체크박스, execute-plan이 그대로 실행 가능한가 | P0 (모호) / P1 (단위 너무 큼) |
| §5 검증 | 명령어 형태 (pytest, python -c, grep 등) | P1 |
| §6 엣지케이스 | Phase 한정 1개 이상 | P1 (0개) / P2 (표면적) |
| 자급자족 | phase 파일만 보고 작업 가능한가 (01-plan.md 다시 안 읽어도 됨) | P1 |

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
| P-id 인용 | plan이 §4.4 패턴(P-CWD/P-JSONL 등) 영역 변경 시 plan 본문에 P-id 명시? | P2 (인용 부재) |
| 절대 날짜·요일 라벨 | plan 본문에 `2026-05-08`, `5/9 토`, `목요일` 같은 표기? 외부 calendar mismatch risk + plan 신뢰도 균열 — Day index + 가용 시간 + 마일스톤 추상 표현으로 정정 권고 | P1 |
| 시간 추정 (`~30분`, `~1.5h`) | plan 본문에 시간 ETA? 사용자 가용 변동성으로 무의미 — LOC·단계 수로 정성 대체 권고 | P2 |

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
| Plan 자체 분할 누락 | 4개 신호(Phase 5+, 독립 기능 2+, ADR 2+, 영향 모듈 3+) 중 2개 이상이 단일 plan에 모임? `create-plan` Step 1.5 평가 누락 가능성 — 사용자 단일 결정 흔적(plan §5 위험에 명시)이 있으면 OK, 없으면 분할 권고 | P1 (흔적 부재) / P2 (흔적 있음·재검토만 권고) |

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
