# orchestrator + cli

`src/orchestrator.py` (~398 LOC) + `src/cli.py` (~67 LOC) 진리문서.

## 모듈 상수

| 상수 | 값 | 의미 |
|---|---|---|
| `MODE_ROLES` | `{"run": {driver:"implementer", reviewer:"spec-reviewer"}, "plan": {driver:"planner", reviewer:"plan-reviewer"}, "implement": {driver:"implementer", reviewer:"spec-reviewer"}}` | `protocol.md §3` 1:1 |
| `ROLE_FILE` | `{"implementer": Path(...).parent.parent / "docs/runtime-docs/roles/implementer.md", ...}` 4 path | `build_prompt` §1 ROLE 입력 |
| `META_SEQ_SENTINEL` | `99` | `_meta_msg`의 `seq_in_turn` (turn 내 최후 위치) |
| `DEFAULT_TIMEOUT_S` | `300` | subprocess timeout (code-conventions §3 명시 필수) |

## 핵심 헬퍼

### `_now_ts() -> str`

```python
return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
```

`protocol.md §2 line 92` 1:1. 정규식 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$` 매치.

### `_detect_converged(text: str) -> bool` (outline/02 §2.9)

```python
last = text.rstrip().splitlines()[-1] if text.rstrip() else ""
return last.strip() == "[CONVERGED]"
```

reviewer 응답 마지막 비공백 줄이 정확히 `[CONVERGED]` 단독일 때만 True.

### `SENTINEL_META(workdir, vendor="system", agent_cli="system", latency_ms=0, convergence_streak=None) -> Meta`

14 필드 일관 채움. `def` 정의 (PEP 8 E731 회피). 시스템 sentinel 메시지(`_task_msg`/`_meta_msg`/`_error_msg` exception fallback)에 사용.

### `build_prompt(role, task, history, directive) -> str`

```
# 1. ROLE
{ROLE_FILE[role].read_text(encoding="utf-8")}    ← R-001 P0 (한국어 role.md)

# 2. TASK
{task}

# 3. HISTORY
{_serialize_history(history)}    ← 빈 history → "(이전 턴 없음)"

# 4. YOUR TURN
당신의 역할({role})로 위 ROLE 섹션의 책임을 수행하십시오.
§ '응답 전 셀프체크'의 모든 항목을 통과해야 응답이 유효합니다.

(directive: {directive or 'none'})
```

`protocol.md §5 :233-271` 1:1.

### `_serialize_history(history) -> str` (`protocol.md §5 :246-260`)

turn_id ≥ 1만 포함 (turn_id=0 task는 §2 TASK에 별도 주입 — 중복 차단). `itertools.groupby`로 turn별 묶음. 라벨:
- `decision` → `- USER (decision: {content}, directive: "{directive}")`
- `from_=="system"` → `- SYSTEM ({kind}): {content}`
- 그 외 → `- {ROLE.upper()} ({kind}): {content}`

빈 body → `(이전 턴 없음)`.

## 메시지 생성 헬퍼 4종

| 헬퍼 | 시그니처 | 호출 위치 |
|---|---|---|
| `_msg(turn_id, seq_in_turn, role, slot, mode, kind, content, *, parent_id, meta) -> Message` | driver/reviewer 응답 | `run_turn` |
| `_error_msg(turn_id, seq_in_turn, role, slot, mode, exc, workdir, *, parent_id, vendor="system", agent_cli="system", latency_ms=0, response_meta=None) -> Message` | 빈 응답·timeout·auth fail | `run_turn` |
| `_task_msg(task, mode, workdir) -> Message` | turn_id=0 첫 메시지 | `run_session` |
| `_meta_msg(turn_id, content, workdir, mode, *, parent_id, convergence_streak=None) -> Message` | auto_end_converged·auto-end (max-turns reached) | `run_session` |

**`_error_msg.response_meta`** (P1 fix): 빈 응답 case (정상 호출 + `text=""`)에 어댑터 응답 meta 전달 → token 4종 + cost + model 보존 (P-JSONL silent loss 차단). exception case는 None → `SENTINEL_META` fallback.

## 턴 라이프사이클

### `run_turn(turn_id, mode, *, driver_runner, reviewer_runner, bus, task, workdir, sessions_dir) -> None`

keyword-only 강제. `runtime-docs/systems/run-mode.md §2` mermaid 라이프사이클 R0~R4 구현.

```
1. history = bus.read_all()                     # turn_id < N snapshot
2. driver: build_prompt + subprocess + bus.append(proposal)
   - 빈 응답 (resp.text.strip() = "") → _error_msg(response_meta=resp.meta) + return
3. reviewer: build_prompt(bus.read_all())       # proposal 포함
   - is_converged = _detect_converged(resp.text)
   - critique_meta = dataclasses.replace(resp.meta, convergence_streak=1 if is_converged else None)
   - bus.append(critique)
   - 빈 응답 → _error_msg + return
