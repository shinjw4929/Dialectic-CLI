---
name: review-plan
description: plan 검토 — 빠진 엣지케이스·모순·실현 가능성. P0/P1/P2 라벨. 자동 plan-edit 루프 없음, 결함 시 사용자에게 수동 fix 보고.
tier: 2
---

# review-plan

## 책임

`plan/<work-id>/<plan-name>.md`를 검토. **결함을 사용자에게 보고만**. 자동 plan-edit는 안 함 — 재계획 필요 시 사용자 수동 fix.

본 도구의 핵심 thesis "사용자 = synthesis 생성자"가 dev-time에도 적용. 도구가 자동으로 plan 수정하면 사용자가 빠짐.

## 호출 시점

- `create-plan` 직후 (자동 chaining 권장)
- `execute-plan` 시작 전 (마지막 검증)
- plan 수정 후 재검증

## 절차

### 1. plan 읽기

대상 plan 파일 + `docs/dev-docs/Plans/plan-writing-guide.md` 형식 기준.

### 2. 형식 검증

`docs/dev-docs/Checklists/review-plan-checklist.md` 항목별 점검:
- 메타 (work-id, 의도, 관련 ADR/Q)
- AS-IS 사실 기준 + 인용 근거 명시
- TO-BE 검증 가능 항목 + 측정 가능
- Phase 분할 + 의존성 명시
- 엣지케이스 1개 이상
- 비기능 요구 검토
- 완료 기준 체크박스 + 측정 가능

각 항목 결과를 표로:

| 항목 | 상태 | 코멘트 |
|---|---|---|
| AS-IS 인용 근거 | ✓ | src/agents/base.py:34 인용 |
| Phase 의존성 | ✗ | Phase 2와 3의 의존성 미명시 |
| 엣지케이스 | △ | 1개 있으나 표면적 |

### 3. 본 도구 specific 검증

`docs/dev-docs/Checklists/review-plan-checklist.md`의 도구 specific 항목:
- 어댑터 일관성 (AgentRunner Protocol 준수 명시?)
- JSONL 스키마 무결성 (msg_id/parent_id/is_mock 등)
- cwd 격리 (subprocess 호출 시 cwd 명시?)
- prompt 누수 (개발용 .md 차단?)
- 4섹션 prompt 형식 (런타임 변경 시)
- mock 동치성 (mock 어댑터 영향 시)

### 4. 결함 P0/P1/P2 분류

| Priority | 의미 | 예시 |
|---|---|---|
| **P0** | plan으로 진행 불가 — 실행 시 거의 확실히 실패 | TO-BE 항목 검증 불가, Phase 의존성 모순, AS-IS 사실 오류 |
| **P1** | 진행 가능하지만 위험 — execute-plan 중 막힐 가능성 ↑ | 엣지케이스 표면적, 비기능 요구 누락, mock 영향 미고려 |
| **P2** | 개선 권고 — 실행에 직접 지장 없음 | 더 명확한 work-id 명명, AS-IS 인용 추가 |

### 5. 사용자 보고

```markdown
## review-plan 결과

대상: plan/001-codex-adapter/plan.md

### P0 (즉시 수정 필요)
1. Phase 2와 3의 의존성 미명시 — execute-plan이 병렬·직렬 판단 불가
2. TO-BE "단위 테스트 작성"이 측정 불가 — 어떤 케이스를 어디에 작성할지 명시 필요

### P1 (위험)
1. 엣지케이스 "subprocess timeout" 1개만 있음 — OS별 차이, 부분 출력 등 추가 검토 권고

### P2 (개선)
1. AS-IS의 docs/runtime-docs/protocol.md §8 인용 시 줄 번호 추가 권고

### 권고

P0 2건 수정 후 재호출 또는 사용자가 plan 직접 수정. 자동 fix 없음.
```

## 안전장치

- **자동 plan-edit 호출 X** — 결함 발견해도 보고만
- 사용자가 plan을 의도적으로 작성한 경우(예: 본 스킬이 잘못 짚는 경우) 사용자 판단이 우선
- 보고에 "권고"라는 단어 사용 — 강제 X

## 본 도구 specific 시각

review-plan이 plan을 보는 frame:
- **본 도구는 AI 에이전트 협업 도구** → plan에 cross-vendor·dialectic 영향 검토
- **하네스 4계층** (Context·Knowledge·Protocol·Validation) → plan이 어느 계층에 속하는지·다른 계층 영향 명시 검토
- **A/B 두 층 분리** → plan이 dev-time 자산 변경인지 runtime 자산 변경인지·두 층 누수 위험 검토

## 한계

- 의미 깊이는 사용자만 판단 가능 (예: "이 ADR이 정말 이 작업과 관련 있나")
- AS-IS 사실 기준 검증은 본 스킬이 코드를 직접 읽어 검증해야 함 — 사용자 신뢰만으로 X
- review-plan 자체가 검사 항목을 빠뜨릴 수 있음 → `docs/dev-docs/Checklists/review-plan-checklist.md` 진화 필요

## 본 스킬 자체의 변경

- 검사 항목 추가 시 `docs/dev-docs/Checklists/review-plan-checklist.md` 동기화 (Documentation-Checklist §1.4)
- 본 도구 specific 시각 변경 시 `.claude/skills/SKILLS.md` 인덱스 한 줄 갱신
