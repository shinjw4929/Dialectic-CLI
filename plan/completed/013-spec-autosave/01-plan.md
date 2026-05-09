# Plan · 013-spec-autosave

## 0. 메타

- 작업 ID: `013-spec-autosave`
- 의도: `mode=plan` 호출 시 planner ROLE 응답을 매 턴 `<workdir>/specs/<slug>.md` 파일로 자동 저장. JSONL 텍스트 보존만 있던 상태 → 파일 시스템에 spec.md 산출 (outline + planner.md SSOT narrative와 wiring 정합)
- 관련 ADR / Q번호: ADR-6 (cwd 격리 — specs/는 workdir 하위로 차단 정합). 신규 ADR 불필요 (정책 변경 X)
- 예상 영향 범위: `src/orchestrator.py` (helper 2개 추가 + run_session(`:604`)/`_run_session_*` 3종(`:710`/`:764`/`:879`)/`run_turn`(`:442`) 시그니처 확장), 신규 단위 테스트 `tests/test_spec_autosave.py`, 문서 cascade (planner.md `:11`/`:139` narrative 정합 + protocol.md plan 모드 산출 명시 + systems/orchestrator.md)
- LOC 추정: ~70 LOC (코드) + ~80 LOC (테스트)
- 백로그 SSOT: plan 011 review-plan 1차 P0 #2 (spec.md 산출 메커니즘 부재) — plan 011은 menu wiring 한정 + JSONL 보존으로 분리 결정 (011 완료 — `plan/completed/011-menu-expansion/`)
- 진행 순서 의존: `011(완료) → 010 → 013` 권고. 010 Phase C가 `run_session` workdir 해소를 헬퍼로 추출 → AS-IS 줄 번호 line drift 흡수 필요 (§5 위험 #7)

## 1. AS-IS

### 1.1 planner 응답 보존 (JSONL 텍스트만)

- `src/orchestrator.py:469` `roles = MODE_ROLES[mode]` — mode=="plan" 시 driver_role="planner"
- `src/orchestrator.py:487` `resp1 = driver_runner.run(p1, ...)` — planner 응답 객체
- `src/orchestrator.py:517-521` `proposal = _msg(turn_id, 1, driver_role, "driver", mode, "proposal", resp1.text, ...)` + `bus.append(proposal)` — JSONL `kind=proposal, from=planner` content 필드로만 저장
- 별도 .md 파일 write 코드 0 (`grep -n "specs/\|spec\.md" src/orchestrator.py` 결과 0건 직접 확인)

### 1.2 SSOT narrative (구현 부재)

- `docs/runtime-docs/roles/planner.md:11` "산출물(`<workdir>/specs/<task_id>.md`)은 추후 `dialectic implement` 모드에서 ... 입력으로 사용된다"
- `docs/runtime-docs/roles/planner.md:139` "최종 spec.md는 사용자가 e(end) 결정 시점의 본 ROLE 출력. 이 spec.md가 곧 implement 모드의 입력 — 정확성이 결정적"
- `outline/04-requirements-and-modes.md:162` mermaid: `Plan --> PlanOut["계획자 ↔ 계획 검토자 ↔ 사용자<br/>산출물: <workdir>/specs/<task_id>.md"]`
- `outline/04-requirements-and-modes.md:199-200` "산출물 | `<workdir>/specs/<task_id>.md` (구체 spec)" + "종료 시 행동 | spec.md를 사용자가 보고 검토 → 다음 단계로"
- `outline/03-ux.md:46-50` `# 계획 모드 (task → spec.md)` + `dialectic implement --spec ./workdir-tmp/specs/dijkstra.md`
- 4 SSOT narrative 모두 `<workdir>/specs/<task_id>.md` 파일 존재 가정. 실제 wiring 0.

### 1.3 workdir / session 격리 / specs/ 디렉토리

> 줄 번호는 본 plan 진입 시점 코드 기준. **plan 010 Phase C 선행 시 ~+18줄 drift 예상** (`_resolve_workdir` 헬퍼 ~20 LOC 추가 + `:606-607` 2줄 → 1줄 축소). execute-plan 진입 시 `grep -n "def run_session\|session_ts = datetime\|def _run_session_"` 재확정 필수 (§5 위험 #7).

- `src/orchestrator.py:604` `def run_session(args)` 진입 — **post-010**: `_resolve_workdir` 호출자로 단순화
- `src/orchestrator.py:606-607` workdir resolve (`Path(args.workdir).resolve()` 또는 `tempfile.mkdtemp(prefix="dialectic-")`) — **post-010**: 1줄 `workdir = _resolve_workdir(args)`. plan 013 wiring은 `workdir` 변수만 사용하므로 의미 영향 0
- `src/orchestrator.py:616-625` ADR-6 차단 (workdir이 repo 루트/하위면 SystemExit). post-010도 동일 위치 책임 (헬퍼 외부에서 호출자 책임 유지 — plan 010 Phase C §3.1 docstring)
- `src/orchestrator.py:662-666` **session 격리 (NEW 레이아웃)**:
  ```python
  session_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
  session_dir = workdir / session_ts
  sessions_dir = session_dir / "sessions"
  sessions_dir.mkdir(parents=True, exist_ok=True)
  bus = Bus(session_dir / "messages.jsonl")
  ```
  → `<workdir>/<session_ts>/messages.jsonl` + `<workdir>/<session_ts>/sessions/` 격리. 같은 workdir 재호출 시 session별 분리(JSONL 누적·DAG 깨짐 차단). post-010 default는 workdir 자체가 unique per run (`~/.local/share/dialectic/runs/<ts-id>/`)이라 session_ts 격리는 사용자 `--workdir <existing>` 재사용 시점에만 의미 — default 흐름엔 한 폴더만 생성
- `src/orchestrator.py:675-691` `_run_session_*` 3종(end-only/critical/full) 분기 — `(args, K, max_turns_runtime, bus, driver_runner, reviewer_runner, workdir, sessions_dir)` 시그니처
- `src/orchestrator.py:710` `_run_session_end_only` 정의 (`:764` critical / `:879` full)
- `specs/` 디렉토리 자동 생성 0 (`grep -n "specs/" src/orchestrator.py` 결과 0건 직접 확인)
- **spec.md 위치 결정 (사용자 결정 d, NEW)**: SSOT narrative(outline/04 `:199`/`planner.md:11`) `<workdir>/specs/<task_id>.md` — **top-level** 유지(NOT `<workdir>/<session_ts>/specs/`). plan 014 implement 모드가 spec.md를 path로 소비하기 쉬움. session-ts 격리는 messages.jsonl/sessions/raw 한정. 충돌 fallback 시 `session_ts`(filename-safe `%Y%m%dT%H%M%SZ`)를 접미사로 재사용 — 기존 `_now_ts()` regex sub 변형 불필요.
- **post-010 default 흐름 결과**: `dialectic run --mode plan --task X` (--workdir 미지정) → `~/.local/share/dialectic/runs/<YYYYMMDD-HHMMSS>-<short-id>/specs/<slug>.md` 생성 + `~/.local/share/dialectic/runs/<...>/<session_ts>/messages.jsonl` 격리
- ADR-6 차단(`:616-625`)은 workdir 자체에만 적용 — workdir 하위 specs/는 자동 정합. post-010 default workdir(`~/.local/share/dialectic/runs/`)는 repo-root와 무관 → 차단 대상 0

### 1.4 task content 형식 (slug 입력)

- `src/orchestrator.py:248` `_task_msg(task: str, mode: str, workdir: Path)` — 자유 텍스트 task content를 turn_id=0 메시지로 저장
- 슬러그 변환 helper 0 (`grep -n "slug\|to_slug" src/` 결과 0건)
- 한글·특수문자·장문 task 모두 자유 입력 가능 (plan 011 wiring + 기존 `_input_task`)

## 2. TO-BE

### 2.1 신규 helper — `src/orchestrator.py`

| helper | 책임 | LOC |
|---|---|---|
| `_task_to_slug(task: str, *, max_len: int = 50) -> str` | task content → 안전한 파일명 slug. 영숫자/한글 유지, 특수문자→hyphen, 연속 hyphen 단일화, 양끝 hyphen 제거, truncate. 빈 결과 → "task" fallback | ~25 |
| `_resolve_spec_path(workdir: Path, task: str, *, session_ts: str) -> Path` | `<workdir>/specs/<slug>.md` 경로 결정. specs/ 디렉토리 mkdir. 충돌 시 `<slug>-<session_ts>.md` 접미사 fallback (run_session `:662` 산출 session_ts 재사용 — 별도 timestamp 변환 불필요) | ~20 |

### 2.2 `run_session` / `run_turn` wiring

- `run_session` (`:604-707`) — `:662-666` session_ts 산출·session_dir mkdir 직후, mode=="plan"이면 `spec_path = _resolve_spec_path(workdir, args.task, session_ts=session_ts)` 1회 계산 (task 불변, slug 캐시)
- `run_session` → `_run_session_*` helper 3종(`:710`/`:764`/`:879`)에 spec_path 전달 (keyword-only `*, spec_path: Path | None = None`)
- `_run_session_*` helper들이 `run_turn`(`:442`)에 spec_path 그대로 전달 (keyword-only)
- `run_turn` driver 응답(`resp1`) 받고 proposal `bus.append`(`:521`) 직후:
  ```python
  if spec_path is not None:
      spec_path.write_text(resp1.text, encoding="utf-8")
  ```
- 매 턴 overwrite (마지막 정본 정책, 사용자 결정 b)

### 2.3 신규 단위 테스트 — `tests/test_spec_autosave.py`

- `_task_to_slug` 케이스 ≥6: 영문 단순 / 한글 / 특수문자 / 장문 truncate / 빈 입력 / 모두 특수문자 (fallback)
- `_resolve_spec_path` 케이스 ≥4: 정상 경로 / 충돌 시 timestamp 접미사 / specs/ 디렉토리 자동 생성 / workdir 절대경로 정합

### 2.4 통합 테스트 (Phase B §5 시연)

- `dialectic` 메뉴 또는 `dialectic run --task X --mode plan --max-turns 1` 호출
- workdir에 `specs/<slug>.md` 파일 존재 검증
- 파일 content가 JSONL `kind=proposal, from=planner`의 content와 동일한지 확인

### 2.5 문서 cascade

- `docs/dev-docs/systems/orchestrator.md` — helper 2개 추가 narrative + run_turn 시그니처 확장. **plan 010 cascade와 동시 수정 영역** — 010 후행 시점이면 010이 추가한 `_resolve_workdir` 단락 cross-link, 010 선행 시점이면 본 plan이 cross-link 추가
- `docs/runtime-docs/protocol.md` — plan 모드 산출물 (`specs/<slug>.md`) 명시 (현재 systems/<mode>.md만 있고 protocol에 spec.md 산출 명시 없을 가능성, 사전 grep 권고)
- `docs/runtime-docs/roles/planner.md` — `:11` narrative가 이제 실제 wiring 보장 (narrative 변경 X, wiring 정합 cross-check)
- `docs/dev-docs/Documentation-Checklist.md` — 변경 매핑 자동 catch (`src/orchestrator.py` 기존 행)
- `docs/dev-docs/Plans/upcoming-plans.md` — **plan 013 entry 신규 추가 필수** (현재 부재 확인 — `:23` mermaid의 P012/P011 부근에 plan 013 노드 + 우선순위 표 entry). plan 014 후행 의존 narrative + plan 010 ordering 의존(`011→010→013`) 도 함께 등록
- `README.md` — plan 010 Phase C가 "결과 위치" 섹션 갱신(default workdir 변경) → 본 plan은 plan 모드 산출 path(`<workdir>/specs/<slug>.md`)를 같은 섹션 또는 "사용 예시" 섹션에 1줄 추가. 010 진행 시점에 따라 영역 분담

## 3. Phase 인덱스

### 3.1 의존성 그래프

```mermaid
flowchart LR
    A["Phase A · helpers + 단위 테스트"]
    B["Phase B · orchestrator wiring + 통합 테스트"]
    A --> B
```

직렬 — Phase B가 Phase A의 helper 2개 (`_task_to_slug` + `_resolve_spec_path`)를 import.

### 3.2 Phase 파일 경로

| Phase | 경로 | 의존 | 병렬 그룹 |
|---|---|---|---|
| A · helpers | [phase-a-helpers.md](phase-a-helpers.md) | (없음) | — |
| B · orchestrator wiring | [phase-b-wiring.md](phase-b-wiring.md) | A | — |

## 4. 비기능 요구

- 외부 의존성 추가 0 (표준 라이브러리만 — `re` / `pathlib` / `datetime`)
- ADR-6 정합 — specs/는 workdir 하위라 차단 SSOT (orchestrator `:616-625`) 그대로 적용
- UTF-8 인코딩 명시 (`Path.write_text(text, encoding="utf-8")`) — 한글 slug 지원
- run_turn 시그니처 확장은 keyword-only `*` + default None — 회귀 0 (기존 호출자 인자 추가 안 해도 동작)
- 매 턴 overwrite — disk I/O 매 턴 1회 (1KB-10KB 수준, negligible)

## 5. 위험 (Phase 횡단)

1. **slug 한글 + filesystem encoding**
   - WSL/Linux는 UTF-8 default — 한글 파일명 정합
   - macOS는 NFD normalization (한글 자모 분리)
   - Windows는 deprecated (본 도구 WSL 가정 — code-conventions.md §환경)
   - 차단: Phase A 단위 테스트에 한글 케이스 + 파일 생성 검증 (tmp_path 활용)

2. **mock 어댑터 부재 (plan 007 deferred) — 통합 테스트 실 호출 비용**
   - Phase B §5 통합 시연은 codex 또는 claude 1턴 호출 필요 (API 비용)
   - mock 어댑터 도입 후 비용 0 회귀 가능 (별도 plan)
   - 본 plan은 실 호출 1회로 DoD 충족

3. **run_turn / `_run_session_*` 시그니처 확장 회귀**
   - `*, spec_path: Path | None = None` keyword-only + default None
   - 기존 호출자(`_run_session_*` 3종 — `:710`/`:764`/`:879`) 모두 인자 추가 필요 — Phase B 작업 단위에서 일괄 갱신
   - default None이라 plan 011 회귀 (mode=="run" 호출) 0
   - 분기별 누락 위험 차단: Phase B §3.4 `run_session_plan_mode_{end_only,critical,full}` 3종 테스트로 helper별 spec_path 전달 검증

4. **매 턴 overwrite — 중간 턴 실패 시 부분 spec.md 잔재**
   - 본 plan 정책: 매 턴 overwrite. driver 응답 후 reviewer 실패 시 driver spec은 이미 보존 (사용자 의도 — phase B §6.3)
   - 사용자 i(iterate) 후 e(end) 시 마지막 턴 spec이 정본 — 이전 턴 spec은 의도적으로 사라짐
   - session 격리(`:662-666`) 덕분에 이전 session spec.md는 collision fallback으로 별도 보존 — 데이터 손실 0

5. **spec.md 위치 — top-level vs session 격리 (NEW, 로그 레이아웃 변경 영향)**
   - 현재 messages.jsonl/sessions/raw은 `<workdir>/<session_ts>/` 격리(`:662-666`)
   - spec.md는 SSOT narrative(outline/04 `:199`/`planner.md:11`) 정합 위해 **top-level `<workdir>/specs/<slug>.md` 유지** — plan 014 implement 모드 spec 소비 path 단순화
   - 충돌 fallback에서 `session_ts` 재사용(`<slug>-<session_ts>.md`) — log 디렉토리명과 1:1 매핑되어 디버깅·tracking 정합

6. **plan 014 (`dialectic implement --spec`) 후행 의존**
   - 본 plan 산출 spec.md는 plan 014에서 implement 모드 입력으로 활용
   - 본 plan에서 `--spec` subparser는 미구현 — narrative만 명시
   - sync-docs cascade: planner.md `:11` "추후 dialectic implement 모드에서 ... 입력" 표현은 plan 014 진입 전까지 부분 narrative만 만족 (실제 호출 path는 plan 014 진입 후)

7. **plan 010 (observability) 진행 순서 의존 — line drift**
   - 권고 순서: `011(완료) → 010 → 013`. 010 Phase C가 `_resolve_workdir` 헬퍼 추출로 `run_session :606-607`을 1줄(`workdir = _resolve_workdir(args)`)로 축소 → 후속 라인 모두 drift
   - 본 plan AS-IS 인용 줄(`:604`/`:662-666`/`:675-691`/`:710`/`:764`/`:879`)은 010 선행 시 모두 ~1-2줄 위로 이동
   - 차단: execute-plan 진입 시 `grep -n "def run_session\|session_ts = datetime\|def _run_session_"` 재확인 (010 Phase C §4 동일 패턴) — 발견 줄로 본 plan 인용 갱신 후 wiring
   - 의미적 충돌 0 — 010 Phase C 산출 default workdir(unique per run)은 본 plan collision fallback narrative와 정합 (default 흐름에선 spec.md 충돌 0, `--workdir <existing>` 재사용 시점만 fallback 발동)
   - `docs/dev-docs/systems/orchestrator.md` cascade는 010 + 013 양쪽 추가 단락 — 후행자가 선행 narrative cross-link

## 6. 완료 기준 (Definition of Done)

- [ ] (Phase A) `_task_to_slug` helper 추가 + 단위 테스트 ≥6 케이스 (영문/한글/특수/장문/빈/all-special) pass
- [ ] (Phase A) `_resolve_spec_path` helper 추가 + 단위 테스트 ≥4 케이스 (정상/충돌-timestamp/specs/ mkdir/절대경로) pass
- [ ] (Phase B) `run_session`/`run_turn` 시그니처 확장 (`*, spec_path: Path | None = None`) — 기존 회귀 0
- [ ] (Phase B) `dialectic run --task <X> --mode plan --max-turns 1` 호출 → `<workdir>/specs/<slug>.md` 파일 존재 + planner content 정확 보존
- [ ] (Phase B) 동일 workdir 재호출 시 `<slug>-<session_ts>.md` 접미사 fallback 동작 (run_session `:662` 산출 session_ts 재사용 → log 디렉토리명과 1:1 매핑 검증)
- [ ] sync-docs 누락 0 (`docs/dev-docs/Documentation-Checklist.md` §1.1 `src/orchestrator.py` 행 매핑 + planner.md cross-check)
- [ ] review-code P0 = 0 (특히 keyword-only 시그니처 + UTF-8 인코딩 명시)
- [ ] `pytest -q` 회귀 0 + 신규 케이스 ≥17 (Phase A 10 + Phase B 7 — `_run_session_*` 3 분기 spec_path 전달 검증 포함)

## 7. 참조 .md

- [`docs/runtime-docs/roles/planner.md`](../../docs/runtime-docs/roles/planner.md) `:11`/`:139` — spec.md SSOT narrative
- [`outline/04-requirements-and-modes.md`](../../outline/04-requirements-and-modes.md) `:162`/`:199-200`/`:226-240` — plan 모드 산출 narrative
- [`outline/03-ux.md`](../../outline/03-ux.md) `:46-50`/`:131-132` — plan/implement narrative
- [`docs/runtime-docs/protocol.md`](../../docs/runtime-docs/protocol.md) — 메시지 스키마 (kind=proposal, from=planner)
- [`docs/dev-docs/architecture.md`](../../docs/dev-docs/architecture.md) ADR-6 — cwd 격리 (specs/는 workdir 하위 정합)
- [`docs/dev-docs/systems/orchestrator.md`](../../docs/dev-docs/systems/orchestrator.md) — helper 추가 cascade
- [`docs/dev-docs/Documentation-Checklist.md`](../../docs/dev-docs/Documentation-Checklist.md) §1.1 `src/orchestrator.py` — 변경 매핑
- `src/orchestrator.py:248` — `_task_msg` (task content turn_id=0 저장)
- `src/orchestrator.py:442` — `run_turn` def (driver 응답 받는 위치)
- `src/orchestrator.py:469` — `roles = MODE_ROLES[mode]`
- `src/orchestrator.py:487` — `resp1 = driver_runner.run(...)`
- `src/orchestrator.py:517-521` — proposal `_msg` + `bus.append`
- `src/orchestrator.py:604-707` — `run_session` 메인 진입
- `src/orchestrator.py:662-666` — session_ts 산출 + session_dir/sessions_dir mkdir 패턴 (NEW 로그 레이아웃, specs/는 top-level 별개)
- `src/orchestrator.py:675-691` — `_run_session_*` 3종 분기 (spec_path 전달 대상)
- `src/orchestrator.py:710` / `:764` / `:879` — `_run_session_end_only` / `_critical` / `_full` def
- `src/orchestrator.py:616-625` — ADR-6 SSOT (변경 X, 위임만)
- plan 011 review-plan 1차 P0 #2 narrative — 본 plan 분리 결정 SSOT
