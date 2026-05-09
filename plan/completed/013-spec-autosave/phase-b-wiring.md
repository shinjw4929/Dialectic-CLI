# Phase B · orchestrator wiring + 통합 테스트 — 013-spec-autosave

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: A (Phase A의 `_task_to_slug` + `_resolve_spec_path` helper 사용)
- 병렬 그룹: —
- 예상 LOC: ~25 (코드) + ~30 (테스트)

## 1. 목표

Phase A 산출 helper 2개를 `run_session`/`run_turn`에 wiring. mode=="plan" 분기에서 매 턴 driver(planner) 응답을 `<workdir>/specs/<slug>.md`로 자동 저장 (overwrite 정본 정책). 통합 테스트로 1턴 실 호출 → 파일 존재 + content 정확 보존 검증.

## 2. 입력

- Phase A 산출 — `_task_to_slug` + `_resolve_spec_path` 두 helper (`src/orchestrator.py` 모듈에 추가됨)
- [`src/orchestrator.py:442`](../../src/orchestrator.py) — `run_turn` def (driver 응답 받는 위치, `:487` `resp1 = driver_runner.run(...)`, `:517-521` proposal `_msg`/`bus.append`)
- [`src/orchestrator.py:604-707`](../../src/orchestrator.py) — `run_session` 메인. `:662-666` session_ts 산출 + session_dir/sessions_dir mkdir (NEW 로그 레이아웃, spec_path 계산 진입점). `:675-691` interactive 분기 (`_run_session_*` helper 3종 호출). **plan 010 Phase C 선행 시 ~+18줄 drift 예상 — execute 진입 시 grep 재확인 (01-plan §1.3 / §5 #7)**
- [`src/orchestrator.py:710` / `:764` / `:879`](../../src/orchestrator.py) — `_run_session_end_only` / `_run_session_critical` / `_run_session_full` 3 helper (`run_turn` 호출). 동일하게 post-010 drift 대상
- 사전 검증 사실: `resp1.text`에 driver 응답 본문 (planner 모드일 때 spec.md draft narrative). session_ts는 `:662`에서 이미 산출됨 — `_resolve_spec_path` 호출 시 재사용 (post-010 default workdir에서도 session_ts 산출 로직 동일)

## 3. 출력

### 3.1 `run_session` 변경

```python
# spec
def run_session(args: argparse.Namespace) -> int:
    """... (기존 docstring 유지) + plan 모드 산출: <workdir>/specs/<slug>.md (plan 013).

    spec.md는 top-level <workdir>/specs/ — session 격리(:662-666)는 messages.jsonl/sessions/raw 한정.
    SSOT narrative(outline/04 :199, planner.md :11) 정합 + plan 014 implement 모드 spec 소비 path 단순화.
    """
    # ... 기존 workdir resolve / ADR-6 차단 / max_turns clamp / mock fallback (변경 X)

    # 기존 :662-666 session 격리 (변경 X)
    session_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_dir = workdir / session_ts
    sessions_dir = session_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    bus = Bus(session_dir / "messages.jsonl")
    bus.append(_task_msg(args.task, args.mode, workdir))

    # plan 013 — mode==plan일 때 spec_path 미리 계산 (task 불변, slug 1회만)
    # session_ts 재사용 → 충돌 fallback 파일명(<slug>-<session_ts>.md)이 session_dir과 1:1 매핑.
    spec_path: Path | None = None
    if args.mode == "plan":
        spec_path = _resolve_spec_path(workdir, args.task, session_ts=session_ts)

    # 기존 _run_session_* 분기 호출에 spec_path 전달 (3종 모두)
    if args.interactive == "end-only":
        return _run_session_end_only(
            args, K, max_turns_runtime, bus,
            driver_runner, reviewer_runner, workdir, sessions_dir,
            spec_path=spec_path,  # plan 013 추가
        )
    # critical/full 분기도 동일 추가 (3 helper 모두 keyword-only spec_path 전달)
```

### 3.2 `_run_session_end_only` / `_run_session_critical` / `_run_session_full` 시그니처 확장

```python
# spec
def _run_session_end_only(
    args, K, max_turns_runtime, bus,
    driver_runner, reviewer_runner, workdir, sessions_dir,
    *, spec_path: Path | None = None,  # plan 013 추가, default None
) -> int:
    """... 기존 docstring + spec_path 전달 narrative."""
    # turn loop 안에서 run_turn 호출 시 spec_path 전달
    run_turn(
        turn_id, args.mode,
        driver_runner=driver_runner, reviewer_runner=reviewer_runner,
        bus=bus, task=args.task, workdir=workdir, sessions_dir=sessions_dir,
        spec_path=spec_path,  # plan 013 추가
    )
```

3 helper 모두 동일 패턴 — keyword-only `*, spec_path: Path | None = None` + run_turn 호출 시 그대로 전달.

### 3.3 `run_turn` 변경

```python
# spec
def run_turn(
    turn_id: int, mode: str, *,
    driver_runner: AgentRunner, reviewer_runner: AgentRunner,
    bus: Bus, task: str, workdir: Path, sessions_dir: Path,
    spec_path: Path | None = None,  # plan 013 추가, default None (회귀 0)
) -> None:
    """... 기존 docstring + spec_path가 None이 아니면 driver 응답 후 spec.md write."""
    # ... 기존 driver 호출 (resp1 = driver_runner.run(...))
    # ... 기존 bus.append(_msg(turn_id, 1, driver_role, "driver", mode, "proposal", resp1.text, ...))
    
    # plan 013 — mode=="plan" + spec_path 활성 시 매 턴 overwrite
    if spec_path is not None:
        spec_path.write_text(resp1.text, encoding="utf-8")
    
    # ... 기존 reviewer 호출 + bus.append (변경 없음)
```

### 3.4 통합 테스트 — `tests/test_spec_autosave.py` 추가 (Phase A 위에 누적)

```python
# spec
def test_spec_autosave_run_turn_writes(tmp_path, monkeypatch):
    """run_turn 호출 시 spec_path 활성이면 driver 응답을 파일로 write.
    
    mock driver_runner: resp1.text = "Mock spec body"
    mock reviewer_runner: resp2.text = "Mock critique"
    검증: spec_path.exists() + read_text() == "Mock spec body"
    """

def test_spec_autosave_run_turn_no_spec_path(tmp_path, monkeypatch):
    """spec_path=None이면 file write X (회귀 보호)."""

def test_spec_autosave_overwrite_per_turn(tmp_path, monkeypatch):
    """동일 spec_path로 run_turn 2회 호출 시 마지막 응답이 정본 (overwrite)."""

def test_spec_autosave_run_session_plan_mode_end_only(tmp_path, monkeypatch):
    """run_session(mode='plan', interactive='end-only') 진입 시 spec_path 자동 계산 + run_turn 전달.

    args.mode='plan', args.task='Add a, b function', args.interactive='end-only'
    검증: <workdir>/specs/add-a-b-function.md 존재
    """

def test_spec_autosave_run_session_plan_mode_critical(tmp_path, monkeypatch):
    """run_session(mode='plan', interactive='critical') 분기에서도 spec_path 전달 — §6.2 회귀 차단.

    `_run_session_critical` 시그니처 누락 시 spec.md 미생성으로 fail.
    """

def test_spec_autosave_run_session_plan_mode_full(tmp_path, monkeypatch):
    """run_session(mode='plan', interactive='full') 분기에서도 spec_path 전달 — §6.2 회귀 차단.

    `_run_session_full` 시그니처 누락 시 spec.md 미생성으로 fail.
    """

def test_spec_autosave_run_session_run_mode_no_spec(tmp_path, monkeypatch):
    """run_session(mode='run') 진입 시 spec_path=None — specs/ 디렉토리 자체 미생성."""
```

mock 패턴: `monkeypatch.setattr(orchestrator, "_resolve_runner", lambda v: MockRunner())` — driver/reviewer 응답 stub. 외부 API 호출 0.

### 3.5 실 호출 시연 (DoD §6 §B)

post-010 default workdir(`~/.local/share/dialectic/runs/<ts-id>/`) 가정. 시연 시점 010 미진행이면 `--workdir /tmp/dialectic-spec-demo` 명시로 대체.

```bash
# 시연 1 (post-010 default 흐름): mode=plan 1턴 → spec.md 파일 생성
dialectic run --task "Python add(a, b) 함수 작성" --mode plan --max-turns 1
# stderr: "[run_session] session 보존: ~/.local/share/dialectic/runs/<ts-id>/<session_ts>/"

# 검증 — workdir 자체는 매번 unique이라 default 흐름엔 충돌 0
WORKDIR=$(ls -td ~/.local/share/dialectic/runs/*/ | head -1)
ls "$WORKDIR/specs/"
# 기대: python-add-a-b-함수-작성.md (한글 truncate 후 slug)

cat "$WORKDIR/specs/"*.md | head -10
# 기대: planner 응답 spec body (Spec · ... markdown)

# 시연 2 (사용자 명시 --workdir 재사용): 충돌 fallback 발동
dialectic run --task "Python add(a, b) 함수 작성" --mode plan --max-turns 1 --workdir /tmp/dialectic-spec-demo
dialectic run --task "Python add(a, b) 함수 작성" --mode plan --max-turns 1 --workdir /tmp/dialectic-spec-demo
ls /tmp/dialectic-spec-demo/specs/
# 기대: python-add-a-b-함수-작성.md + python-add-a-b-함수-작성-<session_ts>.md (접미사, session_dir 디렉토리명과 1:1 매핑)
ls /tmp/dialectic-spec-demo/
# 기대: specs/ + <session_ts_1>/ + <session_ts_2>/ (specs는 top-level, messages.jsonl은 session 격리)
```

## 4. 작업 단위

- [ ] (Pre-execute) `grep -n "def run_session\|session_ts = datetime\|def _run_session_" src/orchestrator.py`로 post-010 line drift 흡수 — 발견 줄로 본 phase 이후 인용 갱신 (plan 010 Phase C §4 동일 패턴)
- [ ] `src/orchestrator.py` `run_session` (`:604-707` — post-010 drift 대상)에 `spec_path` 계산 로직 추가 (`session_ts` 산출·session_dir mkdir 직후, mode=="plan" 분기, `session_ts` 재사용)
- [ ] `_run_session_end_only` / `_run_session_critical` / `_run_session_full` 3 helper 시그니처에 `*, spec_path: Path | None = None` 추가
- [ ] 3 helper 본문에서 `run_turn` 호출 시 `spec_path=spec_path` 전달
- [ ] `run_turn` 시그니처에 `*, spec_path: Path | None = None` 추가
- [ ] `run_turn` 본문 driver 응답 (`resp1`) 받은 직후 `if spec_path is not None: spec_path.write_text(resp1.text, encoding="utf-8")` 추가
- [ ] `tests/test_spec_autosave.py`에 통합 테스트 7 케이스 추가 (Phase A 위 누적) — `run_turn` 직접 3종(write/no-spec/overwrite) + `run_session` 4종(end-only/critical/full plan + run mode no-spec)
- [ ] mock pattern: `MockRunner` class 또는 `unittest.mock.MagicMock` 활용 — driver/reviewer 응답 stub
- [ ] `pytest -q` 전체 회귀 0 확인 (특히 `test_orchestrator_decision_wiring.py` plan 009 산출 + plan 011 산출)
- [ ] 실 호출 시연 2종 (위 §3.5) — workdir에 spec.md 파일 + 충돌 시 timestamp fallback 시각 검증

## 5. 검증

- `python -c "from src.orchestrator import run_session, run_turn; import inspect; print(inspect.signature(run_turn))"` — `spec_path` 파라미터 노출 확인
- `pytest -q tests/test_spec_autosave.py` Phase A·B 누적 ≥17 케이스 pass (Phase A 10 + Phase B 7)
- `pytest -q` 전체 회귀 0 (특히 plan 011 메뉴 wiring 회귀 + plan 009 critical 모드 회귀)
- 실 호출 시연 1: `dialectic run --mode plan ...` → `<workdir>/specs/<slug>.md` 파일 생성 + content 정확
- 실 호출 시연 2: 동일 workdir 재호출 → 충돌 fallback 동작 (`<slug>-<session_ts>.md` 추가, session_dir 디렉토리명과 1:1 매핑)
- sync-docs 호출 결과: `docs/dev-docs/Documentation-Checklist.md` §1.1 `src/orchestrator.py` 매핑 .md 모두 갱신 (systems/orchestrator.md + protocol.md + roles/planner.md cross-check + current-implementation-flow.md)

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **mock driver 응답 patten**
   - `MockRunner` 또는 `MagicMock`으로 `driver_runner.run(...)` stub
   - 응답 객체는 `text` 속성 + 기타 meta — `unittest.mock.MagicMock`으로 단순 wrap
   - 기존 `tests/test_orchestrator_decision_wiring.py` mock 패턴 재사용 권고 (사전 grep)

2. **3 helper 시그니처 동시 확장 — 누락 위험**
   - `_run_session_end_only` / `_run_session_critical` / `_run_session_full` 3 곳 모두 갱신 필요
   - Phase B 작업 단위 체크박스에 명시 (3 helper 각각)
   - `run_session`이 3 helper 호출 → 한 곳만 갱신 시 다른 분기에서 spec_path 전달 0 → mode=plan + critical/full 모드 spec.md 생성 X (회귀 결함)
   - 차단: §3.4 테스트 3종 (`test_spec_autosave_run_session_plan_mode_end_only` / `_critical` / `_full`)이 분기별 spec_path 전달 검증 — 한 helper 누락 시 해당 분기 테스트 fail

3. **spec.md write 시점 vs reviewer 호출 순서**
   - 본 plan 결정: driver 응답 후, reviewer 호출 전 write
   - 대안: reviewer 호출 후 write (driver+reviewer 모두 완료한 후 정본)
   - 대안 거부 이유: reviewer 실패해도 driver spec은 유효 — 사용자가 reviewer 실패 후에도 spec 활용 가능
   - 본 결정 위험: reviewer가 driver spec에 P0 결함 지적 + 사용자가 directive로 spec 수정 요청 → 다음 턴 driver가 새 spec 생성 → write overwrite (마지막 정본 정책 유지)

4. **mode=plan + interactive=critical/full + 사용자 e 결정**
   - planner.md `:139` "최종 spec.md는 사용자가 e(end) 결정 시점의 본 ROLE 출력"
   - 본 plan 정책: 매 턴 overwrite — 사용자 e 결정 시점의 마지막 driver 응답이 자연스럽게 정본
   - 단 사용자가 i(iterate) → 다음 턴 → e 시: 이전 턴의 spec이 overwrite로 사라짐 (의도된 동작)

5. **specs/ 디렉토리 git ignore 정책**
   - workdir이 `/tmp/...`이면 무관
   - 사용자 직접 입력 workdir이 git 추적 디렉토리면 specs/ 파일이 git status에 등장
   - 본 plan 외 — 사용자/별도 plan에서 .gitignore 결정

6. **plan 014 (`dialectic implement --spec`) 후행 의존**
   - 본 plan 산출 spec.md는 plan 014 진입 후 implement 모드 입력으로 활용
   - planner.md `:11` "추후 dialectic implement 모드에서 ... 입력" narrative는 plan 014 진입 전까지 narrative만 정합 (실제 호출 path 부재)
   - 본 plan은 spec.md 파일 생성까지만 책임

7. **spec.md 위치 vs 새 로그 레이아웃 (NEW)**
   - 로그 격리(`:662-666`)로 `<workdir>/<session_ts>/messages.jsonl` + `<workdir>/<session_ts>/sessions/`는 session-isolated
   - spec.md는 SSOT narrative(outline/04 `:199`/planner.md `:11`) 정합으로 **top-level `<workdir>/specs/<slug>.md` 유지** — session 격리 X
   - 충돌 fallback에서 `session_ts` 재사용(`<slug>-<session_ts>.md`) → log 디렉토리명과 1:1 매핑, 디버깅·tracking 정합
   - 사용자가 `<workdir>/<session_ts>/specs/`를 기대하는 회귀 가능성 → Phase A test `test_resolve_spec_path_specs_mkdir`가 top-level 검증
