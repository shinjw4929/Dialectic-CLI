# orchestrator + cli

`src/orchestrator.py` (~398 LOC) + `src/cli.py` (~67 LOC) 진리문서.

## 모듈 상수

| 상수 | 값 | 의미 |
|---|---|---|
| `MODE_ROLES` | `{"run": {driver:"implementer", reviewer:"spec-reviewer"}, "plan": {driver:"planner", reviewer:"plan-reviewer"}, "implement": {driver:"implementer", reviewer:"spec-reviewer"}}` | `protocol.md §3` 1:1 |
| `ROLE_FILE` | `{"implementer": Path(...).parent.parent / "docs/runtime-docs/roles/implementer.md", ...}` 4 path | `build_prompt` §1 ROLE 입력 |
| `META_SEQ_SENTINEL` | `99` | `_meta_msg`의 `seq_in_turn` (turn 내 최후 위치) |
| `META_PATCH_APPLIED_SEQ` | `98` | `_patch_applied_msg`의 `seq_in_turn` (ADR-10 R2.7). 시간 순(turn 내 발생)은 reviewer 앞이지만 직렬화 순(`(turn_id, seq_in_turn)` 정렬)은 reviewer 뒤 — 의도된 비대칭, driver 다음 턴 prompt 강조 효과 |
| `META_DECISION_SEQ` | `97` | `_decision_msg`의 `seq_in_turn`. 직렬화 순 proposal=1 → critique=2 → decision=97 → patch_applied=98 → meta=99. 사용자 직권 지시가 patch 내역보다 먼저 driver 다음 턴 prompt에 노출 (시간 순 ≠ 직렬화 순, ADR-10 비대칭 정합) |
| `MAX_TURNS_HARD_CAP` | `20` | critical/full 모드 i 분기 무한 누적 절대 상한 + 초기값 가드 (`args.max_turns > 20` 시 clamp + stderr) |
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

### `build_prompt(role, task, history, directive, *, exclude_reviewer=False) -> str`

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

`protocol.md §5 :233-271` 1:1. `exclude_reviewer=True` 시 `_serialize_history`에 전달 (full a 분기 — driver 응답 채택 후 다음 턴 prompt에서 critique 제외). default `False` 회귀 0.

### `_serialize_history(history, *, exclude_reviewer=False) -> str` (`protocol.md §5 :246-260`)

turn_id ≥ 1만 포함 (turn_id=0 task는 §2 TASK에 별도 주입 — 중복 차단). `exclude_reviewer=True` 시 `m.kind == "critique"` 메시지 제외 (full a 분기 wiring). `itertools.groupby`로 turn별 묶음. 라벨:
- `decision` → `- USER (decision: {content}, directive: "{directive}")`
- `from_=="system"` → `- SYSTEM ({kind}): {content}`
- 그 외 → `- {ROLE.upper()} ({kind}): {content}`

빈 body → `(이전 턴 없음)`. default `exclude_reviewer=False` 회귀 0.

## 메시지 생성 헬퍼 5종

| 헬퍼 | 시그니처 | 호출 위치 |
|---|---|---|
| `_msg(turn_id, seq_in_turn, role, slot, mode, kind, content, *, parent_id, meta) -> Message` | driver/reviewer 응답 | `run_turn` |
| `_error_msg(turn_id, seq_in_turn, role, slot, mode, exc, workdir, *, parent_id, vendor="system", agent_cli="system", latency_ms=0, response_meta=None) -> Message` | 빈 응답·timeout·auth fail | `run_turn` |
| `_task_msg(task, mode, workdir) -> Message` | turn_id=0 첫 메시지 | `run_session` |
| `_meta_msg(turn_id, content, workdir, mode, *, parent_id, convergence_streak=None) -> Message` | auto_end_converged·auto-end (max-turns reached) | `run_session` |
| `_patch_applied_msg(turn_id, workdir, mode, content, *, parent_id, apply_status, apply_error, files_changed) -> Message` (ADR-10 R2.7) | search-replace 적용 결과 (성공/실패 모두) | `run_turn` |
| `_decision_msg(turn_id, key, directive, workdir, mode, *, parent_id) -> Message` (Phase D wiring) | critical/full 모드 사용자 결정 — `kind="decision"`, `seq_in_turn=97`, `vendor="user"`, `agent_cli="user"`, 토큰 4종 0, `cost_usd=None`, `is_mock=False` | `run_session` critical/full 분기 |

