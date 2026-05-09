# Phase D · orchestrator critical/full wiring + cascade — 009-user-synthesis-wiring

## 0. 메타

- Phase ID: D
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: A (CLI mode), B (TriggerListener), C (prompt_end_or_iterate)
- 병렬 그룹: —
- 예상 LOC: ~50 LOC + 테스트 ~30 LOC

## 1. 목표

`src/orchestrator.py:run_session` turn loop 3 mode 분기 + `_serialize_history`/`build_prompt`/`run_turn` 시그니처 확장 (keyword 인자, default False 회귀 0) + `_decision_msg` helper 신설 (decision kind 재사용) + `MAX_TURNS_HARD_CAP=20` (critical/full + 초기 args 가드) + SIGINT 핸들러 (phase-b R3 hand-off) + mock fallback (P-MOCK).

**i 분기 정책 = α**: trigger / converged / last_turn 모든 i = max_turns_runtime += 1 (단순 누적). 사용자 처음 입력 max_turns는 시작점, i 시 1턴씩 늘림. 사용자 결정 (옵션 α). 인지는 사용자 책임.

## 2. 입력

- `src/orchestrator.py:94-112 _serialize_history(history) -> str` — line 104 `if m.kind == "decision":` 분기 정합. `*, exclude_reviewer: bool = False` keyword 인자 추가
- `src/orchestrator.py:115-128 build_prompt(role, task, history, directive)` — directive 인자 이미 존재. line 123 `_serialize_history(history)`. `*, exclude_reviewer: bool = False` keyword 인자 추가 → 내부 호출에 전달
- `src/orchestrator.py:310-320 run_turn` keyword-only. `*, skip_reviewer: bool = False, exclude_reviewer_history: bool = False` keyword 인자 추가
- `src/orchestrator.py:343 build_prompt(driver_role, ..., directive=None)` driver call
- `src/orchestrator.py:411 build_prompt(reviewer_role, ..., directive=None)` reviewer call
- `src/orchestrator.py:412 reviewer_runner.run` — reviewer 호출 위치
- `src/orchestrator.py:299-307 _resolve_runner` — mock 미등록 (plan 007 deferred)
- `src/orchestrator.py:456-505` run_session AS-IS
- `src/orchestrator.py:511-516` error 분기
- `src/orchestrator.py:525-532` `streak >= K` (line 527) auto_end_converged
- `src/orchestrator.py:50-53, 254-296, 292` patch_applied seq=98 ADR-10 비대칭
- `src/orchestrator.py:_task_msg` / `_meta_msg` / `_patch_applied_msg` 패턴 — `_decision_msg` ref
- `src/ui.py:TriggerListener` (Phase B), `prompt_end_or_iterate(turn_id, reason)` (Phase C), `prompt_decision` (full 모드)
- `src/cli.py:74-77` (Phase A — choices 3종)

## 3. 출력

`src/orchestrator.py` 변경:

```python
# paste
MAX_TURNS_HARD_CAP = 20  # critical·full 모드 i 무한 방지 절대 상한 (모듈 상수)
```

