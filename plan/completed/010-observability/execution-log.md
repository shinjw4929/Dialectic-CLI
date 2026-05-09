# Execution Log · 010-observability

## Phase A · logs 서브커맨드 — 병렬(B와 동시)

- 입력 phase 파일: `phase-a-logs-subcmd.md`
- 산출물:
  - `src/logs.py` (신규, 252 LOC) — `find_latest_session_dir`/`resolve_session_dir`/`format_summary`/`format_full`/`render_logs` + `_SESSION_TS_PATTERN` 상수
  - `tests/test_logs.py` (신규, 259 LOC, 15 테스트)
  - `src/cli.py` (+131 LOC) — `logs` subparser line 90~120 + `_logs_entry` line 447~488
  - `README.md` "5초 데모" 2줄 추가
  - `docs/dev-docs/Documentation-Checklist.md` §1.1 매핑 1행
  - `outline/03-ux.md §3.5` 1차 범위 6 flag + deferred 4 flag narrative
- 검증:
  - `pytest tests/test_logs.py -q` → 15 passed
  - import smoke test `find_latest_session_dir/...` → IMPORT OK
  - 전체 회귀 → 144 passed
- plan 011 line drift 흡수: `p_logs` 블록 line 90~120, `_logs_entry` line 447 (`_print_env_check` 직전)
- 발견 (plan 본문 외): kind_filter ↔ tail 결합 시 "filter then tail" semantic 채택, follow polling 0.5s 채택(plan 본문 SSOT, outline 250ms와 상이 — outline은 후속 plan에서 동기 권고)

## Phase B · env_check 병렬화 — 병렬(A와 동시)

- 입력 phase 파일: `phase-b-env-parallel.md`
- 산출물:
  - `src/env_check.py` (+24 / -11) — `check_env` `executor.map` 채택, `_safe_env()` 1회 + 4 future 공유
  - `tests/test_env_check_parallel.py` (신규, 55 LOC, 3 테스트)
  - `docs/dev-docs/systems/env-check.md` (+22 LOC) — 병렬 호출 narrative + 측정 결과
- 검증:
  - `pytest tests/test_env_check_parallel.py -q` → 3 passed
  - 실측 wall clock: `time python -c "from src.env_check import check_env"` → real 0m0.532s (≤ 12s, 직렬 worst 30s 대비)
  - dict insertion 순서: claude/version → claude/auth → codex/version → codex/login (단언 pass)
  - 전체 회귀 → 129 passed
- 발견 (plan 본문 외): `executor.map` lambda closure로 `env_pass` 캡처 — 읽기 전용 dict라 race 없음, plan 본문 명시 정합

## Phase C · workdir default — 직렬(A·B 후행)

- 입력 phase 파일: `phase-c-workdir-default.md`
- 산출물:
  - `src/orchestrator.py` (+27 / -5) — `_resolve_workdir` 헬퍼 신규, `run_session` 호출 교체, `os` import
  - `src/cli.py` (+2 / -1) — `--workdir` help 갱신 + `_input_workdir` docstring 정합
  - `tests/test_workdir_default.py` (신규, 105 LOC, 5 테스트)
  - `docs/dev-docs/systems/orchestrator.md` (+14 / -1) — `_resolve_workdir` 섹션
  - `docs/dev-docs/systems/cwd-isolation.md` (+13 / -7) — default 경로 + base_dir이 repo 하위 시 차단 명시
  - `docs/runtime-docs/systems/run-mode.md` (+3 / -3) — `--workdir` + 결과 위치
  - `docs/dev-docs/Documentation-Checklist.md` (+1) — `_resolve_workdir` 매핑
  - `README.md` (+2 / -2) — "결과 위치" 섹션
- 검증:
  - default: `~/.local/share/dialectic/runs/20260509-165836-ejgp8blp`
  - `DIALECTIC_RUNS_DIR=/tmp/test_runs`: `/tmp/test_runs/20260509-165839-vka1sgyk`
  - `XDG_DATA_HOME=/tmp/test_xdg`: `/tmp/test_xdg/dialectic/runs/20260509-165841-w7anj43a`
  - `DIALECTIC_RUNS_DIR=<repo>/runs`: SystemExit (ADR-6) — 회귀 차단
  - `pytest tests/test_workdir_default.py tests/test_cwd_isolation.py tests/test_cwd_isolation_integration.py -q` → 모두 pass
  - 전체 회귀 → 149 passed (Phase A 산출 무손상 확인)
- plan 011 narrative cascade: `_input_workdir` docstring 정정 (mkdtemp 인용 제거 → `~/.local/share/dialectic/runs/`만), `_input_confirm`은 추상 라벨이라 변경 0
- 발견 (plan 본문 외): **C-008 surface 확장** — `cleanup=False` default에서 ADR-6 차단 시 `_resolve_workdir`이 mkdtemp로 생성한 base_dir 임시 dir leak. 기존 `--workdir <repo-under>` 외에 `DIALECTIC_RUNS_DIR=<repo>/runs` env-driven 경로도 같은 surface. 본 plan 범위 외 (제약 "ADR-6 차단 변경 X") — `validation.md §3` 신규 P-id 후보. 테스트 임시 회피는 `finally: shutil.rmtree(base_dir)`

## DoD 체크 (`01-plan.md §6`)

- [x] (Phase A) `dialectic logs --tail 10` 자동 탐색 — 단위 검증 OK
- [x] (Phase A) `--workdir <wd> --session <UTC-ts>` 명시 — tests pass
- [x] (Phase A) `--workdir <wd>` (workdir level) / `<wd>/<UTC-ts>` (session_dir) — tests pass
- [x] (Phase A) malformed JSONL skip + stderr — tests pass
- [x] (Phase A) `find_latest_session_dir` 2-tier + `resolve_session_dir` 자동 분기 — tests pass
- [x] (Phase B) wall clock ≤ 12s — 실측 0.532s
- [x] (Phase B) sub-check 4건 dict insertion 순서 — 단언 pass
- [x] (Phase C) default workdir = `~/.local/share/dialectic/runs/<...>` — 단위 OK
- [x] (Phase C) `DIALECTIC_RUNS_DIR` override — OK
- [x] (Phase C) `DIALECTIC_RUNS_DIR=<repo>/runs` SystemExit — 회귀 OK
- [x] `pytest -q` 회귀 0 + 신규 23건 (A 15, B 3, C 5 ≥ 17 충족)
- [ ] sync-docs 누락 0 — **별도 호출 필요**
- [ ] review-code P0 = 0 — **별도 호출 필요**