`_patch_applied_msg`: `from_="system"`, `slot=None`, `kind="patch_applied"`, `seq_in_turn=META_PATCH_APPLIED_SEQ`. `meta`는 `dataclasses.replace(SENTINEL_META(workdir), apply_status=..., apply_error=..., files_changed=...)`로 ADR-10 3 필드 채움 (`patches`는 None — proposal 측 책임). `content`는 호출자(`run_turn`)가 만든 prefix `apply_status=...` 명시 요약 — driver의 reviewer critique 오인 차단 mitigation.

**`_error_msg.response_meta`** (P1 fix): 빈 응답 case (정상 호출 + `text=""`)에 어댑터 응답 meta 전달 → token 4종 + cost + model 보존 (P-JSONL silent loss 차단). exception case는 None → `SENTINEL_META` fallback.

## 턴 라이프사이클

### `run_turn(turn_id, mode, *, driver_runner, reviewer_runner, bus, task, workdir, sessions_dir, skip_reviewer=False, exclude_reviewer_history=False) -> None`

keyword-only 강제. `runtime-docs/systems/run-mode.md §2` mermaid 라이프사이클 R0~R4 구현. `skip_reviewer=True` (full s 분기) 시 reviewer 호출 skip + critique 미생성 (다음 턴 parent_id는 `_last_proposal_msg_id` fallback). `exclude_reviewer_history=True` (full a 분기) 시 driver `build_prompt`에 `exclude_reviewer=True` 전달 (이전 턴 critique 제외). 둘 다 default `False` 회귀 0.

```
1. history = bus.read_all()                     # turn_id < N snapshot
2. driver: with Spinner("[role: vendor] running..."): build_prompt + subprocess
   - spinner는 `try` 내부에서 build_prompt + runner.run만 wrap (호출 단위 boundary)
   - 빈 응답 (resp.text.strip() = "") → _error_msg(response_meta=resp.meta) + return
   - patches = extract_patches(resp.text)        # ADR-10 R2 patches 추출
   - proposal_meta = dataclasses.replace(resp.meta, patches=patches or None)
   - bus.append(proposal)                        # meta.patches에 1회로 기록 (P-JSONL append-only)
   - print_message(role_label, vendor_label, kind="proposal", text, meta)  # outline/03-ux §3.2:193-201 stdout 출력
2.6. R2.6 — if patches: status, error, files_changed = apply_patches(patches, workdir=workdir)
2.7. R2.7 — if patches: bus.append(_patch_applied_msg(... summary, apply_status, apply_error, files_changed))
   - summary prefix `apply_status=ok|failed` (driver 오인 차단 mitigation)
   - patches 0개면 R2.6/R2.7 skip — 노이즈 차단
3. reviewer: with Spinner(...): build_prompt(bus.read_all()) + subprocess  # proposal + patch_applied 포함
   - is_converged = _detect_converged(resp.text)
   - critique_meta = dataclasses.replace(resp.meta, convergence_streak=1 if is_converged else None)
   - bus.append(critique)
   - print_message(role_label, vendor_label, kind="critique", text, meta)  # outline/03-ux §3.2:204-225
   - 빈 응답 → _error_msg + return
```

`dataclasses.replace`로 frozen Meta 변경 X (어댑터 meta 정직성 — 새 Meta 생성). `apply_patches`는 path validation·dry-run·all-or-nothing commit·best-effort 롤백 (patch_apply.md 정통).

**UI wiring** (plan 008-ui-polish): driver/reviewer 호출은 `with stdin_canonical_off(), Spinner(...)` 중첩으로 wrap — Spinner는 stderr 진행 표시(`[{ROLE_LABEL_KO[role]}: {VENDOR_LABEL[runner.name]}] running... ⠋`, outline/03-ux §3.2:190 SSOT 1:1, isatty 가드 보유), `stdin_canonical_off`은 호출 동안 사용자 키 누름이 line으로 완성되어 다음 prompt에 누수되는 결함 차단(line discipline off + drain thread + INTR `\x03` 감지 시 SIGINT raise). 단계 종료 후 KeyboardInterrupt는 `cli._interactive_menu`의 `run_session` try/except까지 propagate되어 종료 확인 prompt로 처리(`_safe_input`과 동일 패턴). proposal/critique 정상 응답 시 `bus.append` 직후 `src/ui.py:print_message`로 stdout에 구분선·헤더(`✓ {latency}s · {tokens}` + cost optional)·본문 출력. ANSI 색상 outline §3.5:362 (proposal=cyan, critique=yellow). `kind in ("proposal", "critique")`만 처리 — 빈 응답·error 분기는 stdout 출력 X (후속 plan 검토).

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
4. 초기값 가드 (P1-ε):
   - max_turns_runtime = min(args.max_turns, MAX_TURNS_HARD_CAP)
   - if args.max_turns > MAX_TURNS_HARD_CAP: stderr 경고 (clamp 사실 보고)
