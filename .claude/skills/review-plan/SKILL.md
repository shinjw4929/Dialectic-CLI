---
name: review-plan
description: plan 검토 — 00-summary.md(digest) + 01-plan.md(인덱스) + phase 파일 분리 형식 점검, 빠진 엣지케이스·모순·실현 가능성·summary 동기화. P0/P1/P2 라벨. 자동 plan-edit 없음.
tier: 2
---

# review-plan

## 책임

`plan/<work-id>/` 폴더 단위 검토 — `01-plan.md` + `phase-<id>-<slug>.md` 모두. **결함을 사용자에게 보고만**. 자동 plan-edit 안 함 — 재계획 필요 시 사용자 수동 fix.

본 도구의 핵심 thesis "사용자 = synthesis 생성자"가 dev-time에도 적용. 도구가 자동으로 plan 수정하면 사용자가 빠짐.

## 호출 시점

- `create-plan` 직후 (자동 chaining 권장)
- `execute-plan` 시작 전 (마지막 검증)
- plan 수정 후 재검증

## 실행 방식 (자기 편향성 방지)

본 스킬을 호출하는 메인 에이전트가 **plan 작성자 본인**이면 서브에이전트 분기 필수. 다른 작업자가 만든 plan을 검토하는 경우에는 메인 직접 실행 가능.

| 조건 | 실행 방식 |
|---|---|
| 메인 = `create-plan` 호출자 (자기 plan 검토) | **서브에이전트 분기 필수** — 자기 합리화·blind spot 차단 |
| 메인 ≠ plan 작성자 | 메인 직접 실행 가능 (이미 fresh perspective) |

본 도구의 thesis(cross-vendor dialectic)와 동일 원칙 — 한 컨텍스트가 driver·reviewer 동시 수행하면 antithesis 약화. dev-time도 동일.

### 격리 명령어 (서브에이전트 prompt 필수 포함)

서브에이전트가 메인의 작성 맥락에 끌려가지 않도록, 호출 시 다음 지시를 명시:

> 당신은 이 plan의 작성자가 아닙니다. 작성 의도·이유·암묵 가정을 모르며, plan에 명시된 사실과 `docs/dev-docs/Checklists/review-plan-checklist.md` 체크리스트만으로 판단하십시오. "작성자가 의도했을 것이다"라고 추측 금지 — 적혀 있지 않으면 결함.

### Agent tool 호출 템플릿

```
Agent(
  description="review-plan: <work-id>",
  subagent_type="general-purpose",
  prompt="""
  [위 격리 명령어 전문]

  대상: plan/<work-id>/ 폴더 (00-summary.md + 01-plan.md + 모든 phase-*.md Read).
  절차: 본 SKILL.md §1~§7 순회.
  출력: §8 사용자 보고 형식의 markdown 보고서. P0/P1/P2 라벨 필수.
  """,
)
```

서브에이전트 출력만 메인이 수신 → 사용자에게 그대로 전달.

## 절차

### 1. plan 폴더 읽기

대상: `plan/<work-id>/` 전체.
- `00-summary.md` 1개 (필수, digest).
- `01-plan.md` 1개 (필수, 인덱스).
- `phase-<id>-<slug>.md` N개 (필수, Phase 본문). 01-plan.md §3.2 표가 가리키는 모든 파일.
- 형식 기준: `docs/dev-docs/Plans/plan-writing-guide.md` §2(00-summary.md) + §3(01-plan.md) + §4(phase 파일).

### 2. 폴더 구조 검증 (1차 — 형식 자체)

