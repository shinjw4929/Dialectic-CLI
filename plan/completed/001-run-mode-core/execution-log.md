# Execution Log · 001-run-mode-core

## Phase A · Foundation (직렬 시작점)

- 입력 phase 파일: `phase-a-foundation.md`
- 산출물:
  - `src/schema.py` (+86 LOC) — `Meta` 14 필드 (frozen+slots, `convergence_streak: int|None=None` default 마지막), `Message` 12 필드, `to_dict`/`from_dict` (`from_` ↔ `"from"` 키 변환)
  - `src/bus.py` (+40 LOC) — `Bus(path)` + `append` (`f.flush()` 강제) + `read_all` (라인 순서 보존). update/delete API 미노출
  - `src/agents/base.py` (+38 LOC) — `AgentResponse` (frozen+slots), `AgentAuthError(Exception)`, `AgentRunner` Protocol (keyword-only `run`)
  - `src/agents/__init__.py` 갱신 — re-export
- 검증: `import` 성공, round-trip 동치, Bus smoke ✓
- 비고: code-conventions.md §5의 `meta: dict` vs phase-a §3.3 `meta: Meta` 사이에서 phase-a 명세 채택 (타입 안전 우월). §5 sync는 Phase D `phase-d §3.5b`에서 처리

## Phase B1 · codex 어댑터 / Phase B2 · claude 어댑터 (병렬, 의존: A)

### B1
- 입력: `phase-b1-codex.md`
- 산출물: `src/agents/codex.py` (+145 LOC) — `cmd_list` 정확(`--ephemeral`/`--sandbox`/`--ignore-rules` 등), `Meta(model=None, thread_id=...)` 채움, `_parse_events` JSONL 4 이벤트 처리, parse 실패 라인 raw 보존+skip, AgentAuthError raise (`not logged in`/`unauthorized`/`authentication`), `_build_env` 화이트리스트
- 검증: import + name/vendor 단언 ✓, cmd_list 옵션 모두 포함 ✓, `subprocess.run(cwd=workdir, shell=False)` ✓

### B2
- 입력: `phase-b2-claude.md`
- 산출물: `src/agents/claude.py` (+134 LOC) — `cmd_list`(`--bare`·`--append-system-prompt` 부재), JSON parsing (`payload.get("result")` 등), `Meta(reasoning_output_tokens=0)` (claude 미보고), AgentAuthError raise, `_empty_meta` fallback 헬퍼 (14 필드 강제 채움)
- 검증: import + name/vendor 단언 ✓, `--bare`/`--append-system-prompt` 부재 ✓, cwd=workdir ✓

## Phase C · Orchestrator + CLI + env_check (직렬, 의존: B1+B2)

- 입력: `phase-c-orchestrator.md`
- 산출물:
  - `src/orchestrator.py` (+398 LOC) — `MODE_ROLES`/`ROLE_FILE`/`SENTINEL_META`/`META_SEQ_SENTINEL`/`_now_ts` (ts 형식 protocol.md §2:92 1:1)/`_detect_converged`/`_serialize_history`/`build_prompt`/헬퍼 4종/`_resolve_runner`/`run_turn` (keyword-only)/`run_session` (ADR-6 차단 + ADR-9 fallback K>1 가드 + streak 누적 + auto_end_converged early return)
  - `src/env_check.py` (+52 LOC) — `_safe_env` (PATH/HOME/USER/LANG + auth) + `check_env` + `_run_capture(cwd=cwd or Path.home())` (claude doctor timeout=30s)
  - `src/cli.py` (rewrite, +67 LOC) — argparse subparsers `run`+`doctor`, `--mode choices=["run"]`, `--convergence-streak default=2`, `--interactive choices=["end-only"]`, `--workdir` ADR-6 안내
- 검증: import 모두 성공, `_detect_converged` 5 케이스 ✓, MODE_ROLES 3 키 + ROLE_FILE 4 path 존재 ✓, `_now_ts()` 정규식 매치 ✓, `dialectic run --help` 전 인자 노출 ✓
- 비고: orchestrator LOC 165→398 (의사코드를 명시 본문으로 풀어냄, paste/spec 정합 우선)

## Phase D · Tests + Doc cross-check (직렬, 의존: C)