5. mock fallback (P-MOCK, plan 007 deferred 후 활성):
   - if (args.driver=="mock") or (args.reviewer=="mock") and args.interactive in ("critical","full"):
       args.interactive = "end-only"  # 강제 (raw 키 stdin 비호환)
6. session_ts 생성(`datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")`) + session_dir = workdir/`<ts>` + sessions_dir = session_dir/sessions + sessions_dir.mkdir(parents=True) + bus = Bus(session_dir/messages.jsonl) + bus.append(_task_msg). plan 011 Bug 2 fix — workdir 재호출 시 세션 격리 보장 (이전 `<workdir>/logs/` 단계 제거 → `<workdir>/<ts>/`)

7. mode 분기 (3 분기):
   (a) end-only — AS-IS for ... in range(1, max_turns_runtime+1):
        - run_turn(...) + error 즉시 break + streak >= K 즉시 auto_end_converged
        - listener 가동 X, 사용자 prompt 0
   (b) critical — while turn <= max_turns_runtime:
        - 매 턴 with TriggerListener() as trigger + _setup_sigint_handler(trigger)
          (cleanup-restart 패턴 — 매 턴 시작 시 listener 새로 진입, finally signal 복원)
        - run_turn(...) 호출 (driver+reviewer normal)
        - error 즉시 auto-end
        - converged_now = (streak >= K), triggered = trigger.is_set(), last_turn_now = (turn == max_turns_runtime)
        - should_prompt = triggered or converged_now or last_turn_now
        - should_prompt 시 prompt_end_or_iterate(turn_id, reason) 호출:
            * key="e" → _meta_msg("auto_end_user") + return 0
            * key="i" → _decision_msg + max_turns_runtime += 1 + streak = 0
                       max_turns_runtime > MAX_TURNS_HARD_CAP 시 auto_end_hard_cap + return
   (c) full — while turn <= max_turns_runtime:
        - listener 가동 X (매 턴 prompt_decision 자동 호출)
        - run_turn(..., skip_reviewer=skip_reviewer_next, exclude_reviewer_history=...)
        - parent_id 결정 (skip_reviewer_next=True면 _last_proposal_msg_id fallback)
        - flag reset (parent_id 결정 후 — P1-새-2 dead code fix)
        - prompt_decision(turn_id, "full") → 6 분기 (a/r/m/i/e/s):
            a → exclude_reviewer_history_next = True
            r → directive 빈 입력 시 last_critique.content[:200] 자동 주입 (β inline)
            m → pass
            i → max_turns_runtime += 1, streak = 0, hard cap 가드
            e → auto_end_user + return 0
            s → skip_reviewer_next = True

8. fallthrough: bus.append(_meta_msg("auto-end (max-turns reached)"))
9. finally:
   - if cleanup: shutil.rmtree(workdir)  # Day 2 default cleanup=False — 미실행
   - else: sys.stderr.write(workdir 보존 + messages.jsonl + raw streams 경로 안내)
