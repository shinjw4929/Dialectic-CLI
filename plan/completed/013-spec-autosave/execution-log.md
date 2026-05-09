# Execution Log · 013-spec-autosave

## Phase A · helpers (slug + path resolve) — 직렬

- 입력 phase 파일: phase-a-helpers.md
- 산출물:
  - `src/orchestrator.py`: `import re` 추가, `_task_to_slug` / `_resolve_spec_path` helper 2개 (+`_SLUG_KEEP_RE` / `_SLUG_DASH_COLLAPSE_RE` 모듈 상수) — `_now_ts` 직후 utility 영역 (~50 LOC)
  - `tests/test_spec_autosave.py`: slug 6 + path 4 = 10 케이스 (~85 LOC)
- 검증:
  - `python -c "from src.orchestrator import _task_to_slug, _resolve_spec_path; print(_task_to_slug('Hello World!'))"` → `hello-world` ✓
  - `pytest tests/test_spec_autosave.py -q` → 10/10 pass
  - 회귀: `pytest -q` → 159/159 pass (Phase A 시점)

## Phase B · orchestrator wiring + 통합 테스트 — 직렬 (A 의존)

- 입력 phase 파일: phase-b-wiring.md
- 산출물:
  - `src/orchestrator.py`:
    - `run_turn` 시그니처 `*, spec_path: Path | None = None` 추가
    - `bus.append(proposal)` + `print_message` 직후 `spec_path.write_text(resp1.text, encoding="utf-8")` (reviewer 호출 전)
    - `run_session`에서 `mode=="plan"` 분기로 `spec_path = _resolve_spec_path(workdir, args.task, session_ts=session_ts)` 1회 계산
    - `_run_session_end_only` / `_critical` / `_full` 3종 시그니처 + `run_turn` 호출에 `spec_path` 전달
  - `tests/test_spec_autosave.py`: run_turn 3 + run_session 4 = 7 통합 케이스 (mock driver/reviewer + monkeypatch `_resolve_runner` / `TriggerListener` / `prompt_decision` / `prompt_end_or_iterate`) (~140 LOC 누적)
- 검증:
  - `pytest tests/test_spec_autosave.py -q` → 17/17 pass
  - 회귀: `pytest -q` → 166/166 pass (158 prior + 8 prior workdir + 17 신규 - 17 prior == net +17)
  - 시그니처 노출: `inspect.signature(run_turn)` → `spec_path: pathlib.Path | None = None` 확인
  - 시연 slug: `_task_to_slug("Python add(a, b) 함수 작성") = "python-add-a-b-함수-작성"` ✓

## 문서 cascade (sync-docs 수동)

- `docs/dev-docs/systems/orchestrator.md`:
  - `_task_to_slug` / `_resolve_spec_path` helper 단락 추가 (`_now_ts` 직후)
  - `run_turn` 시그니처 한 줄 갱신 (`spec_path=None` 명시)
  - **spec_path wiring** 단락 추가 (UI wiring 단락 직전 — `:133` 부근)
- `docs/runtime-docs/protocol.md` §3 직후 — **모드별 산출물 표** 추가 (run/plan/implement/compare 4행)
- `docs/dev-docs/Documentation-Checklist.md` §1.1 — `_task_to_slug` / `_resolve_spec_path` 매핑 행 신규
- `docs/dev-docs/Plans/upcoming-plans.md`:
  - mermaid에 P013(completed) + P014(backlog) 노드·간선 추가
  - plan 013 entry 신규 단락 (의도/Phase/산출 핵심/의존)
- `README.md` 〈현재 동작 모드〉 — `--mode plan` 줄 갱신 (spec.md auto-save 산출 narrative)

## 완료 기준 (01-plan.md §6)

- [x] (Phase A) `_task_to_slug` helper + 단위 테스트 6 케이스 pass (영문/한글/특수/장문/빈/all-special)
- [x] (Phase A) `_resolve_spec_path` helper + 단위 테스트 4 케이스 pass (정상/충돌-session_ts/specs/ mkdir/절대경로)
- [x] (Phase B) `run_session`/`run_turn` 시그니처 확장 (`*, spec_path: Path | None = None`) — 기존 회귀 0
- [x] (Phase B) mock run_session(mode='plan') 통합 케이스 — `<workdir>/specs/<slug>.md` 파일 존재 + planner content 정확 보존 (end-only/critical/full 3 분기 모두)
- [x] (Phase B) 동일 workdir 재호출 시 `<slug>-<session_ts>.md` 접미사 fallback 동작 (Phase A test_resolve_spec_path_collision_session_ts에서 검증)
- [x] sync-docs 수동 갱신 완료 (5 SSOT)
- [x] `pytest -q` 회귀 0 + 신규 19 케이스 pass (총 168)
- [x] review-code P0/P1 = 0 (P2 5건은 직접 위협 X — 사용자 판단)
- [ ] 실 호출 시연 (`dialectic run --mode plan ...`) — API 비용으로 사용자 명시 시점 진행

## 권고

- 사용자 명시 후 실 호출 시연 1회 (post-010 default workdir에서 `~/.local/share/dialectic/runs/<ts-id>/specs/<slug>.md` 생성 확인)
- `commit` 호출 시 plan 010 (uncommitted) + plan 013 산출 분리 commit 권고 (의미 단위 분리)

## 사후 갱신 (review-code 후 사용자 추가 요청)

- **plan 종료 시 stderr 안내에 spec.md 경로 추가** (`run_session` finally 블록):
  - `spec_path: Path | None = None` 사전 선언 위치를 `cleanup = False` 직후로 이동 (try 외부 가시성 확보)
  - finally 블록에서 `spec_path is not None and spec_path.exists()` 시 `spec.md: <path>` 1줄 추가
  - 빈 응답·write 실패 시 미노출 (defensive)
  - 신규 테스트 2건 추가 (`test_spec_autosave_stderr_announce_plan_mode` / `_run_mode_no_spec`) — Phase B 누적 9 → 11
  - `pytest -q` 168/168 pass (회귀 0)
- `docs/dev-docs/systems/orchestrator.md` `spec_path wiring` 단락에 stderr 안내 narrative 1문장 추가