- 입력: `phase-d-tests.md`
- 산출물:
  - `tests/__init__.py` + 5 신규 테스트 파일 (총 +343 LOC):
    - `test_schema.py` (+62) — Message/Meta round-trip + ts 정규식 + `from`/`from_` 변환
    - `test_bus_append.py` (+50) — append-only reflection + 라인 순서 + 재오픈 보존
    - `test_cwd_isolation.py` (+104) — codex/claude monkeypatch (`--ephemeral`/`--bare` 부재 등) + `test_run_session_rejects_repo_root_workdir`
    - `test_orchestrator_converge.py` (+77) — `_detect_converged` 4 + ADR-9 fallback 2
    - `test_cwd_isolation_integration.py` (+50, `@pytest.mark.integration`)
  - `pyproject.toml` — `markers` + `addopts = "-m 'not integration'"`
  - `.gitignore` — `CLAUDE.md.test-marker`
  - `docs/runtime-docs/protocol.md` — §2 (Meta JSONC + classDiagram에 `reasoning_output_tokens`/`convergence_streak` 추가, msg_id uuid4) + §4 R4 + §8 (`meta:dict→Meta`, codex `--ephemeral`, claude `--append-system-prompt` 제거) + §10
  - `docs/dev-docs/code-conventions.md` §5 — `meta: dict→Meta` + `:114` 정정
  - `docs/dev-docs/architecture.md` ADR-6 한 줄 보강
  - `README.md` — Day 2 status banner + 환경설정 + 5초 데모 + 현재 동작 모드
- 검증:
  - `pytest -q tests/test_schema.py tests/test_bus_append.py tests/test_cwd_isolation.py tests/test_orchestrator_converge.py`: **14 passed**
  - `pytest -q` (전체): **17 passed, 1 deselected** (integration auto-skip)
  - protocol.md grep: `convergence_streak`(2)·`reasoning_output_tokens`(2)·`--ephemeral`(3)·`--bare`(3) 모두 등장
  - schema↔protocol §2 14 필드 1:1
- 비고:
  - `test_run_session_rejects_repo_root_workdir` SimpleNamespace에 `convergence_streak`/`interactive` 추가 (AttributeError 회피)
  - architecture.md ADR-9 보강은 기존 행에 fallback 명세 이미 포함이라 미터치 (ADR-6만 갱신)
  - `outline/05-timeline.md` Day 2 narrative 미갱신 (phase-d §5에 fallback narrative 있음 — commit message에 사유 명시)

## DoD 체크 (00-plan §6)

| 항목 | 책임 Phase | 상태 |
|---|---|---|
| import 성공 + Message round-trip | A | ✓ |
| codex 짧은 prompt 실 호출 (`thread_id` 등) | B1 | △ 인증 환경 의존, import + 구조 검증으로 갈음 |
| claude 짧은 prompt 실 호출 (`session_id`/`cost_usd`) | B2 | △ 인증 환경 의존, monkeypatch 단위 검증으로 갈음 |
| `dialectic run --max-turns 1` exit 0 + JSONL 4 라인 | C | △ 실 호출 미수행 (인증 환경 의존) |
| `dialectic doctor` exit 0 비용 0 | C | △ 실 호출 미수행 |
| `[CONVERGED]` 수렴 메커니즘 | C | ✓ unit test 4 케이스 |
| ADR-9 fallback warning | C | ✓ unit test 2 케이스 |
| `pytest -q` 통과 | D | ✓ 17 passed, 1 deselected |
| `pytest -m integration` 통과 | D | △ 사용자 수동 실행 (claude OAuth 환경) |
| protocol.md §2/§4/§8/§10 갱신 | D | ✓ |
| README status banner + 환경설정 | D | ✓ |
| validation.md 환원 항목 | 전체 | (Day 2 운영 중 발견 0 — narrative TBD) |
| sync-docs 누락 0 | 전체 | 미호출 |
| review-code P0 = 0 | 전체 | 미호출 |
| outline/05-timeline.md Day 2 narrative | 전체 | 미갱신 (commit message에 사유 명시 fallback) |
| commit 5묶음 사용자 승인 | 전체 | 사용자 결정 영역 |