```python
# spec
def _serialize_history(
    history: list[Message],
    *,
    exclude_reviewer: bool = False,
) -> str:
    """기존 본문 (turn_id>=1 sort + group + format) 유지.

    exclude_reviewer=True 시 m.kind == "critique" 메시지 제외 (full a 분기 —
    driver 응답 채택 → 다음 턴 prompt에서 reviewer critique 제외).
    decision 분기 (line 104) 그대로 유지 — content는 outline §3.3 SSOT key.
    """


def build_prompt(
    role: str,
    task: str,
    history: list[Message],
    directive: str | None,
    *,
    exclude_reviewer: bool = False,
) -> str:
    """AS-IS 4섹션 prompt 본문 유지. _serialize_history 호출에 exclude_reviewer 전달.
    full a 분기 시 run_turn이 exclude_reviewer=True 전달 → driver build_prompt에서
    reviewer critique 제외.
    """


def _decision_msg(
    turn_id: int,
    key: str,
    directive: str | None,
    workdir: Path,
    mode: str,
    *,
    parent_id: str | None,
) -> Message:
    """decision kind 메시지 helper (protocol.md:238 SSOT 재사용).

    필드:
      msg_id     = uuid4()
      from_      = "user", to = "implementer", slot = None
      seq_in_turn= 97 (직렬화 순: proposal=1 → critique=2 → decision=97
                       → patch_applied=98 → meta=99. 시간 순 ≠ 직렬화 순,
                       ADR-10 의도된 비대칭 — src/orchestrator.py:50-53.
                       사용자 직권 지시가 patch 내역보다 먼저 driver 다음 턴
                       prompt에 노출 — _serialize_history sort 정합)
      kind       = "decision" (재사용)
      content    = key (outline §3.3 a/r/m/i/e/s)
      directive  = directive 본문 또는 None
      meta       = Meta(vendor="user", agent_cli="user", model=None,
                        session_id=None, thread_id=None,
                        input_tokens=0, output_tokens=0,
                        cached_input_tokens=0, reasoning_output_tokens=0,
                        cost_usd=None, latency_ms=0,
                        is_mock=False, workdir=str(workdir))
    """


def _last_critique_msg_id(history: list[Message]) -> str | None:
    """history 역방향 탐색 — 마지막 critique kind msg_id."""


def _last_proposal_msg_id(history: list[Message]) -> str | None:
    """history 역방향 탐색 — 마지막 proposal kind msg_id (full s 분기 fallback)."""


def _setup_sigint_handler(listener: TriggerListener) -> Callable | int | None:
    """SIGINT 핸들러 등록 (phase-b R3 hand-off).
    abort 시 raw mode 복원 + sys.exit(130). 반환값 = 이전 핸들러 (__exit__ 시
    signal.signal로 복원). signal.signal 시그니처상 반환 타입은
    Callable | int | None — int는 SIG_DFL/SIG_IGN sentinel, None은 핸들러 부재.
    """


def run_session(args: argparse.Namespace) -> int:
    """기존 본문 유지 (workdir·cleanup·ADR-6·ADR-9 fallback 그대로).

    초기값 가드 (P1-ε):
      max_turns_runtime = min(args.max_turns, MAX_TURNS_HARD_CAP)
      if args.max_turns > MAX_TURNS_HARD_CAP:
          sys.stderr.write(
              f"--max-turns ({args.max_turns}) > MAX_TURNS_HARD_CAP "
              f"({MAX_TURNS_HARD_CAP}) — clamped\\n"
          )

    mock 모드 fallback (P-MOCK, 괄호 명시):
      mock_in_use = (args.driver == "mock") or (args.reviewer == "mock")
      interactive_in = args.interactive in ("critical", "full")
      if mock_in_use and interactive_in:
          sys.stderr.write("mock 모드는 critical/full 비호환 — end-only 강제 (P-MOCK)\\n")
          args.interactive = "end-only"
      ※ 현재 _resolve_runner(:299-307)에 mock 미등록. fallback 활성은 plan 007
        진입 후 — 본 plan 시점은 vacuous (unreachable).

    turn loop 3 mode 분기:

    end-only: 현재 동작 (변경 X)

    critical: while loop (i 분기 max_turns_runtime 동적 갱신 정합 — P0급 P1-새-1 fix)
        turn = 1
        while turn <= max_turns_runtime:
            with TriggerListener() as trigger:
                prev_handler = _setup_sigint_handler(trigger)
                try:
                    run_turn(...)  # default skip_reviewer=False, exclude_reviewer_history=False
                finally:
                    signal.signal(signal.SIGINT, prev_handler)
            # 종료 조건 평가 (error / converged / last_turn) — 기존 분기 재사용
            history_after = bus.read_all()
            # error 분기 (line 511-516)는 with 블록 안에서 처리 — 자동 cleanup
            converged_now = (streak >= K)
            last_turn_now = (turn == max_turns_runtime)
            should_prompt = (trigger.is_set() or converged_now or last_turn_now)
            if should_prompt:
                if converged_now:
                    reason = f"[CONVERGED] streak {K} 도달"
                elif last_turn_now:
                    reason = f"max-turns {max_turns_runtime} 도달"
                else:
                    reason = "Ctrl+F 트리거"
                key, directive = prompt_end_or_iterate(turn_id=turn, reason=reason)
                parent_id = _last_critique_msg_id(history_after)
                if key == "e":
                    bus.append(_meta_msg(turn, "auto_end_user", workdir, args.mode,
                                         parent_id=parent_id))
                    return 0
                if key == "i":
                    bus.append(_decision_msg(turn, "i", directive, workdir, args.mode,
                                             parent_id=parent_id))
                    max_turns_runtime += 1   # α 정책 — trigger/converged/last_turn 모두 +1
                    streak = 0
                    if max_turns_runtime > MAX_TURNS_HARD_CAP:
                        bus.append(_meta_msg(
                            turn,
                            f"auto_end_hard_cap (max_turns_runtime > {MAX_TURNS_HARD_CAP})",
                            workdir, args.mode, parent_id=parent_id))
                        return 0
            turn += 1

    full: while loop (i 분기 max_turns_runtime 동적 갱신 정합)
        listener 가동 X — 매 턴 prompt 자동
        turn = 1
        skip_reviewer_next = False
        exclude_reviewer_history_next = False
        while turn <= max_turns_runtime:
            run_turn(..., skip_reviewer=skip_reviewer_next,
                          exclude_reviewer_history=exclude_reviewer_history_next)
            history_after = bus.read_all()
            # parent_id 결정 — reset 이전 (P1-새-2 dead code fix)
            if skip_reviewer_next:
                parent_id = _last_proposal_msg_id(history_after)
            else:
                parent_id = _last_critique_msg_id(history_after)
            # 다음 턴 flag 리셋 (parent_id 결정 후)
            skip_reviewer_next = False
            exclude_reviewer_history_next = False
            key, raw_directive = prompt_decision(turn_id=turn, interactive_mode="full")
            # full r 분기 directive 자동 주입 (β inline 결정 — _summarize_critique helper 폐기)
            if key == "r" and not raw_directive:
                last_critique = next(
                    (m for m in reversed(history_after) if m.kind == "critique"),
                    None,
                )
                if last_critique is not None:
                    raw_directive = (
                        f"이전 턴 reviewer 비판 강조 채택: "
                        f"{last_critique.content[:200]}"
                    )
            bus.append(_decision_msg(turn, key, raw_directive, workdir, args.mode,
                                     parent_id=parent_id))
            if key == "a":
                exclude_reviewer_history_next = True
            elif key == "r":
                pass  # decision_msg는 위에서 append 완료 (directive 보존)
            elif key == "m":
                pass  # 현재 동작 (둘 다 history)
            elif key == "i":
                max_turns_runtime += 1
                streak = 0
                if max_turns_runtime > MAX_TURNS_HARD_CAP:
                    bus.append(_meta_msg(
                        turn,
                        f"auto_end_hard_cap (max_turns_runtime > {MAX_TURNS_HARD_CAP})",
                        workdir, args.mode, parent_id=parent_id))
                    return 0
            elif key == "e":
                bus.append(_meta_msg(turn, "auto_end_user", workdir, args.mode,
                                     parent_id=parent_id))
                return 0
            elif key == "s":
                skip_reviewer_next = True
            turn += 1
    """
```

