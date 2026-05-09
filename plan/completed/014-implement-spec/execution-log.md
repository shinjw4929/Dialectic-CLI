# Execution Log · 014-implement-spec

## Phase 그래프 (실행 결과)
- A · CLI subparser + `_input_spec_path` (의존 0) — 병렬 with D ✓
- D · `apply_patches` 신규 파일 분기 (의존 0) — 병렬 with A ✓
- B · `run_session` implement 분기 (A 의존) ✓
- C · cascade + alias + chaining 통합 (B+D 의존) ✓

## Phase A — 병렬 with D
- 입력: phase-a-cli.md
- 산출:
  - `src/cli.py` — `--spec` 인자 + `dialectic implement` alias subparser(`:92-122`) + `_input_spec_path` helper(`:285-326`) + `_input_mode` implement 활성(`:251-274`) + `_input_confirm` spec echo + 메뉴 단계 3 분기(`:497-503`)
  - `tests/test_implement_spec.py` 신규 — 7 케이스 (basic/missing retry/directory retry/empty retry/`?` help/EOF/UTF-8 디코딩)
  - `tests/test_interactive_menu_expansion.py` — `test_input_mode_implement_back` → `_active`로 갱신
  - `tests/test_cli_menu.py` — `assert "task 재입력"` → `assert "재입력"` (mode-aware narrative)
- 검증: pytest tests/test_implement_spec.py 7/7 / 전체 177 pass / `dialectic implement --help` 정상

## Phase D — 병렬 with A
- 입력: phase-d-patch-new-file.md
- 산출:
  - `src/patch_apply.py:74-194` — 빈 SEARCH 차단에 `resolved.exists()` 가드 + `new_files: set[Path]` 추적 + `parent.mkdir(parents=True, exist_ok=True)` + rollback `unlink()` 분기
  - `docs/runtime-docs/roles/implementer.md:80-81` — 신규 파일 셀프체크 항목 2건
  - `docs/dev-docs/systems/patch-apply.md:41-66` — 4 단계 narrative 보강
  - `tests/test_patch_apply_new_file.py` 신규 6 케이스 (basic/subdir/mixed/existing-rejected/rollback unlink/new-then-modify)
- 검증: pytest 신규 6/6 + 기존 11/11 + 전체 183 pass (회귀 0)

## Phase B — 직렬 (A 후)
- 입력: phase-b-orchestrator.md
- 산출:
  - `src/orchestrator.py:766-784` — `run_session` `if args.mode == "implement":` 분기 (None/missing/directory/empty 4종 SystemExit + spec body → args.task substitution)
  - `tests/test_implement_spec.py` — Phase B 5건 추가 (4종 SystemExit + substitution mock)
- 검증: pytest 누적 12건 / 전체 188 pass / SystemExit 4종 단위 호출 메시지 검증 ✓

## Phase C — 직렬 (B+D 후)
- 입력: phase-c-integration.md (chaining 명세 1차 사용자 축소 → 사용자 정정 → 원복하여 전체 명세 수행)
- 산출:
  - `tests/test_implement_spec.py` — alias argparse 단위 3건 + chaining mock 통합 3건 (누적 18건)
  - 문서 cascade 5건:
    - `docs/runtime-docs/systems/INDEX.md` implement 행 갱신
    - `docs/dev-docs/systems/orchestrator.md` `run_session` implement wiring 단락 + cli subparser 표
    - `docs/dev-docs/Documentation-Checklist.md §1.1` 신규 매핑 행
    - `README.md` 〈현재 동작 모드〉 implement 활성 narrative
    - `docs/dev-docs/Plans/upcoming-plans.md` P014 backlog → completed + entry 단락
- 검증: pytest 18/18 / 전체 194 pass / 5 cascade 문서 grep 진입 확인

## DoD 체크 (01-plan.md §6)
- [x] (Phase A) `--spec` 인자 + alias + `_input_spec_path` + `_input_mode` 활성 + `_input_confirm` 확장 + 단위 테스트 7 (≥3)
- [x] (Phase B) `run_session` mode==implement 분기 + 4종 SystemExit + substitution + 단위 테스트 5 (≥5)
- [x] (Phase D) `apply_patches` 신규 파일 분기 + rollback unlink + 셀프체크 + 단위 테스트 6 (≥5)
- [x] (Phase C) chaining mock 통합 3 + alias argparse 3 + cascade 5 (dijkstra 실 시연은 사용자 명시 후 별도)
- [x] `pytest -q` 전체 194 pass (baseline 169 + 신규 25 = 194 / 회귀 0)
- [x] sync-docs 누락 0 — 필수 2건(architecture.md §4 :103 + current-implementation-flow.md :11-12) 갱신 후 OK; 권고 3건 P2 deferred
- [x] review-code P0 = 0 — P1 1건(orchestrator.py:797 OSError catch 누락, C-005 R3 누적) auto-fix + 단위 테스트 1건 추가 (누적 19건); validation.md C-005 R3 환원 적용
- [ ] dijkstra 실 시연 — 사용자 명시 후 (deferred, API 비용)

