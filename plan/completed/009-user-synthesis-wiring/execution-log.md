# Execution Log · 009-user-synthesis-wiring

## Phase A · CLI mode (병렬 그룹 A·B·C)

- 입력: `phase-a-cli-mode.md`
- 산출:
  - `src/cli.py:74-79` `--interactive` choices 3종 (end-only/critical/full) + help narrative
  - `src/cli.py:261` 메뉴 `interactive="critical"` default
  - `tests/test_cli_interactive_modes.py` 신규 (~85 LOC, 7 케이스 — parametrize 포함)
  - `tests/test_cli_menu.py:108` 기존 단언 `end-only` → `critical` 갱신 (메뉴 default 변경 cascade)
- 검증: pytest 신규 7 pass / 전체 66 pass (P0-2 fix — parser.parse_args 격리)

## Phase B · TriggerListener (병렬 그룹 A·B·C)

- 입력: `phase-b-trigger-listener.md`
- 산출:
  - `src/ui.py` TriggerListener 클래스 추가 (~164 LOC, Spinner 아래)
  - import 변경: `import tty` 추가 + `try: import termios except ImportError: termios=None` 가드
  - `tests/test_trigger_listener.py` 신규 (~167 LOC, 5 케이스)
- 검증:
  - 신규 5 pass / 전체 79 pass (회귀 0)
  - R3 cleanup 단언 통과 (`with TriggerListener(): raise RuntimeError` 후 tcsetattr 복원)
  - isatty False silent + termios 부재 fallback 단언
  - cleanup-restart round-trip 단언
- R1 실 호출 검증: 사용자 시연으로 미룸 (Phase D wiring 완료 후)

## Phase C · prompt_end_or_iterate (병렬 그룹 A·B·C)

- 입력: `phase-c-prompt-end-or-iterate.md`
- 산출:
  - `src/ui.py` prompt_end_or_iterate(turn_id, reason) 함수 (+49 LOC)
  - `tests/test_prompt_end_or_iterate.py` 신규 (~105 LOC, 8 케이스)
- 검증:
  - 신규 8 pass / 전체 74 pass (병렬 그룹 보고 시점)
  - `[User Synthesis · Turn 3]` 라벨 stderr 출력 단언 (outline §3.2:216 SSOT 정합)
  - reason stderr 포함 단언

## A·B·C 통합 회귀 검증

- pytest 79 pass (Phase A·B·C 모두 통합 후)

## Phase D · orchestrator wiring (직렬, A·B·C 의존)

- 입력: `phase-d-orchestrator-wiring.md`
- 산출:
  - `src/orchestrator.py` (+396 / -45)
    - 모듈 상수: `MAX_TURNS_HARD_CAP = 20`, `META_DECISION_SEQ = 97`
    - 시그니처 확장 3개 (default False 회귀 0):
      - `_serialize_history(history, *, exclude_reviewer=False)`
      - `build_prompt(role, task, history, directive, *, exclude_reviewer=False)`
      - `run_turn(..., *, skip_reviewer=False, exclude_reviewer_history=False)`
    - helper 5개:
      - `_decision_msg(turn_id, key, directive, workdir, mode, *, parent_id) -> Message`
      - `_last_critique_msg_id(history) -> str | None`
      - `_last_proposal_msg_id(history) -> str | None`
      - `_setup_sigint_handler(listener) -> Callable | int | None`
    - `run_session` mode 분기:
      - 초기 가드 `max_turns_runtime = min(args.max_turns, MAX_TURNS_HARD_CAP)` + stderr clamp
      - mock fallback (괄호 명시) → end-only 강제 (현재 vacuous, plan 007 진입 후 활성)
      - end-only AS-IS 유지
      - critical: while loop + TriggerListener cleanup-restart + SIGINT 핸들러 try/finally
      - full: while loop + prompt_decision 6 분기 (a/r/m/i/e/s)
      - α 정책: trigger/converged/last_turn 모든 i = max_turns_runtime += 1
  - `tests/test_orchestrator_decision_wiring.py` 신규 (~556 LOC, 23 케이스)
- 검증:
  - 신규 23 pass / 전체 102 pass (회귀 0)
  - while loop 동적 갱신 단언 (P1-새-1 fix): args.max_turns=2 + critical i 1회 → max_turns_runtime=3
  - parent_id reset 위치 단언 (P1-새-2 fix): full s 직후 _last_proposal_msg_id fallback
  - SIGINT 핸들러 단언 (R3 안전망)
  - 초기 가드 단언 (args.max_turns=25 → clamp + stderr)
  - mock fallback 단언 (현재 vacuous, plan 007 진입 후 활성)

