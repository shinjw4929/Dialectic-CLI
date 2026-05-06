# Validation — 결함 패턴 → 규칙 환원

> 본 도구를 운영하면서 **반복 발견된 결함 패턴을 규칙으로 추출**하여 다음 세션부터 같은 결함이 자동 차단되도록 적재한다. 4계층 중 **Validation 계층**의 핵심 자산.

본 문서는 운영 중에 채워진다. 초기 상태는 스켈레톤 (구조만 정의).

---

## 0. 환원 흐름

```
결함 발견 (review-plan / review-code / 사용자 발견)
    ↓
1회성? → 단순 수정 권고만 (본 문서에 추가 X)
반복? → 본 문서에 규칙으로 추가 + 관련 .md/스킬에 검사 항목으로 승격
    ↓
다음 작업부터 자동 차단
```

**판정 기준** (반복으로 분류):
- 같은 도메인에서 2회 이상 발견
- 다른 도메인이지만 패턴이 동일 (예: 어댑터마다 cwd 누락)
- 사용자가 "이건 반복될 결함이다"라고 직관적으로 판단

---

## 1. 규칙 카탈로그

각 규칙은 다음 형식:

```markdown
### R-NNN: <규칙 이름>

- **계층**: Context / Knowledge / Protocol / Validation 중 하나
- **도메인**: 안전성 / 인터페이스 / 컨벤션 / spec / plan / 등
- **발견 경로**: review-code · review-plan · 사용자 발견 등
- **발견 횟수**: N회 (시점)
- **규칙**: <검사 가능 표현>
- **위반 시**: P0 / P1 / P2
- **승격 대상**: <어느 .md/체크리스트에 추가됐나>
- **사례**:
  1. <발견 1: 어떤 작업에서, 어떤 코드/문서에서>
  2. <발견 2>
```

---

## 2. 현재 적재된 규칙

(초기 상태 — 운영 중에 채워질 자리)

> 첫 1회 운영 후 이 자리에 R-001부터 누적됨. 운영 흐름 예시:
>
> - Day 2 어댑터 작성 중 `subprocess.run`에 `cwd` 누락 발견 → R-001로 환원
> - Day 2 다른 어댑터에서도 같은 누락 → R-001 빈도 ↑
> - R-001을 `docs/dev-docs/Checklists/review-code-checklist.md` 안전성 도메인에 P0 항목으로 승격
> - Day 3부터는 review-code가 자동 검사

---

## 3. 환원 가능 후보 (관찰 중)

규칙으로 승격할지 결정 전 단계. 1회만 발견된 결함을 잠정 적재.

> (운영 중 채워짐)

---

## 4. 운영 메커니즘

### 4.1 결함 발견 시점

- `review-code` 호출 결과 → §3 후보로 잠정 적재
- `review-plan` 호출 결과 → §3 후보
- 사용자 직접 발견 → 사용자 판단으로 §3 또는 §2 직접 적재
- 본 도구 실행 중 자체 결함 (실 호출 vs mock 동작 불일치 등) → §3

### 4.2 후보 → 규칙 승격

- §3 후보가 1회 더 발견되면 §2 규칙으로 승격
- 승격 시 ID(R-NNN) 부여, "승격 대상" 명시 — 어느 체크리스트·SKILL.md에 검사 항목으로 추가됐는가
- `docs/dev-docs/Documentation-Checklist.md` §1.4에 매핑 확인

### 4.3 규칙 진화

- 규칙이 승격된 후 새 사례가 또 발견되면 "사례" 항목에 누적 (빈도 추적)
- 규칙이 부적합하다고 판명되면 (false positive 양산 등) — 규칙 수정 또는 삭제. 삭제 시 사유 기록.

### 4.4 본 도구 specific 환원 패턴

본 도구 특수 영역에서 자주 발생할 수 있는 패턴 (선제 모니터링):

- **cwd 격리 실수** (ADR-6 위반) — 어댑터마다 반복 가능성 ↑
- **JSONL append-only 위반** — 멀티 어댑터·멀티 모드에서 동시 쓰기 시 위험
- **mock vs 실 호출 비대칭** — meta.is_mock 누락, 출력 형식 차이
- **모드↔role 매핑 일관성** — MODE_ROLES dict와 docs 사이
- **두 층 누수** (A의 .md가 runtime prompt에 끼어듦) — cwd 격리가 막아주지만 구조 변경 시 재검증 필요
- **벤더 비대칭** — Codex만, Claude만 갖는 옵션이 어댑터 인터페이스에 누수

위 6가지는 본 도구 운영 초기에 1회씩 발생할 가능성이 있으므로, 발견 시 즉시 R-NNN으로 환원 권고 (1회 발견이라도).

---

## 5. 4계층과의 관계

| 계층 | Validation에서 환원 시 영향 |
|---|---|
| Context | CLAUDE.md / AGENTS.md의 Pre/Post Checklist에 검사 항목 추가 (예: "subprocess cwd 명시 검토") |
| Knowledge | docs/dev-docs/code-conventions.md에 새 규칙 추가, docs/dev-docs/architecture.md ADR 갱신 (큰 결정 영향 시) |
| Protocol | docs/dev-docs/Checklists/ 안 항목 승격, docs/dev-docs/Documentation-Checklist.md 매핑 추가 |
| Validation | 본 문서 §2 규칙 자체 진화 |

→ Validation은 다른 3 계층을 갱신하는 메타 계층. 결함을 영속적으로 흡수.

---

## 6. 본 문서 자체의 변경

- 새 규칙 추가 시 ID 순차 부여 (R-001, R-002, ...)
- 형식 변경 시 §1 형식 정의 갱신 + 기존 규칙 재포맷
- 본 문서 갱신은 `docs/dev-docs/Documentation-Checklist.md` §1.3에 매핑되어 있음 — sync-docs가 점검

---

> 초기 갱신: 2026-05-06 (스켈레톤). 운영 중 §2·§3 누적.