`tests/test_orchestrator_decision_wiring.py` 신규 (~30 LOC) — ≥10 케이스:
- end-only CONVERGED → auto_end_converged (회귀)
- end-only max_turns 도달 → auto_end_max_turns (회귀)
- critical Y → auto_end_user
- critical n → 1턴 추가 (α 정책) + streak 0 + decision append
- critical text → 1턴 추가 + decision directive 보존
- critical i 반복 + hard_cap 도달 → auto_end_hard_cap
- args.max_turns=25 초기 가드 → max_turns_runtime=20 + stderr clamp
- full a → 다음 턴 build_prompt에 exclude_reviewer=True 전달 단언
- full s → 다음 턴 run_turn skip_reviewer=True 전달 단언 + parent_id=_last_proposal_msg_id
- full r + raw_directive=None → critique[:200] 자동 주입 단언
- full r + raw_directive 있음 → 사용자 입력 우선 단언
- full e → auto_end_user
- full i + hard_cap 도달 → auto_end_hard_cap
- mock + critical → end-only fallback narrative stderr (현재 vacuous, plan 007 진입 후 활성)

## 4. 작업 단위

- [ ] `src/orchestrator.py` 모듈 상단 `MAX_TURNS_HARD_CAP = 20` 상수 (paste)
- [ ] `_serialize_history` `*, exclude_reviewer: bool = False` 키워드 인자 + critique 필터. 기존 호출자 default False 회귀 0
- [ ] `build_prompt` `*, exclude_reviewer: bool = False` 키워드 인자 + 내부 `_serialize_history` 전달. 기존 호출자 default False 회귀 0
- [ ] `run_turn` `*, skip_reviewer: bool = False, exclude_reviewer_history: bool = False` 키워드 인자 + driver build_prompt(line 343)에 exclude_reviewer 전달 + reviewer 호출(line 411-412) 분기. default False 회귀 0
- [ ] `_decision_msg(turn_id, key, directive, workdir, mode, *, parent_id)` helper
- [ ] `_last_critique_msg_id(history)` / `_last_proposal_msg_id(history)` helper
- [ ] `_setup_sigint_handler(listener)` helper — 이전 핸들러 반환, `__exit__` `signal.signal(SIG, prev)` 복원
- [ ] `run_session` 초기 `max_turns_runtime = min(args.max_turns, MAX_TURNS_HARD_CAP)` + stderr 경고 (P1-ε)
- [ ] mock fallback 괄호 명시 (`(args.driver=="mock") or (args.reviewer=="mock")`) and `(args.interactive in ("critical","full"))` (P1-F). plan 007 미진입 시 vacuous narrative
- [ ] turn loop 3 분기 — end-only (`for ... in range`, AS-IS 유지) / critical (**`while turn <= max_turns_runtime`** with TriggerListener cleanup-restart) / full (**`while turn <= max_turns_runtime`** prompt_decision + 6 분기)
- [ ] critical 분기: should_prompt + reason 분기 (converged/last_turn/trigger) + `prompt_end_or_iterate(turn_id, reason)` + e/i 분기. **i 시 `max_turns_runtime += 1` (`if key == "i":` 블록 안 — directive None/text 모두 동일 처리, P1-G fix)**
- [ ] full 분기: prompt_decision + 6 분기. **a → exclude_reviewer_history_next=True. r → raw_directive 없으면 last_critique.content[:200] inline 자동 주입 (β inline 결정, `_summarize_critique` helper 폐기). s → skip_reviewer_next=True. i → max_turns_runtime += 1. e → auto_end_user. m → 현재 동작**
- [ ] **parent_id 결정을 `skip_reviewer_next = False` reset 이전에 위치 (P1-새-2 dead code fix)**
- [ ] **`auto_end_hard_cap` 메시지 placeholder 통일** — `f"auto_end_hard_cap (max_turns_runtime > {MAX_TURNS_HARD_CAP})"` critical/full 둘 다 동일 (P2-1 잔존 fix)
- [ ] `tests/test_orchestrator_decision_wiring.py` 신규 ≥10 케이스 (초기 가드 + 3 mode × 종료 매트릭스 + r 자동 주입 + mock fallback)
- [ ] `pytest tests/test_orchestrator_decision_wiring.py -q` pass