| 항목 | 검사 | 위반 시 |
|---|---|---|
| `00-summary.md` 존재 | 폴더 안 1개 | P0 |
| `01-plan.md` 존재 | 폴더 안 1개 | P0 |
| Phase 파일 존재 | `phase-<id>-<slug>.md` 1개 이상 | P0 (0개) |
| 01-plan.md §3.2 경로 표 | 모든 phase 파일을 가리키는지 cross-check | P0 (누락) / P1 (잘못된 경로) |
| Phase 파일 ↔ 01-plan.md 일관성 | 각 phase §0의 `소속 plan` 경로가 01-plan.md를 가리킴, 의존 Phase·병렬 그룹이 01-plan.md §3.1 mermaid와 일치 | P0 (모순) / P1 (느슨) |
| `<id>` 명명 일관 | 01-plan.md §3.1 mermaid의 Phase ID(`A`, `B1` 등) ↔ 파일명 (`phase-a-...`, `phase-b1-...`) 대응 | P1 |
| 00-summary.md ↔ 01-plan.md 동기화 | summary §의도·Phase 흐름·핵심 결정/위험·DoD 요약이 본문과 일치(요약 발췌이므로 누락은 OK, 모순은 결함) | P1 (어긋남) |

### 3. 00-summary.md 내용 검증

`plan-writing-guide.md` §2 형식 기준 — 30~80줄 digest. 본문(01-plan.md)의 요약본임을 잊지 않는다.

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

summary는 **발췌**이므로 본문에 있는 항목이 summary에 없는 건 OK. 하지만 **summary가 본문과 어긋나면** P1 (digest 목적 역행).

### 4. 01-plan.md 내용 검증

`docs/dev-docs/Checklists/review-plan-checklist.md` §1·§5 항목별:
- §0 메타 (work-id·의도·ADR/Q·LOC)
- §1 AS-IS 사실 + 인용 (파일·줄 번호)
- §2 TO-BE 검증 가능 항목
- §3 Phase 인덱스 (mermaid + 경로 표)
- §4 비기능 요구
- §5 위험 (Phase 횡단)
- §6 완료 기준 체크박스 + 책임 Phase 명시

### 5. phase 파일 내용 검증 (각 phase별)

`review-plan-checklist.md` §2(도구 specific)·§4(실행 가능성) 항목별:
- §0 메타 (Phase ID·01-plan.md 경로·의존·병렬 그룹·LOC)
- §1 목표 한 문장
- §2 입력 (의존 산출물·참조 .md 줄 번호·사전 검증 사실)
- §3 출력 (생성·변경 파일 + 시그니처 수준 명세)
  - phase 파일 §3 코드 블록의 paste/spec 라벨 검사 (review-plan-checklist §1.4 "§3 코드 블록 라벨" 행) — paste 의도인 정의에 라벨 없으면 P1 보고. 자세히는 `plan-writing-guide.md` §4.1.
- §4 작업 단위 (체크박스, execute-plan이 그대로 실행 가능한가)
- §5 검증 (명령어 형태인가)
- §6 엣지케이스 (Phase 한정, 1개 이상)

본 도구 specific:
- 어댑터 일관성 (AgentRunner Protocol, keyword-only).
- JSONL 무결성 (msg_id/parent_id/is_mock/workdir).
- cwd 격리 (subprocess `cwd=` 명시).
- prompt 누수 차단 (개발용 .md 차단).
- 4섹션 prompt 형식 (런타임 변경 시).
- mock 동치성 (mock 어댑터 영향 시).

### 6. AS-IS 사실 직접 검증

본 스킬은 plan AS-IS의 사실 주장을 **직접 코드·CLI·문서를 읽어 검증**:
- 파일·줄 번호 인용이 실제로 그 위치에 있는지 Read.
- 사용자/plan이 미검증 사실로 둔 항목(`--help`, dry-run으로 확인 가능한 것)은 본 스킬이 직접 검증하여 plan에 반영 권고.
- 사용자 신뢰만으로 통과 X.
- **절대 날짜·요일 라벨 발견 시 P1 결함 보고** — plan 본문에 `2026-05-08`, `5/9 토`, `목요일` 같은 표기가 있으면 외부 calendar와 어긋날 risk. Day index + 가용 시간 + 마일스톤 추상 표현으로 정정 권고. 자세히는 `plan-writing-guide.md` §6 안티패턴.
- **시간 추정 발견 시 P2 결함 보고** — `~30분`, `~1.5h`, `4.5h 가용` 같은 ETA. LOC·단계 수로 정성 대체 권고.

