# Summary · plan 014 implement-spec

## 의도

`dialectic implement --spec <path>` (또는 `dialectic run --mode implement --spec <path>`) wiring — plan 013 산출 `<workdir>/specs/<slug>.md`를 implement 모드 입력으로 소비. driver=implementer / reviewer=spec-reviewer 1턴 라이프사이클 + 메뉴 단계 2 implement 분기 활성 + **`apply_patches` 신규 파일 생성 분기 보강** (architecture.md `:137` ADR-10 narrative "신규 파일·기존 파일 둘 다 동일 흐름" wiring 충족). `protocol.md §5 :282-284` "implement 모드는 task 대신 spec.md 본문 주입" narrative wiring 충족 + dijkstra 등 빈 workdir 시나리오 작동.

## 배경 / 동기

- plan 013(완료) spec.md 자동 생성 → 본 plan 산출이 그 소비자
- plan 011 phase-a-mode-select.md `:128` "implement는 `--spec` 입력 가정인데 메뉴는 task만 받음" deferred 안내 — 본 plan으로 활성
- outline `:46-50`/`:131-132`/`§4.5.3 :228-240` + `runtime-docs/systems/INDEX.md:13` 모두 implement 모드 narrative 명시. wiring 0 → SSOT-구현 차이 누적
- `MODE_ROLES["implement"]` 정의는 Day 1 plan 001부터 보존됨 — 본 plan은 wiring 만 추가 (role 정의 변경 X)
- **plan 005 시점 잠재 결함 — `architecture.md:137` ADR-10 narrative "신규 파일·기존 파일 둘 다 동일 흐름"이 `src/patch_apply.py:109` `read_text()` FileNotFoundError 미catch + `:97-99` 빈 SEARCH 차단으로 구현 부재**. dijkstra 등 빈 workdir 신규 파일 시나리오 status="failed" — 본 plan Phase D로 해소. **`apply_patches` 호출은 `src/orchestrator.py:594` `run_turn` 내부 모드 무관 path** → Phase D 효과는 implement뿐 아니라 **run 모드(driver=implementer 동일)에서도 신규 파일 생성 활성**. plan 모드는 planner role narrative-only 가이드라 사실상 영향 0

## Phase 흐름

A · CLI subparser + `_input_spec_path` 메뉴 helper · D · `apply_patches` 신규 파일 분기 (A·D 병렬) → B · `run_session` implement 분기 + spec read 검증 (A 의존) → C · 통합 테스트 (plan→implement chaining + dijkstra 시연, B+D 의존)

## 핵심 의사결정

- **CLI 1차 = `--mode implement --spec <path>`** (`p_run` 확장) + `dialectic implement` alias subparser 동시 추가 (outline `:50` narrative 직접 충족)
- **`--task` vs `--spec`**: mode==implement 시 `--spec` required, `--task` 무시 (사용자 stderr 경고)
- **task 자리 substitution**: spec body를 `args.task`로 대입 — `_task_msg` / `build_prompt §2 TASK` 일관 (별도 build_prompt 분기 X)
- **spec 검증 4종**: None/missing/directory/empty 모두 SystemExit + 사용자 친화적 메시지
- **spec 본문 token 한도**: 1차 stderr 경고만, 거부 X (정확한 한도는 별도 plan)
- **메뉴 단계 3 분기**: mode==implement 시 `_input_task` 대신 `_input_spec_path` 호출
- **신규 파일 생성 분기 (Phase D)**: `apply_patches`에 `SEARCH=""` + 파일 부재 시 REPLACE를 신규 파일로 write. 기존 파일 + `SEARCH=""`은 기존 정책 유지 (PatchApplyError). rollback 시 신규 파일 unlink. `roles/implementer.md:78` 셀프체크 항목 보강

## 핵심 위험

- patches in spec body — spec body는 task 자리(build_prompt §2 TASK)이라 `extract_patches` 영향 0 (driver 응답에만 호출). implementer가 spec body 베껴 응답하면 정상 동작 (분리 적용)
- spec 본문 token 한도 초과 — 1차 stderr 경고만, 정확한 한도 체크는 별도 plan
- `dialectic implement` alias vs `--mode implement` 두 path 인자 동기화 — Phase A §6 P2 위험으로 명시 + `_add_common_args` helper 추출 권고
- 메뉴 단계 3 mode 분기 — `_interactive_menu_body` docstring + 흐름 narrative 갱신 필요
- spec 경로 ADR-6 — read-only이므로 cwd auto-discovery 영향 0 (subprocess `cwd=workdir`로 격리). 추가 차단 불필요
- `apply_patches` 신규 파일 분기 — rollback unlink 시 mkdir로 만든 빈 디렉토리 잔재 (cleanup 깔끔함 ↓, 기능 영향 0). 별도 plan 016 후속

## DoD 요약

- [ ] (Phase A) `--spec <path>` 인자 + `dialectic implement` alias + `_input_spec_path` + `_input_mode` implement 분기 활성 + `_input_confirm` 시그니처 확장 + 단위 테스트 ≥3
- [ ] (Phase B) `run_session` mode==implement 분기 (spec 검증 4종 SystemExit + args.task substitution) + 단위 테스트 ≥5
- [ ] (Phase D) `apply_patches` 신규 파일 분기 (`SEARCH=""` + `not exists()` → write_text + parent mkdir + rollback unlink) + `roles/implementer.md:78` 셀프체크 + 단위 테스트 ≥5
- [ ] (Phase C) plan→implement chaining mock 통합 테스트 (신규 파일 patch fence 포함) + alias 동등 동작 argparse 단위 검증 + 메뉴 implement 분기 통합 + 문서 cascade 5건 + dijkstra 실 시연 (사용자 명시 후, API 비용)
- [ ] sync-docs 누락 0 / review-code P0 = 0 / `pytest -q` 회귀 0 + 신규 ≥18 (A 7 + B 5 + D 6 + C 3+ chaining)

→ 상세: [01-plan.md](01-plan.md), Phase별 [phase-a-cli.md](phase-a-cli.md) · [phase-b-orchestrator.md](phase-b-orchestrator.md) · [phase-d-patch-new-file.md](phase-d-patch-new-file.md) · [phase-c-integration.md](phase-c-integration.md)
