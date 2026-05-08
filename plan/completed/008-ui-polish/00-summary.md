# Summary · UI polish (호출 spinner + stdout 출력 + 메뉴 입력 보강)

## 의도

`dialectic` 단독 실행(default 진입) 시 driver/reviewer 호출 동안 사용자가 인지할 진행 표시·결과 출력·입력 안내가 모두 결여된 결함 3건을 단일 plan으로 묶어 wiring. outline/03-ux §3.2 narrative SSOT는 정의됐으나 코드 wiring 0인 갭 제거.

## 배경 / 동기

- plan 006-ui로 `src/ui.py:Spinner` + `_interactive_menu` minimum cut 진입까지 도달. 그러나 `dialectic` 단독 실행 시 (1) 호출 30~50초 동안 화면 정지 (Spinner 정의됐으나 호출자 0), (2) proposal/critique stdout 미출력 (workdir 안내만), (3) `task (한 줄):` prompt가 example/도움말/진행 확인 없이 단일 — 기획자 페르소나(outline/03-ux §3.1 line 19, Q14)가 무엇을 입력해야 할지 추측
- outline/03-ux §3.2 line 190-225 narrative + §3.5 line 362 ANSI 색상이 모두 SSOT로 정의되어 있고, `Spinner`는 이미 plan 006으로 구현됨 — wiring만 남음

## Phase 흐름

```
A · 호출 spinner → B · 호출 결과 stdout 출력
                                              C · 메뉴 입력 보강 (독립)
```

A·B는 `src/orchestrator.py:run_turn` 같은 함수 수정이라 직렬. C는 `src/cli.py:_interactive_menu` 단독, A·B 무관 — 병렬 가능.

## 핵심 의사결정

- **Spinner 메시지 형식 = outline §3.2:190 SSOT 1:1** — `[{role_label}: {vendor}] running...` 동적 생성 (vendor=Codex CLI/Claude Code, role_label=구현자/기획 검토자 등)
- **호출 종료 1줄 = outline §3.2:193 SSOT 1:1** — `[{role_label}: {vendor}] ✓ {latency}s · {output_tokens} out / {input_tokens} in` (cost는 None일 수 있어 옵셔널)
- **`src/ui.py:print_message` 신설** — `kind`별 ANSI 색상 (proposal=cyan, critique=yellow) + 구분선·헤더·본문 1:1 출력. helper 단일 진입점으로 orchestrator의 print 분기 차단
- **메뉴 진행 확인 단계** — task 입력 후 `driver=codex, reviewer=claude, 1턴 — 진행? [Y/n]:` prompt. `n` 입력 시 return 0 안전 종료. example + `?` 도움말 키 추가
- **deferred 5건 본 plan 범위 외** — `dialectic logs` (plan 009), env_check 병렬·`claude doctor` timeout (plan 009), workdir default 변경 (plan 009 / C-010), 메뉴 단계 2·4 (plan 010), mock 어댑터 (plan 007)

## 핵심 위험

- **spinner 출력 ↔ stdout 출력 race** — Spinner는 stderr(`\r` carriage return), print_message는 stdout. 채널 분리로 race 없음. test에서 capsys로 양쪽 분리 단언
- **isatty=False (CI/파이프) 회귀** — Spinner는 plan 006에서 이미 isatty 가드 보유. print_message는 항상 출력 (CI에서도 결과 보여야 함). 색상 ANSI는 isatty=False 시 비워서 escape 노이즈 차단
- **R-001 P-ENCODING** — 본 plan은 stdin/stdout만, file I/O 0이라 vacuously OK. 그러나 신규 테스트 파일에 read_text/write_text 추가 시 `encoding="utf-8"` 강제
- **frozen Meta 회귀** — orchestrator의 Meta 갱신은 `dataclasses.replace(...)`로 새 Meta 생성. 본 plan은 메시지 추가 X (출력만), Meta 직접 변경 0

## DoD 요약

- [ ] (Phase A) `src/ui.py`에 `VENDOR_LABEL`/`ROLE_LABEL_KO` paste + `src/orchestrator.py:run_turn` driver/reviewer 호출 `Spinner(message)` 컨텍스트 wrapping. 단위 테스트 ≥2 케이스 pass
- [ ] (Phase B) `src/ui.py`에 ANSI 상수 + `print_message` 신설 + `run_turn` proposal/critique append 직후 stdout 출력. 단위 테스트 ≥3 케이스 pass
- [ ] (Phase C) `src/cli.py:_interactive_menu` example + 진행 확인 + 도움말 키 보강. 단위 테스트 ≥3 케이스 pass
- [ ] 전체 회귀 0 — `pytest -q` 43 → ≥48
- [ ] sync-docs cascade — `dev-docs/systems/orchestrator.md`, `runtime-docs/systems/run-mode.md`, `README.md`, `Documentation-Checklist.md §1.1` (필요 시) 갱신
- [ ] review-code P0 = 0 (R-001 encoding 포함)

→ 상세: [01-plan.md](01-plan.md), Phase별 [phase-a-spinner.md](phase-a-spinner.md) · [phase-b-stdout.md](phase-b-stdout.md) · [phase-c-menu-polish.md](phase-c-menu-polish.md)