### 7. 결함 P0/P1/P2 분류

| Priority | 의미 | 예시 |
|---|---|---|
| **P0** | plan으로 진행 불가 — 실행 시 거의 확실히 실패 | phase 파일 부재, 01-plan.md §3.2 경로 표 누락, AS-IS 사실 오류, Phase 의존성 모순 |
| **P1** | 진행 가능하지만 위험 — execute-plan 중 막힐 가능성 ↑ | 엣지케이스 표면적, 비기능 요구 누락, 사용자 의도 절반 충족, mock 영향 미고려 |
| **P2** | 개선 권고 — 실행에 직접 지장 없음 | AS-IS 인용 줄 번호 부재, 더 명확한 work-id 명명 |

### 8. 사용자 보고

결함 보고는 표 형식 (Priority·위치·결함·P-id 칼럼). P-id는 `docs/dev-docs/validation.md` §4.4 표 조회 → 매치 시 인용, 매치 X면 `(해당 없음)`.

```markdown
## review-plan 결과

대상: plan/001-codex-adapter/ (00-summary.md + 01-plan.md + phase-a-foundation.md + phase-b1-codex.md + phase-b2-claude.md + phase-c-orchestrator.md)

### 폴더 구조 검증
| 항목 | 상태 |
|---|---|
| 00-summary.md 존재 | ✓ |
| 01-plan.md 존재 | ✓ |
| phase 파일 4개 모두 존재 | ✓ |
| §3.2 경로 표 ↔ phase 파일 일치 | ✓ |
| phase §0 소속 plan 경로 일관 | ✓ |
| summary ↔ 본문 동기화 | ✓ |

### 결함 목록

| Priority | 위치 | 결함 | P-id |
|---|---|---|---|
| P0 | plan 본문 §X | AS-IS 사실 오류 — `cwd=` 누락 인용 (실제는 명시됨) | P-CWD |
| P1 | phase Y §3 | 코드 블록 라벨 부재 — paste 의도인 dataclass에 라벨 없음 | (해당 없음) |
| P2 | 01-plan §1 | AS-IS 줄 번호 부재 (인용 권고) | (해당 없음) |

### 권고
P0 N건 수정 후 재호출 또는 사용자가 plan 직접 수정. 자동 fix 없음.
```

## 안전장치

- **자동 plan-edit 호출 X** — 결함 발견해도 보고만.
- 사용자가 plan을 의도적으로 작성한 경우(예: 본 스킬이 잘못 짚는 경우) 사용자 판단이 우선.
- 보고에 "권고"라는 단어 사용 — 강제 X.

## 본 도구 specific 시각

review-plan이 plan을 보는 frame:
- **본 도구는 AI 에이전트 협업 도구** → plan에 cross-vendor·dialectic 영향 검토.
- **하네스 4계층** (Context·Knowledge·Protocol·Validation) → plan이 어느 계층에 속하는지·다른 계층 영향 명시 검토.
- **A/B 두 층 분리** → plan이 dev-time 자산인지 runtime 자산인지·두 층 누수 위험 검토.

## 한계

- 의미 깊이는 사용자만 판단 가능 (예: "이 ADR이 정말 이 작업과 관련 있나").
- AS-IS 사실 기준 검증은 본 스킬이 코드·CLI를 직접 읽어 검증해야 함 — 사용자 신뢰만으로 X.
- review-plan 자체가 검사 항목을 빠뜨릴 수 있음 → `docs/dev-docs/Checklists/review-plan-checklist.md` 진화 필요.

## 본 스킬 자체의 변경

- 검사 항목 추가 시 `docs/dev-docs/Checklists/review-plan-checklist.md` 동기화 (Documentation-Checklist §1.4).
- plan 형식 변경 시 본 스킬 + create-plan + execute-plan + plan-writing-guide.md + review-plan-checklist.md 5개 동기화 필수.
- 본 도구 specific 시각 변경 시 `.claude/skills/SKILLS.md` 인덱스 한 줄 갱신.