## 후처리 메모
- 최종 pytest: 200 passed / 3 skipped / 1 deselected (회귀 0)
- plan 014 신규 테스트 누적: A 7 + B 5 + D 6 + C alias 3 + C chaining 3 + P1 fix 1 + 정규식 회귀 차단 1 = 26 (DoD ≥18 충족)
- plan/014-implement-spec/ → plan/completed/014-implement-spec/ 이동 완료

## 사후 hot-fix (사용자 수동 시연 catch — plan 014 P0 보강)

dijkstra 실 시연(`/home/sjw49/test4` workdir, claude→codex)에서 발견된 결함 6건:
1. **메뉴 단계 3 안내문 mode 분기** (`src/cli.py:498-507`) — implement 모드인데 task 안내문(`다익스트라 ... IME 결함`) 출력. mode-aware 분기로 spec 안내문 별도
2. **`ROLE_LABEL_KO["spec-reviewer"]` rename** (`src/ui.py:58` + tests + docs 일괄) — "기획 검토자" → "코드 검토자". plan-reviewer "계획 검토자"와 의미 구분 (사용자 implement 모드에서 plan-reviewer 매핑 결함으로 오인)
3. **`_PATCH_PATTERN` 빈 SEARCH 매칭 결함** (`src/patch_apply.py:21-30`) — 기존 정규식 `(?P<search>.*?)\n={7}`이 search 직전 `\n` 강제 → 신규 파일 fence(`<<<<<<< SEARCH\n=======\n` 직접 인접) 매칭 0건. plan 014 Phase D는 `apply_patches`만 고치고 `extract_patches` 정규식 미수정 — 단위 테스트가 dict 직접 입력으로 우회. **fix**: `(?:(?P<search>.+?)\n)?` alternation + `extract_patches`에서 None→"" 변환 + `test_extract_new_file_empty_search` 회귀 차단
4. **markdown fence wrapping** (`src/patch_apply.py:21-30`) — driver(LLM)가 `FILE:\n```\n<<<<<<< SEARCH...` 형태로 markdown ``` 한 줄 끼워넣어 정규식 깨짐. **fix**: `(?:`{3}[^\n]*\n)?` optional fence 흡수
5. **종료 stderr 안내 보강** (`src/orchestrator.py:847-899`) — finally 블록에 `reason:` (bus 마지막 meta 메시지 content) + `files_changed:` (apply_status="ok" union) 출력. 사용자 ADR-9 자동 종료 인지 + 산출 파일 즉시 확인
6. **implement 모드 silent failure 차단** (`src/orchestrator.py:711-715` + `:891-899`) — turn loop 진입 후 files_changed 0건이면 SystemExit(2) + 친절 진단 메시지. `entered_turn_loop` flag로 spec 검증 raise와 구분 (메시지 보존)
7. **roles/implementer.md:78-83 셀프체크 강화** — markdown fence만 응답 금지 narrative + FILE↔SEARCH 사이 fence 금지

추가 환원:
- `validation.md` C-005 R3 사례 (`OSError` 미catch, plan 014 Phase B spec read) 추가 — 3회 누적 임계 도달, R-NNN 승격 검토 진입
- `validation.md` C-016 신규 후보 — "단위 테스트가 정규식 추출 단계 우회 → end-to-end 회귀 누락 패턴" (plan 014 시연으로 발견). raw 입력 통합 테스트 의무화 권고

검증: 사용자 dijkstra `/home/sjw49/test5/dijkstra.py` 실제 생성 확인 (`reason: auto_end_user` + `files_changed: ...` stderr 출력). plan 014 DoD dijkstra 실 시연 ✓.

## 진행 메모
- Phase A·D는 한 메시지 두 Agent 병렬 분기 — 의존 0 검증
- Phase D 보고 시점에 1 fail 보고 (`test_interactive_menu_confirm_n_retries_task_input`)는 working tree race 가능성 — 메인이 `.venv/bin/pytest -q` 재실행 시 통과 (183 pass) 확인
- Phase C 1차에 사용자가 00-summary.md 축소 (chaining 통합 제외) → 정정 지시로 chaining 3 케이스 추가 작성 (누적 18건)
