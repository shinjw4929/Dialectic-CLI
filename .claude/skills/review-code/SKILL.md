---
name: review-code
description: 코드의 안전성·인터페이스·컨벤션 3 도메인 검사. 발견된 결함은 docs/dev-docs/validation.md로 환원.
tier: 2
---

# review-code

## 책임

`src/` 코드(또는 변경된 .md 일부)를 **3개 도메인**별로 검사:

1. **안전성** (Security): subprocess injection, 토큰 노출, 파일 I/O 경로
2. **인터페이스** (Interface): 어댑터 일관성, JSONL 스키마, cwd 격리
3. **컨벤션** (Convention): 타입 힌트, 의존성 최소화, README 정합성

발견된 결함은 P0/P1/P2 분류 + 가능 시 `docs/dev-docs/validation.md`에 규칙으로 환원 제안.

## 호출 시점

- `execute-plan` 완료 후 (자동 권장)
- commit 직전 (분류 단계에서 결함 잡기)
- 사용자가 명시 호출 (특정 PR 검토)

## 실행 방식 (자기 편향성 방지)

본 스킬을 호출하는 메인 에이전트가 **검사 대상 코드의 작성자(execute-plan 실행자) 본인**이면 서브에이전트 분기 필수. 다른 작업자가 작성한 코드를 검토하는 경우에는 메인 직접 실행 가능.

| 조건 | 실행 방식 |
|---|---|
| 메인 = `execute-plan` 실행자 (자기 코드 검토) | **서브에이전트 분기 필수** — 자기 합리화·blind spot 차단 |
| 메인 ≠ 코드 작성자 (PR 검토 등) | 메인 직접 실행 가능 (이미 fresh perspective) |

본 도구의 thesis(cross-vendor dialectic)와 동일 원칙 — 한 컨텍스트가 driver·reviewer 동시 수행하면 antithesis 약화. dev-time도 동일.

### 격리 명령어 (서브에이전트 prompt 필수 포함)

서브에이전트가 메인의 구현 맥락에 끌려가지 않도록, 호출 시 다음 지시를 명시:

> 당신은 이 코드의 작성자가 아닙니다. 구현 의도·trade-off·암묵 가정을 모르며, 코드의 실제 동작과 `docs/dev-docs/Checklists/review-code-checklist.md` 체크리스트만으로 판단하십시오. "작성자가 그렇게 한 이유가 있을 것"이라고 추측 금지 — 위반 패턴이 보이면 결함.

### Agent tool 호출 템플릿

```
Agent(
  description="review-code: <대상 요약>",
  subagent_type="general-purpose",
  prompt="""
  [위 격리 명령어 전문]

  대상: <파일 목록> (또는 `git diff HEAD~1`로 변경분 식별).
  절차: 본 SKILL.md §"3 도메인 검사 항목" 순회 + §"P0/P1/P2 분류" 적용.
  출력: §3 결과 보고 형식의 markdown + validation.md 환원 후보 섹션.
  """,
)
```

서브에이전트 출력만 메인이 수신 → 사용자에게 그대로 전달 + validation.md 환원 결정.

## 3 도메인 검사 항목

`docs/dev-docs/Checklists/review-code-checklist.md`가 항목별 표를 보유. 본 스킬은 그 표를 순회하며 검사.

### 도메인 1: 안전성

| 항목 | 검사 |
|---|---|
| subprocess injection | `shell=True` 사용? `cmd_list`로 분리? 사용자 입력이 그대로 인자로 들어가나? |
| 토큰 노출 | 환경변수 dump, `os.environ` print, log에 키 이름 노출? `ANTHROPIC_API_KEY` 등 키 자체가 기록되나? |
| 파일 I/O 경로 | `Path.resolve()` 후 `--workdir` 하위 검증? path traversal (`../`) 차단? mock recording 임의 경로 허용? |
| subprocess timeout | 명시? 무한대 가능성? |
| subprocess cwd | 명시? Dialectic-CLI 자체 cwd로 호출되는 가능성? |
| JSON 파싱 | malformed input 시 raise vs catch? raw 보존? |

### 도메인 2: 인터페이스

| 항목 | 검사 |
|---|---|
| AgentRunner Protocol 준수 | codex/claude/mock 어댑터 모두 동일 시그니처? `AgentResponse` 반환? |
| keyword-only 인자 | `run(prompt, *, raw_log_path, ...)` — 위치 인자로 받는 어댑터 있나? |
| JSONL 스키마 (필수 필드) | msg_id UUID, parent_id, ts ISO-8601 UTC, kind, from, slot, mode, meta.is_mock, meta.workdir 모두 있나? |
| JSONL append-only | 기존 라인 수정 시도? truncate? overwrite? |
| flush/fsync | 매 메시지 후 flush? |
| cwd 격리 | 어댑터 호출 시 `cwd=resolved_workdir` 명시? `tempfile.mkdtemp()` fallback? |
| MODE_ROLES 일관성 | orchestrator의 dict가 docs/runtime-docs/protocol.md §3과 일치? |
| 어댑터 비대칭 | 한 어댑터만 다른 옵션·반환·예외 처리? |

### 도메인 3: 컨벤션

