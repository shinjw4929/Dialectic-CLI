# run 모드 — 한 턴 E2E SSOT

`dialectic run` 명령의 동작 진리. Day 2 정식 검증 완료 (실 호출 18 tests passed).

## 1. 명령 표면

```bash
dialectic run --task <text> [--workdir <path>] [--driver {codex,claude}]
                            [--reviewer {codex,claude}] [--max-turns <int>]
                            [--mode {run}] [--convergence-streak <int>]
                            [--interactive {end-only}]
```

| 인자 | default | 설명 |
|---|---|---|
| `--task` | (필수) | 사용자 task 한 줄. driver/reviewer prompt §2 TASK에 주입 |
| `--workdir` | `tempfile.mkdtemp(prefix="dialectic-")` | 작업 디렉토리. **Day 2: 미지정 시에도 cleanup X — 결과 확인 통로 (C-010)**. 종료 시 stderr에 `workdir`+`logs/messages.jsonl`+`logs/sessions/` 경로 안내. **Dialectic-CLI repo 루트·하위 사용 불가 (ADR-6, SystemExit + mkdtemp leak 차단 — C-008)** |
| `--driver` | `codex` | thesis 발화 위치 |
| `--reviewer` | `claude` | antithesis 발화 위치 |
| `--max-turns` | `1` | 최대 turn 수. 도달 시 `auto-end (max-turns reached)` |
| `--mode` | `run` | Day 2는 `run`만. plan/implement/compare는 Day 3+ |
| `--convergence-streak` | `2` | reviewer `[CONVERGED]` 마커 누적 K턴 도달 시 `auto_end_converged` (outline/02 §2.9). ADR-9 fallback: `--max-turns < K+1` 시 K=1 + stderr 경고 |
| `--interactive` | `end-only` | Day 2는 `end-only` 단일. Day 3+에서 full/critical 추가 + 6지선다 |

## 2. 한 턴 라이프사이클

```mermaid
flowchart TD
    Start(["Turn N start"])
    R0["Resolve roles<br/>driver=implementer<br/>reviewer=spec-reviewer"]
    R1["build_prompt(driver)<br/>§1 ROLE = roles/implementer.md<br/>§2 TASK<br/>§3 HISTORY (turn_id<N)<br/>§4 YOUR TURN"]
    R2["subprocess: codex exec --json<br/>cwd=resolved_workdir<br/>응답에서 patches 추출 (ADR-10)<br/>append kind=proposal, slot=driver<br/>meta.patches=[...] or None"]
    R26["**R2.6** apply_patches(patches, workdir=workdir)<br/>(if patches; ADR-10 all-or-nothing)<br/>path validation → 빈 SEARCH 차단 → dry-run unique-match → commit write"]
    R27["**R2.7** append kind=patch_applied<br/>seq=98, from=system<br/>meta.apply_status=ok|failed<br/>content=apply_status=... (prefix 명시)"]
    R3["build_prompt(reviewer)<br/>§3 HISTORY = turn N proposal+patch_applied 포함"]
    R4["subprocess: claude -p<br/>(stdin: 4섹션 prompt)<br/>append kind=critique, slot=reviewer<br/>meta.convergence_streak = 1 if [CONVERGED] else None"]
    R5{"streak >= K?"}
    R6["append kind=meta<br/>content=auto_end_converged<br/>meta.convergence_streak=K<br/>early return"]
    R7{"turn < max_turns?"}
    R8["append kind=meta<br/>content=auto-end (max-turns reached)"]

    Start --> R0 --> R1 --> R2 --> R26 --> R27 --> R3 --> R4 --> R5
    R5 -- yes --> R6
    R5 -- no, streak reset/누적 --> R7
    R7 -- yes, N+=1 --> R1
    R7 -- no --> R8
```

`protocol.md §4 :226-248` 라이프사이클 mermaid의 run 모드 구현. R2.6/R2.7은 ADR-10 search-replace 메커니즘 (patches 0개면 skip — 노이즈 차단). R5/R6은 outline/02 §2.9 [CONVERGED] 메커니즘 보강.

## 3. 메시지 흐름 (실 호출 검증 기록)

`/tmp/dialectic-demo/logs/messages.jsonl` 4 라인 — 2026-05-08 실 호출 결과:

| 라인 | turn_id | seq_in_turn | from | kind | parent_id | meta 핵심 |
|---|---|---|---|---|---|---|
| 1 | 0 | 1 | system | task | null | vendor=system, is_mock=false |
| 2 | 1 | 1 | implementer | proposal | (task) | vendor=openai, agent_cli=codex, thread_id=..., reasoning_output_tokens=37, **patches=[...] or None (ADR-10)** |
| 2.5 | 1 | 98 | system | patch_applied | (proposal) | (있을 때만) **apply_status=ok\|failed, files_changed=[...]** (ADR-10 R2.7) |
| 3 | 1 | 2 | spec-reviewer | critique | (proposal 또는 patch_applied) | vendor=anthropic, agent_cli=claude, session_id=..., **convergence_streak=1**, cost_usd=0.063 |
| 4 | 1 | 99 | system | meta (auto_end_converged) | (critique) | vendor=system, **convergence_streak=1** |