```

### 새 helper (Phase D wiring)

| helper | 책임 |
|---|---|
| `_last_critique_msg_id(history) -> str \| None` | history 역방향 탐색 — 마지막 critique kind msg_id. critical/full 모두 decision parent_id 통일 |
| `_last_proposal_msg_id(history) -> str \| None` | full s 분기 직후 critique 부재 시 parent_id fallback |
| `_setup_sigint_handler(listener) -> Callable\|int\|None` | SIGINT 핸들러 등록 — abort 시 listener `__exit__`로 raw mode 복원 + sys.exit(130). 반환값은 이전 핸들러 (caller가 with 종료 시 `signal.signal(SIGINT, prev)` 복원) |

### `_resolve_runner(name) -> AgentRunner`

`{"codex": CodexRunner(), "claude": ClaudeRunner()}[name]`. invalid name → 친절 ValueError (mock은 Day 3+).

## cli

### argparse subparsers 2개

| 서브커맨드 | 인자 |
|---|---|
| `run` | `--task`(필수), `--workdir`, `--driver`, `--reviewer`, `--max-turns`, `--mode`, `--convergence-streak`, `--interactive` |
| `doctor` | (인자 없음) |
| (default) | 인자 0 → `_interactive_menu()` 진입 |

`--mode choices=["run"]` (Day 2 한정 — Day 3+ plan/implement/compare 추가 시 choices 확장. `MODE_ROLES` dict는 이미 plan/implement 키 보존이라 한 줄 변경).

`--interactive choices=["end-only","critical","full"]` (plan 009 산출). CLI default `end-only`, 메뉴 진입 default `critical`. full 모드는 매 턴 끝 6지선다(a/r/m/i/e/s) prompt_decision 강제, critical 모드는 Ctrl+F 트리거 + CONVERGED/max-turns 종료 직전 prompt_end_or_iterate (Y/n/text), end-only 모드는 사용자 prompt 0 (자동화·CI).

### default 메뉴 진입 (`_interactive_menu`)

기획자 페르소나(outline/03-ux §3.1)의 default 진입로. `dialectic` 단독 실행 시 `_interactive_menu` 호출. Day 2 minimum cut: run 모드 + default 매핑(codex/claude) + `--interactive end-only` 고정. plan 008-ui-polish 보강: 헤더 1줄(default 매핑·인자 안내, 매번 노이즈 차단 위해 단축) + `with stdin_canonical_off(), Spinner("환경 점검 중..."):` 으로 `check_env()` wrap. `check_env()`는 claude/codex 양쪽 `version + auth/login`만 점검 (P-VENDOR 대칭) — `claude doctor`는 영구 제외 (codex 동등 명령 부재 + capture_output 호출 시 tty/pipe 분기로 30s+ hang). spinner 종료 후 `flush_stdin(grace_period_s=0.1)` — mode 복원·flush 사이 race window를 통과하는 fast-typing/auto-repeat keystroke 100ms 동안 추가 폐기. `stdin_canonical_off`는 termios로 line discipline 차단 — spinner 중 사용자 Enter가 line으로 완성되어 다음 `input()` prompt에 누수되는 root cause 차단(exit 시 모드 복원 + tcflush). `flush_stdin()`은 추가 안전망 drain. 활성 부족(N<M) 시 fail sub-check를 `tool/sub` 형식 1줄 출력. task input 등 모든 input은 `_safe_input` wrap — EOF/Ctrl-C 시 즉시 종료 X, "종료하시겠습니까? (Enter=종료, n=계속)" 확인 prompt 후 사용자 의지 명시 (실수 안전망). 내부적으로 `_readline_input`(`sys.stdin.readline()` 직접 사용)으로 `input()`의 GNU readline wide-char(한글 등 CJK) cursor 계산 결함 회피. 추가로 메뉴 진입 시 `stdin_utf8_mode` 컨텍스트로 line discipline IUTF8 iflag set — multi-byte 한 char 단위 Backspace로 (default off 시 byte 단위 → cursor 결함 root cause). Python termios 모듈 IUTF8 상수 미노출 빌드에선 `_LINUX_IUTF8 = 0o040000` hardcode fallback. trade-off: 좌우 이동·히스토리 등 line edit 기능 잃음(한 줄 입력 한정 메뉴라 영향 작음). prompt 자체도 짧게(`task> ` 등) + example·도움말 안내는 별도 print 라인. 빈 task 재요청 retry (종료는 Ctrl-C/EOF + 종료 확인 통과만) + max-turns 입력 단계(default 1, 빈 입력 fallback, 비정수/음수 retry) + 진행 확인 단계(`진행? [Y/n] (n=task 재입력):`, `n` 거부 시 task 재입력 outer 루프 continue, 빈/y/invalid는 Y default 진행). EOFError/KeyboardInterrupt 안전 종료(exit 0). `parser.parse_args` 재호출 회피 — `argparse.Namespace` 직접 구성으로 `sys.exit` 부작용 차단 (cli `args.func(args)` 패턴과 비대칭은 minimum cut 한정, 후속 plan에서 정합화 검토). 모드 선택·매핑 선택·턴 진행 화면(outline/03-ux §3.2 단계 2/4/5)은 후속 plan 분리.

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
- `jsonl-bus.md` — Message/Meta 스키마 (헬퍼 5종이 생성, Meta 18 필드)
- `cwd-isolation.md` — ADR-6 메커니즘 + §Layer 4 patch_apply 쓰기 경계
- `patch-apply.md` — ADR-10 search-replace 모듈 (`extract_patches`/`apply_patches`/`validate_patch_path`/`PatchApplyError`) — `run_turn` R2/R2.6에서 호출
- `architecture.md` ADR-1·ADR-3·ADR-9·ADR-10 (stateless·모드↔role 매핑·[CONVERGED] streak·search-replace 메커니즘)