| 항목 | 검사 |
|---|---|
| 타입 힌트 | 모든 함수 시그니처에 있나? `def foo(x):` 같은 미타입? |
| 외부 의존성 | `import` 문에 표준 라이브러리 외 항목? `pyproject.toml`에 추가됐나? ADR 있나? |
| 함수 길이 | 100 lines 초과 함수? 분할 권고. |
| 매직 넘버 | 300, 250 등 하드코딩 — 상수 또는 인자로? |
| 주석 정책 | WHAT 적힌 주석 (자명함)? WHY 적힌 주석은 OK |
| README 정합성 | 새 CLI 옵션·서브커맨드가 README에 반영? |
| Documentation-Checklist 준수 | 코드 변경에 따라 갱신해야 할 .md 모두 손봤나? (sync-docs 결과와 cross-check) |

## P0/P1/P2 분류

| Priority | 의미 | 예시 |
|---|---|---|
| **P0** | 즉시 수정 — 보안·정합성·기능 직접 위협 | shell=True, subprocess cwd 미명시, append-only 위반, 어댑터 시그니처 불일치 |
| **P1** | 위험 — 결함 원인이 될 가능성 | 일부 timeout 미명시, JSONL flush 누락, README 미갱신 |
| **P2** | 개선 권고 — 직접 위협 X | 매직 넘버, 함수 길이 초과, 주석 정책 위반 |

## 절차

### 1. 검사 대상 식별

- 인자로 명시 (예: `review-code src/agents/codex.py`)
- 인자 없으면 `git diff HEAD~1`로 최근 변경 파일

### 2. 도메인별 순회

각 도메인 × 각 항목에 대해:
- 코드 grep / AST 파싱으로 패턴 검사
- 위반 발견 시 P 라벨 + 코드 줄 번호 + 권고 fix

### 3. 결과 보고

```markdown
## review-code 결과

대상: src/agents/codex.py + tests/test_codex.py

### 안전성
- [P0] line 42: subprocess.run에 shell=True 사용 — cmd_list로 분리 필요
- [P1] line 67: timeout 미명시 — 300s 권고

### 인터페이스
- [P0] line 18: AgentRunner Protocol의 keyword-only 인자 위반 — `*` 추가 필요
- [P2] line 92: AgentResponse를 dict로 반환 — frozen dataclass 사용 권고

### 컨벤션
- [P1] line 5: import requests — 외부 의존성 추가, ADR 필요
- [P2] line 110: 함수 길이 130 lines — 분할 권고

### validation.md 환원 후보
1. subprocess shell=True 패턴 (반복 발견 시 규칙화)
2. AgentRunner keyword-only 인자 누락 (어댑터 작성 시 매번 점검 항목)
```

### 4. 환원 자료

발견된 결함 중 **반복 가능한 패턴**은 `docs/dev-docs/validation.md`에 규칙으로 추가 권고:
- 한 번만 발견되면 단순 수정 권고
- 같은 도메인에서 2번 이상 반복되거나, 미래 비슷한 작업에서 또 나올 패턴이면 → validation.md "결함 → 규칙" 섹션에 추가
- 최종 결정은 사용자

## 안전장치

- **자동 코드 수정 X** — 보고만. 수정은 사용자/`execute-plan` 후속 호출.
- **검사 항목 누락 인지** — 본 도구 변화에 따라 새 검사 항목이 필요해질 때 사용자에게 알림 (예: 새 어댑터 추가 시 그 도메인 검사 항목 추가 권고)
- **거짓 양성 줄이기** — 명백한 패턴만 P0. 애매한 항목은 P2 또는 단순 코멘트.

## 본 도구 specific 시각

review-code의 3 도메인은 본 도구가 다루는 코드 베이스에 맞춤:
- 안전성: 외부 CLI subprocess 호출이 핵심이라 injection·sandbox·격리가 핵심
- 인터페이스: 어댑터 단일 인터페이스 + JSONL 무결성 (다른 도구는 다른 인터페이스 — 도메인이 다름)
- 컨벤션: Python·외부 의존성 0 원칙 (다른 도구는 다른 언어·다른 의존성 정책)

이게 dialectic-CLI 자체의 thesis(cross-vendor 시각 다양성)와 차원이 다른 **도메인 다양성** — 메타 충돌 아님. 런타임 dialectic이 벤더 다양성을 다룬다면, 본 스킬은 코드 도메인 다양성을 다룸.

## 한계

- 의미적 정합성(예: protocol.md 본문이 실제로 코드 동작을 정확히 반영하는가) 깊이 검사는 본 스킬이 못 함 → 별도 review-design 같은 스킬이 필요할 수 있으나 본 도구 스코프에서는 review-code + sync-docs로 충분
- 동시성·race condition 검사는 본 스킬 범위 X — 어차피 본 도구가 단일 프로세스 (compare 모드만 병렬)

## 본 스킬 자체의 변경

- 검사 항목 추가 시 `docs/dev-docs/Checklists/review-code-checklist.md` 동기화 (Documentation-Checklist §1.4)
- 새 도메인 추가 (예: 4번째 도메인) 시 본 SKILL.md + checklist + `docs/dev-docs/code-conventions.md` 모두 영향
- 환원 패턴이 반복적으로 잡히면 `docs/dev-docs/validation.md`에 규칙 추가 + 본 스킬 검사 항목으로 승격 가능
