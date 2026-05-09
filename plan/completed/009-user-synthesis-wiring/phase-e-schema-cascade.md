# Phase E · schema 정정 + outline·docs cascade — 009-user-synthesis-wiring

## 0. 메타

- Phase ID: E
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: D (orchestrator wiring — `_decision_msg` helper 호출자 산출)
- 병렬 그룹: —
- 예상 LOC: ~10 LOC (코드) + 테스트 ~10 LOC + 문서 cascade 다수

## 1. 목표

`src/schema.py` `kind` 표 outdated 정정 (6→7종, patch_applied 추가만) + `Meta.vendor` enum docstring 확장 (3→4종, "user" 추가). `user_synthesis` kind 신설 안 함 — 기존 `decision` kind 재사용 (`docs/runtime-docs/protocol.md:238` SSOT). outline §3.1·§3.2·§3.3 critical mode narrative 다중 위치 cascade. architecture.md ADR-9 narrative 갱신. protocol.md + jsonl-bus.md + code-conventions.md + Documentation-Checklist + README sync-docs cascade.

## 2. 입력

- `src/schema.py:53` kind docstring — AS-IS `"task" | "proposal" | "critique" | "decision" | "error" | "meta"` **6종 (outdated)**
- `src/orchestrator.py:50-52, 254-265, 292` patch_applied 정의 — 실제 코드 사용 중
- `docs/runtime-docs/protocol.md:67`, `:111-122`, `:238` — kind 표 7종 정합 + `decision` from=user SSOT
- `src/schema.py:55 directive: str | None` — 기존 필드 (decision kind directive 본문 활용)
- `src/schema.py:21 vendor: str` — `"openai" | "anthropic" | "mock"` 3종
- `src/orchestrator.py` `_decision_msg` helper (Phase D)
- 참조: `outline/03-ux.md` 다중 위치 (`:29`, `:32`, `:34`, `:61-65`, `:226-238`, `:271-282`)
- 참조: `docs/dev-docs/architecture.md` §6 ADR 표 — ADR-9 narrative 갱신 대상

## 3. 출력

### 3.1 `src/schema.py` 변경 (~5 LOC)

`:53` kind docstring 정정 (6→7종):

```python
# paste
    kind: str              # "task" | "proposal" | "critique" | "decision" | "error" | "meta" | "patch_applied"
```

`:21` Meta vendor docstring 4종 갱신:

```python
# paste
    vendor: str            # "openai" | "anthropic" | "mock" | "user"
```

### 3.2 `docs/runtime-docs/protocol.md` §6 narrative 갱신

`:121` patch_applied 행 이미 정합 — 변경 X.

`:238` decision 행 narrative 보강 — 호출 시점 명시:

```markdown
| `decision` | run_session critical/full 모드 (Phase D wiring) — 매 턴 끝 prompt_decision/prompt_end_or_iterate 호출 결과 | `user` |
```

추가 narrative — `decision` 메시지 형식:

```
content    = key (a|r|m|i|e|s) — outline §3.3 SSOT
directive  = directive 본문 (있을 때) 또는 null
seq_in_turn= 97 — 직렬화 순서 proposal=1 → critique=2 → decision=97 → patch_applied=98 → meta=99
              시간 순 ≠ 직렬화 순 (ADR-10 비대칭, src/orchestrator.py:50-52)
              decision은 patch_applied(98) 직전 슬롯 — 사용자 직권 지시가 patch 내역보다
              먼저 driver 다음 턴 prompt에 노출 (_serialize_history sort 정합)
meta.vendor = "user", meta.agent_cli = "user"
meta.is_mock= false (사용자 입력은 실 행위)
meta.cost_usd = null (LLM 호출 0 — 측정 불가, 0과 의미 다름)
```

### 3.3 `outline/03-ux.md` 다중 cascade 갱신 (5 위치)

본 plan §1.5 정합 narrative.

**`:29` 갱신** (default 정의):
```
**`--interactive {full,critical,end-only}` 플래그**
(default 진입로별 분기 — CLI 직접 호출 default `end-only`, 메뉴 진입 default `critical`):
사용자 개입 강도 dial. 진입로 1·2 양쪽에서 동일 동작이지만 default만 분기.
```

**`:32`, `:34` 갱신** (예제):
```
$ dialectic run                              # 모드만 정함 → task부터 메뉴 (default --interactive end-only)
$ dialectic                                  # 메뉴 진입 (default --interactive critical)
$ dialectic run --task @tasks/wave/task.md --interactive critical  # CLI 명시
```

**`:61-65` 갱신** (강도 dial 본문):
```
- full: 매 턴 끝 6지선다(a/r/m/i/e/s) 강제. listener 가동 X
- critical (메뉴 default): Ctrl+F 비동기 트리거 + CONVERGED/max-turns 종료 직전
                          prompt_end_or_iterate (Y/n/text 분기). reviewer P0/P1
                          자동 검출은 parser 미구현 (후속 plan)
- end-only (CLI 직접 호출 default): max-turns·CONVERGED 도달 시 즉시 auto_end
                                   (사용자 prompt 0)
Ctrl-F 트리거: critical 모드만 listener 가동. Ctrl-C는 abort (subprocess SIGINT 전파).
플래그 충돌: --non-interactive가 --interactive보다 우선 (변경 X)
```

