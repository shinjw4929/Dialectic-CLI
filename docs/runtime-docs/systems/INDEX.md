# Runtime Systems Index

Dialectic-CLI 런타임 모드별 진리문서 (B 층 — `outline/01-harness-layers.md` §1.2).

각 모드는 본 디렉토리 안에 단독 파일로 SSOT 보관. `protocol.md`(스키마·라이프사이클 표준)는 횡단 사양, 본 파일들은 모드별 동작.

## 4 모드 매트릭스

| 모드 | 파일 | driver / reviewer (역할) | 종료 조건 | 산출물 | 상태 |
|---|---|---|---|---|---|
| **run** | [run-mode.md](run-mode.md) | implementer / spec-reviewer | `[CONVERGED]` streak K (default 2) 또는 `--max-turns` 도달 | `<workdir>/<file>` 코드 + `logs/messages.jsonl` | **Day 2 정식 검증 ✓** |
| **plan** | (Day 3+ 추가) | planner / plan-reviewer | run과 동일 | `<workdir>/specs/<slug>.md` (top-level — session 격리 X. 충돌 시 `<slug>-<session_ts>.md` fallback) | spec.md auto-save **plan 013 ✓** (`_resolve_spec_path` + `run_turn` spec_path wiring). 메뉴 wiring **plan 011 ✓** |
| **implement** | (Day 3+ 추가) | implementer / spec-reviewer | run과 동일 | `<workdir>/<file>` 코드 (spec.md 입력) | 미구현 — `--spec @<path>` 입력 메커니즘 + `build_prompt` implement 분기 부재 |
| **compare** | (Day 4+ 추가) | (run/plan/implement 중 선택) | 병렬 실행 후 `compare.md` 생성 | `logs/runs/<ts>/compare.md` | 메타 모드 — `MODE_ROLES["compare"]` 키 부재가 의도된 설계 (별도 dispatcher) |

## 변경 시 갱신 매핑

코드 변경이 모드 동작에 영향을 미치면 본 디렉토리의 해당 모드 파일 갱신 필수:

| 코드 변경 | 갱신 대상 |
|---|---|
| `MODE_ROLES` dict | INDEX.md + 영향 받는 모드 파일 |
| `src/orchestrator.py run_session/run_turn` | `run-mode.md` (Day 2) + 향후 다른 모드 파일 |
| `src/cli.py` `--mode`/`--convergence-streak`/`--interactive` argparse | INDEX.md + 영향 받는 모드 파일 |
| `src/agents/*.py` 어댑터 cmd_list 또는 인터페이스 | (모듈 진리는 `dev-docs/systems/agents.md` — 본 INDEX는 모드 단위 unaffected) |
| `outline/02-communication.md` §2.9 [CONVERGED] 메커니즘 | `run-mode.md` + 향후 plan/implement-mode |

`docs/dev-docs/Documentation-Checklist.md` §1에 본 매핑 등재 — 변경 시 sync-docs가 catch.

## 관련 문서

- `protocol.md` (메시지 스키마, 턴 라이프사이클, 4섹션 prompt) — 모드 횡단 사양
- `roles/{implementer,spec-reviewer,planner,plan-reviewer}.md` — 4 ROLE 본문 (각 모드의 `build_prompt` §1 ROLE 섹션 입력)
- `outline/02-communication.md` (통신 모델 + [CONVERGED] 메커니즘 결정)
- `outline/04-requirements-and-modes.md` (4 모드 정의 + 종료 조건)
