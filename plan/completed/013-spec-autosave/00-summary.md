# Summary · plan 013 spec-autosave

## 의도

`mode=plan` 호출 시 planner ROLE 응답을 매 턴 `<workdir>/specs/<slug>.md` 파일로 자동 저장 (top-level — session 격리 X). 현재는 JSONL `kind=proposal, from=planner` content 필드로만 보존되고 별도 .md 파일 미생성 — `docs/runtime-docs/roles/planner.md:11`/`outline/04-requirements-and-modes.md:199-200` SSOT narrative와 실제 wiring 차이 해소.

**post-010 default 흐름** (`011→010→013` 권고 순서): `dialectic run --mode plan --task X` (--workdir 미지정) → `~/.local/share/dialectic/runs/<ts-id>/specs/<slug>.md` 생성. messages.jsonl은 `<ts-id>/<session_ts>/` 격리 별개.

## 배경 / 동기

- plan 011 1차 review-plan에서 P0 #2로 식별 — plan 011은 menu wiring 한정 + JSONL planner 응답 보존으로 DoD 분리, **spec.md auto-save는 본 plan 013 책임**으로 위임
- outline `:46`/`:50`/`:131-132`/`:199-200`/`:226-240` + planner.md `:11`/`:139` 모두 `<workdir>/specs/<task_id>.md` 산출 narrative 명시 — wiring 0이면 SSOT-구현 차이 누적
- 후속 plan 014 (`dialectic implement --spec <path>` subparser, 사용자 결정 분리)가 본 plan 산출에 의존

## Phase 흐름

A · helpers (slug + path resolve) → B · orchestrator wiring + integration test

## 핵심 의사결정

- task content 자동 slug (영숫자/한글 유지, 특수문자→hyphen, 첫 50char truncate) — 충돌 시 `session_ts` 접미사 fallback (run_session `:662` 산출 재사용 — filename-safe)
- 매 턴 overwrite (마지막 planner 응답이 정본, planner.md `:139` SSOT 정합)
- `dialectic implement --spec <path>` subparser는 본 plan 외 — plan 014로 분리 (사용자 결정)
- write 위치: `run_turn` 안 driver 응답 받은 직후, mode=="plan" 분기 — 모든 interactive 모드(end-only/critical/full) 공통 적용
- spec.md 경로 — **top-level `<workdir>/specs/<slug>.md`** (session 격리 X). SSOT narrative(outline/04 `:199`/planner.md `:11`) 정합 + plan 014 implement 모드 spec 소비 path 단순화. messages.jsonl/sessions/raw은 `<workdir>/<session_ts>/` 격리(`:662-666`) 별개
- specs/ 디렉토리는 ADR-6 정합 (workdir 하위 — repo-root 차단 SSOT는 orchestrator `:616-625` 그대로)

## 핵심 위험

- slug 한글 처리 — terminal/filesystem encoding 차이 가능성. UTF-8 가정 + 단위 테스트로 차단
- run_turn / `_run_session_*` 3종 시그니처 확장 — 한 helper 누락 시 해당 interactive 분기 spec.md 미생성 회귀. 분기별 테스트 3종으로 차단 (default None + keyword-only로 외부 회귀 0)
- 매 턴 overwrite — 중간 턴 실패 시 부분 spec.md 잔재 가능. 정상 완료 시 마지막 정본으로 대체됨 (사용자 의도)
- mock 어댑터(plan 007 deferred) 부재로 통합 테스트는 실 호출 1회 필요 (API 비용)
- spec.md 위치 — top-level vs session 격리 (NEW, 로그 레이아웃 변경 영향). messages.jsonl 등은 `<workdir>/<session_ts>/` 격리지만 spec.md는 SSOT narrative 정합 위해 top-level 유지. 충돌 fallback에 session_ts 재사용으로 1:1 매핑
- plan 014 (`dialectic implement --spec`) 후행 의존 — 본 plan 산출 spec.md 활용 path는 plan 014 진입 전까지 narrative만 정합 (실제 호출 path 부재)
- plan 010 (observability, active) ordering — 권고 순서 `011(완료) → 010 → 013`. 010 Phase C `_resolve_workdir` 추출로 line drift → execute-plan 진입 시 grep 재확인 (의미 충돌 0)

## DoD 요약

- [ ] (Phase A) `_task_to_slug` + `_resolve_spec_path` helper + 단위 테스트 ≥6
- [ ] (Phase B) `mode=plan` 1턴 실 호출 → `<workdir>/specs/<slug>.md` 파일 존재 + planner content 정확 보존
- [ ] (Phase B) 동일 task 재호출 시 `<slug>-<session_ts>.md` 접미사 fallback 동작 (session_dir 디렉토리명과 1:1)
- [ ] sync-docs 누락 0 / review-code P0 = 0 / `pytest -q` 회귀 0 + 신규 ≥17 (interactive 분기 3종 spec_path 전달 검증 포함)

→ 상세: [01-plan.md](01-plan.md), Phase별 [phase-a-helpers.md](phase-a-helpers.md) · [phase-b-wiring.md](phase-b-wiring.md)