**`:226-238` 갱신** (§3.2 critical 모드 자동 진행 예시):
- AS-IS narrative `(critical mode, P0/P1=0이라 prompt 생략. 'q' 또는 Ctrl-C로 개입)` 폐기
- TO-BE: `(critical mode, Ctrl+F 입력 시 다음 턴 끝에 prompt_end_or_iterate 진입. 종료 직전(CONVERGED·max-turns)에는 자동 prompt)`
- 'q' 키 narrative 폐기 (본 plan은 Ctrl+F 단일 트리거)

**`:271-282` 갱신** (§3.3 수렴 종료 흐름 mermaid):
- AS-IS mermaid `streak reset 사용자 prompt` 등 reviewer P0/P1 자동 검출 전제 폐기
- TO-BE mermaid: `[CONVERGED] streak=K 도달 → critical 모드면 prompt_end_or_iterate / end-only 모드면 auto_end_converged`
- 캡션 narrative 갱신: critical = Ctrl+F 트리거 + 종료 직전 prompt SSOT

### 3.4 `docs/dev-docs/architecture.md` §6 ADR-9 narrative 갱신 (P1-1)

ADR-9 (`[CONVERGED]` streak K 자동 종료) narrative 추가 (절대 날짜 없이):

```
ADR-9 정책 변경 (plan 009-user-synthesis-wiring 실행 후):
  - end-only 모드: 기존 정책 유지 (streak >= K → 즉시 auto_end_converged)
  - critical 모드: streak >= K 도달 시 강제 종료 차단 → prompt_end_or_iterate 호출
                  사용자 Y → auto_end_user / n/text → 추가 1턴 + streak 리셋
  - full 모드: 매 턴 끝 prompt_decision (streak 무관)
  - MAX_TURNS_HARD_CAP=20 절대 상한 도입 (critical·full i 무한 방지 + 초기 args 가드)
```

### 3.5 `docs/dev-docs/systems/jsonl-bus.md` cascade

- kind 표 `patch_applied` 행 정합 확인
- `decision` 행 narrative 갱신 — 호출 시점 + Phase D wiring
- meta narrative — `vendor="user"`, `agent_cli="user"`, 토큰 4종 0, `cost_usd=None`, `is_mock=false`

### 3.6 `docs/dev-docs/systems/orchestrator.md` cascade

- turn loop mode 분기 narrative — end-only/critical/full 3 분기 + cleanup-restart
- `_serialize_history(history, *, exclude_reviewer=False)` 시그니처 확장
- `build_prompt(role, task, history, directive, *, exclude_reviewer=False)` 시그니처 확장
- `run_turn(..., *, skip_reviewer=False, exclude_reviewer_history=False)` 시그니처 확장 (default False 회귀 0)
- `_decision_msg` helper + `_last_critique_msg_id` / `_last_proposal_msg_id` helper
- `_setup_sigint_handler` (phase-b R3 hand-off)
- `MAX_TURNS_HARD_CAP=20` 상수 (초기값 가드 + critical·full i 무한 방지)
- mock fallback 분기 narrative (현재 vacuous, plan 007 진입 후 활성)

### 3.7 `docs/dev-docs/code-conventions.md` cascade

- §2 외부 의존성 0: `termios`, `tty`, `select`, `signal` 표준 라이브러리
- TriggerListener termios 패턴 — POSIX 한정 + Windows native cmd no-op fallback
- cleanup-restart 패턴 — Spinner 동일 isatty 가드 + threading.Event + try/finally tcsetattr 복원

### 3.8 `docs/dev-docs/Documentation-Checklist.md` §1.1 cascade (P1-9)

- `src/ui.py` 행 — TriggerListener·prompt_end_or_iterate 추가에 따라 cascade 대상에 P-RAW (validation.md) + code-conventions.md 추가
- `outline/03-ux.md` 행 — §3.1 default 분기 + §3.2 자동 진행 예시 + §3.3 수렴 종료 mermaid 매핑 갱신
- `src/schema.py` 행 — protocol.md §6 + jsonl-bus.md kind 표 매핑 (이미 있을 가능성, outdated 정정 영향)
- `src/orchestrator.py` 행 — `_serialize_history`/`build_prompt`/`run_turn` 시그니처 확장 영향 매핑

### 3.9 `README.md` 갱신

- `--interactive critical/full` 옵션 narrative + 메뉴 default 변경
- Ctrl+F 안내 1줄 (critical 모드)
- Ctrl+C는 abort (subprocess SIGINT)

### 3.10 `tests/test_schema_kind_table.py` 신규 (~10 LOC)

- `Message(..., kind="patch_applied", ...)` round-trip 단언
- `Message(..., kind="decision", ..., directive="...")` round-trip 단언
- Meta `vendor="user"` round-trip 단언