## Phase E · schema 정정 + cascade (직렬, D 의존)

- 입력: `phase-e-schema-cascade.md`
- 산출:
  - 코드 (~5 LOC):
    - `src/schema.py:21` Meta.vendor 4종 (user 추가)
    - `src/schema.py:53` Message.kind 7종 (patch_applied 추가, outdated 정정)
  - 단위 테스트 (~95 LOC): `tests/test_schema_kind_table.py` 신규 3 케이스
  - 문서 cascade 8개 .md:
    - `protocol.md` §2 line 71 vendor 4종 + line 118 decision narrative + classDiagram Kind enum patch_applied
    - `outline/03-ux.md` 5 위치 cascade
    - `architecture.md` §6 ADR-9 표 행 + 정책 변경 sub-section
    - `jsonl-bus.md` vendor/kind/meta 정직성
    - `orchestrator.md` 모듈 상수·시그니처·helper·mode 분기
    - `code-conventions.md` 외부 의존성 + TriggerListener 패턴
    - `Documentation-Checklist.md` §1.1 매핑 갱신
    - `README.md` --interactive 옵션 + Ctrl+F·Ctrl+C narrative
- 검증:
  - 신규 3 pass / 전체 105 pass (회귀 102 → 105)
  - protocol.md kind 7종 grep 정합
  - outline `default 진입로별 분기` + `Ctrl+F` (5 위치) + `P0/P1=0이라 prompt 생략` 0건
  - schema.py vendor user / kind patch_applied 등장
  - architecture.md ADR-9 MAX_TURNS_HARD_CAP 등장
  - Documentation-Checklist src/ui.py P-RAW + code-conventions 매핑 등장

## 통합 결과

- 회귀: 0 → 105 pass (74 기존 + 31 신규)
- 신규 단위 테스트: 5 파일 (cli_interactive_modes / trigger_listener / prompt_end_or_iterate / orchestrator_decision_wiring / schema_kind_table)
- LOC: 코드 +570 / 테스트 +1008 / 문서 cascade 8개 .md

## DoD 체크박스 (01-plan.md §6)

- [x] (Phase A) cli.py:74-77 choices 3종 + :257-262 메뉴 default critical
- [x] (Phase A) tests/test_cli_interactive_modes.py ≥3 케이스 (실 7)
- [x] (Phase B) src/ui.py:TriggerListener + ≥4 케이스 (실 5)
- [ ] (Phase B) Ctrl+F 실 호출 검증 (R1·R2 통과) — 사용자 시연 대기
- [x] (Phase B) __exit__ 자동 cleanup 단위 테스트 (R3)
- [x] (Phase C) prompt_end_or_iterate(turn_id, reason) + ≥4 케이스 (실 8)
- [x] (Phase D) _serialize_history(*, exclude_reviewer) 시그니처 확장 + 회귀 0
- [x] (Phase D) build_prompt(*, exclude_reviewer) 시그니처 확장 + 회귀 0
- [x] (Phase D) run_turn(*, skip_reviewer, exclude_reviewer_history) 시그니처 확장 + 회귀 0
- [x] (Phase D) _decision_msg/_last_critique_msg_id/_last_proposal_msg_id/_setup_sigint_handler helper
- [x] (Phase D) MAX_TURNS_HARD_CAP=20 (critical·full + 초기 가드)
- [x] (Phase D) 3 mode 분기 wiring + cleanup-restart + SIGINT 핸들러
- [x] (Phase D) tests ≥10 케이스 (실 23)
- [ ] (Phase D) critical/full 실 호출 시연 — 사용자 시연 대기
- [x] (Phase E) src/schema.py:53 7종 + :21 4종
- [x] (Phase E) tests/test_schema_kind_table.py ≥2 케이스 (실 3)
- [x] (Phase E) outline 5 위치 cascade
- [x] (Phase E) architecture.md §6 ADR-9 narrative
- [x] (Phase E) sync-docs cascade — protocol + jsonl-bus + code-conventions + Documentation-Checklist + README
- [x] 전체 회귀 0 — pytest 105 pass
- [ ] sync-docs 누락 0 — sync-docs 스킬 호출 대기
- [ ] review-code P0 = 0 — review-code 스킬 호출 대기

DoD 미충족 4건:
- Ctrl+F / critical/full 실 호출 시연 (R1) — 사용자 시연 영역
- sync-docs / review-code 스킬 호출 — 실행 대기