`(seq_in_turn, ts)` 정렬 시 직렬화 순서는 `proposal(1) → critique(2) → patch_applied(98) → meta(99)` — patch_applied는 **시간 순**(turn 내 발생 순)으로는 critique 앞이지만 **직렬화 순**으로는 critique 뒤 (의도된 비대칭, ADR-10 §5.6 mitigation: driver 다음 턴 prompt에서 마지막 강조 효과 ↑).

DAG 무결성: `parent_id` 모두 직전 메시지 `msg_id`. task만 `parent_id=null`.

## 4. 종료 조건 (DoD `01-plan §6` + outline/04 §4.5.1)

```
+----------------------------------------------------------+
| 우선순위 (위에서 아래로 평가)                              |
+----------------------------------------------------------+
| 1. SystemExit  — workdir == repo 루트 또는 하위 (ADR-6)   |
|                  + mkdtemp leak 차단 (C-008)              |
| 2. fatal error — kind=error (auth/CLI 미설치/timeout/     |
|                  parse fail/빈 응답+stderr) 즉시 break     |
|                  → auto-end (error: ...) (C-009)          |
|                  retry 1회는 Day 3+ deferred              |
| 3. auto_end_converged — streak >= K (early return)       |
| 4. auto-end (max-turns reached) — turn 루프 fallthrough  |
+----------------------------------------------------------+
| 종료 후: cleanup=False default (C-010) — workdir 보존 +  |
|        stderr에 messages.jsonl/sessions/ 경로 안내        |
+----------------------------------------------------------+
```

ADR-9 fallback: `--max-turns < --convergence-streak + 1` + `K > 1` 가드 시 K=1 + stderr `K reduced to 1 (ADR-9, outline/02 §2.9)`. K=1 명시 입력은 fallback path skip (degenerate guard).

**fatal error 응답 형식** (protocol.md §9 정합): 어댑터가 비-auth 비정상 종료 시 `text="" + stderr_excerpt=stderr[:N]` 반환 → orchestrator 빈 응답 분기에서 `_error_msg` content에 `"ValueError: empty_response | stderr: <발췌>"` 합성 → messages.jsonl 단독으로 사용자 디버깅 가능 (P-STDERR_LOSS round 7 정합).

## 5. 의존 모듈 (dev-docs/systems/)

| 모듈 | 책임 |
|---|---|
| [orchestrator](../../dev-docs/systems/orchestrator.md) | `run_session`, `run_turn`, `build_prompt`, `_detect_converged`, 헬퍼 4종 (`_msg`/`_error_msg`/`_task_msg`/`_meta_msg`) |
| [agents](../../dev-docs/systems/agents.md) | `CodexRunner`, `ClaudeRunner` — cmd_list, 인증 실패 감지, raw stream 보존 |
| [jsonl-bus](../../dev-docs/systems/jsonl-bus.md) | append-only Bus + Meta 14 필드 + ts 형식 |
| [cwd-isolation](../../dev-docs/systems/cwd-isolation.md) | ADR-6 메커니즘 (workdir resolve + repo-root 차단 + subprocess cwd) |
| [env-check](../../dev-docs/systems/env-check.md) | `dialectic doctor` 동작 |

## 6. 변경 시 갱신 영향

| 코드 변경 | run-mode.md 영향 |
|---|---|
| `run_session` 종료 분기 추가 | §4 종료 조건 매트릭스 갱신 |
| `--mode` choices 확장 (Day 3+ plan/implement) | INDEX.md + 본 파일은 unaffected (run 한정) |
| `[CONVERGED]` 알고리즘 변경 (outline/02 §2.9) | §2 라이프사이클 R4·R5 + §4 종료 조건 갱신 |
| 어댑터 추가 (mock 등 Day 3+) | §1 `--driver`/`--reviewer` choices 갱신 + §3 메시지 흐름 예시 갱신 |
| `MODE_ROLES["run"]` 매핑 변경 | §2 R0 노드 갱신 |

## 7. 검증 명령

```bash
# 단위 (필수, 매 변경마다)
pytest -q tests/test_orchestrator_converge.py tests/test_cwd_isolation.py

# E2E (인증 환경 필요)
dialectic doctor   # 인증 OK 확인
dialectic run --task "Reply with single digit: 1+1=?" \
              --workdir /tmp/dialectic-demo \
              --driver codex --reviewer claude --max-turns 1
cat /tmp/dialectic-demo/logs/messages.jsonl   # 4 라인 (task→proposal→critique→meta)
```

DoD 만족 기준 — `messages.jsonl`에 4 라인 + 모든 `parent_id` 체인 + `convergence_streak=1` 박힘 + `kind=meta content="auto_end_converged"` 등장.