## 5. 검증

- `pytest tests/test_orchestrator_decision_wiring.py -q` ≥10 케이스 pass
- 컨텍스트 매니저 자동 cleanup 단언 (critical 분기 안 `return 0` 시 listener `__exit__` 호출 mock 단언)
- SIGINT 핸들러 단위 테스트: `os.kill(getpid(), signal.SIGINT)` → tcsetattr 복원 + sys.exit(130) 단언
- 초기 가드 단위 테스트: `args.max_turns=25` → `max_turns_runtime=20` clamp + stderr capsys 단언
- **while loop 동적 갱신 단위 테스트**: `args.max_turns=2`, critical i 1회 → `max_turns_runtime=3` → turn 3 진행 단언 (P1-새-1 fix 검증)
- **parent_id 결정 단위 테스트**: full s 직후 다음 턴 → `_last_proposal_msg_id` fallback 호출 단언 (P1-새-2 fix 검증)
- 실 호출 시연:
  - critical [CONVERGED] → `n` → 추가 1턴 (α 정책)
  - critical → Enter/Y → `auto_end_user`
  - full a → 다음 턴 build_prompt에 exclude_reviewer=True
  - full s → 다음 턴 reviewer 호출 skip
  - full r + 빈 입력 → critique[:200] 자동 주입 decision msg
  - mock + critical → `end-only` fallback (plan 007 진입 후 활성)