```

`dataclasses.replace`로 frozen Meta 변경 X (어댑터 meta 정직성 — 새 Meta 생성).

### `run_session(args: argparse.Namespace) -> int`

```
1. workdir = Path(args.workdir).resolve() if args.workdir else mkdtemp().resolve()
   - workdir == DIALECTIC_REPO_ROOT or in parents → cleanup leak 차단 + SystemExit (ADR-6, C-008)
2. cleanup = False  # Day 2: --workdir 미지정 시에도 결과 보존 (사용자 확인 통로, C-010)
3. ADR-9 fallback:
   - K = args.convergence_streak
   - if max_turns < K + 1 and K > 1:
       sys.stderr.write("K reduced to 1 (ADR-9, outline/02 §2.9)")
       K = 1
4. sessions_dir 생성 + bus = Bus(logs/messages.jsonl)
5. bus.append(_task_msg(args.task, args.mode, workdir))    # turn_id=0
6. for turn in range(1, args.max_turns + 1):
   - run_turn(...)
   - last_msg = bus.read_all()[-1]
   - if last_msg.kind == "error" and last_msg.turn_id == turn:
       # protocol.md §9 정합 — fatal error (auth/CLI 미설치/timeout/parse fail) 즉시 break.
       # retry 1회는 Day 3+ deferred (C-009).
       bus.append(_meta_msg("auto-end (error: ...)", parent_id=last_msg.msg_id)) + return 0
   - last_critique = next(reverse iter, kind=="critique" + turn_id==turn)
   - if convergence_streak == 1: streak += 1
       if streak >= K: bus.append(_meta_msg("auto_end_converged", convergence_streak=K)) + return 0
     else: streak = 0
7. fallthrough: bus.append(_meta_msg("auto-end (max-turns reached)"))
8. finally:
   - if cleanup: shutil.rmtree(workdir)  # Day 2 default cleanup=False — 미실행
   - else: sys.stderr.write(workdir 보존 + messages.jsonl + raw streams 경로 안내)
```

### `_resolve_runner(name) -> AgentRunner`

`{"codex": CodexRunner(), "claude": ClaudeRunner()}[name]`. invalid name → 친절 ValueError (mock은 Day 3+).

## cli

### argparse subparsers 2개

| 서브커맨드 | 인자 |
|---|---|
| `run` | `--task`(필수), `--workdir`, `--driver`, `--reviewer`, `--max-turns`, `--mode`, `--convergence-streak`, `--interactive` |
| `doctor` | (인자 없음) |

`--mode choices=["run"]` (Day 2 한정 — Day 3+ plan/implement/compare 추가 시 choices 확장. `MODE_ROLES` dict는 이미 plan/implement 키 보존이라 한 줄 변경).

`--interactive choices=["end-only"]` (Day 2 한정 — Day 3+ full/critical 추가 + 6지선다 분기 + Enter=iterate default).

### entry-point

`pyproject.toml:23` `dialectic = "src.cli:main"`. `pip install -e .` 후 `dialectic` 명령 직접 실행.

## 변경 시 갱신 영향

| 코드 변경 | 갱신 대상 |
|---|---|
| `MODE_ROLES` dict 키 추가/제거 | 본 §모듈 상수 + `protocol.md §3` + `runtime-docs/systems/INDEX.md` 4 모드 매트릭스 + 영향 받는 모드 파일 |
| `run_turn`/`run_session` 분기 추가 | 본 §턴 라이프사이클 + `runtime-docs/systems/<mode>.md` |
| `[CONVERGED]` 알고리즘 (outline/02 §2.9) | 본 §_detect_converged + `run-mode.md` |
| ADR-9 fallback 가드 | 본 §run_session + `run-mode.md §4` |
| 헬퍼 4종 시그니처 | 본 §메시지 생성 헬퍼 + `code-conventions.md` |
| cli 인자 추가/제거 | 본 §cli + `runtime-docs/systems/<mode>.md §1` + `README.md` 데모 |
| `_now_ts` 형식 | 본 §_now_ts + `protocol.md §2:92` + `tests/test_schema.py` 정규식 |

## 관련 문서

- `runtime-docs/systems/run-mode.md` — 모드 단위 진리 (본 모듈이 구현)
- `agents.md` — 어댑터 인터페이스 (driver/reviewer 호출 대상)
- `jsonl-bus.md` — Message/Meta 스키마 (헬퍼 4종이 생성)
- `cwd-isolation.md` — ADR-6 메커니즘 (run_session repo-root 차단)
- `architecture.md` ADR-1·ADR-3·ADR-9 (stateless·모드↔role 매핑·[CONVERGED] streak)