## 4. 작업 단위

- [ ] `src/schema.py:53` kind docstring 7종 정정 (`patch_applied` 추가, paste)
- [ ] `src/schema.py:21` Meta.vendor docstring 4종 갱신 (`user` 추가, paste) — §3 spec paste 블록 + §4 별도 체크박스
- [ ] `docs/runtime-docs/protocol.md` §6 `decision` 행 narrative 보강 (호출 시점 + 메시지 형식 + seq=97 정렬 narrative)
- [ ] `outline/03-ux.md` 5 위치 cascade — `:29`, `:32`, `:34`, `:61-65`, `:226-238`, `:271-282`
- [ ] `docs/dev-docs/architecture.md` §6 ADR-9 narrative 갱신 (절대 날짜 없이)
- [ ] `docs/dev-docs/systems/jsonl-bus.md` decision 행 + meta narrative
- [ ] `docs/dev-docs/systems/orchestrator.md` turn loop mode 분기 + cleanup-restart + SIGINT + 시그니처 확장 narrative
- [ ] `docs/dev-docs/code-conventions.md` TriggerListener termios 패턴
- [ ] `docs/dev-docs/Documentation-Checklist.md` §1.1 — `src/ui.py` 행 + `outline/03-ux.md` 행 + `src/orchestrator.py` 행 매핑 갱신
- [ ] `README.md` `--interactive critical/full` + Ctrl+F 안내
- [ ] `tests/test_schema_kind_table.py` 신규 ≥2 케이스
- [ ] `pytest -q` 전체 회귀 0
- [ ] `sync-docs` 호출 → `SYNC_DOCS_STATUS: OK`

## 5. 검증

- `pytest tests/test_schema_kind_table.py -q` pass
- `pytest -q` 전체 회귀 0
- `sync-docs` 호출 시 `SYNC_DOCS_STATUS: OK`
- `docs/runtime-docs/protocol.md` §6 kind 표 grep 7종 정합
- `outline/03-ux.md` grep `default critical` → 갱신 후 `default 진입로별 분기` 등장
- `outline/03-ux.md` grep `Ctrl+F` → 갱신 후 5 위치 등장
- `outline/03-ux.md` grep `P0/P1=0이라 prompt 생략` → 갱신 후 0건
- `src/schema.py:21` grep `"user"` 등장
- `src/schema.py:53` grep `patch_applied` 등장
- `docs/dev-docs/architecture.md` ADR-9 grep `MAX_TURNS_HARD_CAP` 등장
- `docs/dev-docs/Documentation-Checklist.md` §1.1 grep src/ui.py 행에 P-RAW + code-conventions 매핑

## 6. 엣지케이스 / 위험 (Phase 한정)

- **kind 검증 부재**: Message kind str 자유 — invalid kind도 schema 통과. 본 phase는 enum 검증 도입 X (review-code P2 후속 plan)
- **vendor="user" 영향 범위**: Meta.vendor 자유 str이라 코드 변경 0. docstring narrative만. `_resolve_runner` 등에서 vendor enum 비교 시 영향 검토 (현재 0건 추정)
- **token usage 정직성**: user 메시지는 LLM 호출 0 → tokens 4종 0. `cost_usd=None` (호출 자체 없음, 0과 의미 다름)
- **Documentation-Checklist 매핑**: src/ui.py + outline §3.1 + src/orchestrator.py cascade가 sync-docs 게이트에서 정확 catch — 부재 시 BLOCKED
- **mock 모드 decision (P-MOCK)**: Phase D mock + critical/full → end-only fallback이라 mock 모드에서 decision kind 발생 0. plan 007 진입 후 활성. 단위 테스트 (Phase D mock fallback 케이스)에서 decision 메시지 발생 0 단언 권고
- **outline cascade risk**: outline 갱신이 다른 outline 섹션 (Q6=b, Q18 등)과 정합. grep 영향 사전 확인
- **seq_in_turn 시간 vs 직렬화 비대칭 (R5-7)**: decision seq=97 vs patch_applied seq=98 — 시간상 patch_applied가 critique 직후 (먼저), decision은 critique → 사용자 입력. 시간 순 ≠ seq 순. ADR-10 의도된 비대칭 — `_serialize_history` sort에서 decision이 patch_applied보다 먼저 노출 → "사용자 직권 지시"가 patch 내역보다 먼저 driver 다음 턴 prompt에 보임
- **ADR-9 narrative 갱신 위치**: architecture.md §6 ADR 표 본문 sub-section 추가 (절대 날짜 없이 `plan 009-user-synthesis-wiring 실행 후` narrative)
- **decision kind와 protocol.md `:238` SSOT 정합**: 본 plan은 `decision` 의미 변경 X — 추가 호출 시점 명시만
- **시그니처 확장 회귀**: `_serialize_history`/`build_prompt`/`run_turn` 모두 default False라 AS-IS 회귀 0. 단위 테스트로 확인