- 기존 회귀 0 — end-only AS-IS 동작 + `_serialize_history`/`build_prompt`/`run_turn` default 호출 회귀 0

## 6. 엣지케이스 / 위험 (Phase 한정)

- **TriggerListener cleanup-restart 정합**: 매 턴 `with` 진입/종료 비용 ms 단위
- **`return 0` 시 자동 cleanup**: critical 분기 안 모두 `with` 블록 안 `return` → Python 자동 `__exit__`
- **error 분기 + listener**: critical error도 `with` 블록 안 → return 시 자동 cleanup
- **last_turn vs converged_now 판정**: while loop에서 `turn == max_turns_runtime` last_turn. converged = `streak >= K`. 둘 다 True여도 prompt 1회
- **while loop 동적 갱신 정합 (P1-새-1)**: i 분기 `max_turns_runtime += 1` 즉시 다음 iteration 평가 — `for ... range`는 생성 시점 고정이라 동작 X. while 패턴 필수
- **parent_id reset 위치 (P1-새-2)**: `skip_reviewer_next = False` reset이 parent_id 결정 후. dead code 차단 — `_last_proposal_msg_id` fallback 도달 가능
- **full r 분기 inline (β)**: `_summarize_critique` helper 양산 폐기. critique.content[:200] inline — 단순. 사용자 입력 directive 우선 (raw_directive 비어있을 때만 자동 주입)
- **MAX_TURNS_HARD_CAP 도달**: meta `f"auto_end_hard_cap (max_turns_runtime > {MAX_TURNS_HARD_CAP})"` placeholder 통일
- **MAX_TURNS_HARD_CAP 초기 가드**: `args.max_turns > 20` 시 clamp + stderr (안전 우선)
- **mock + critical/full → end-only fallback (P-MOCK)**: 현재 vacuous (mock 어댑터 미등록). plan 007 진입 후 활성
- **SIGINT 핸들러 SIG_DFL 복원**: `_setup_sigint_handler` 반환값 = 이전 핸들러. `__exit__` `signal.signal(SIGINT, prev)` 복원
- **parent_id 통일 (P1-H)**: `_last_critique_msg_id` 기본, full s 직후 `_last_proposal_msg_id` fallback
- **decision seq=97 vs patch_applied seq=98**: ADR-10 의도된 비대칭. `_decision_msg` docstring + protocol.md §6 narrative
- **시그니처 확장 회귀**: 기존 호출자 default False 회귀 0. 단위 테스트로 단언
- **i 분기 indent (P1-γ')**: `if key == "i":` 블록 안 `bus.append(_decision_msg)` + `max_turns_runtime += 1` + `streak = 0` + `if max_turns_runtime > HARD_CAP` 가드. directive None/text 모두 동일 처리 (α 정책)
- **α 정책 사용자 인지 책임**: trigger/converged/last_turn 모든 i = +1. 사용자 처음 입력 max_turns는 시작점, i 시 누적 +1 (사용자 옵션 α 결정). hard_cap=20으로 절대 상한 보호
