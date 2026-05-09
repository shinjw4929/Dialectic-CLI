# Summary · plan 015 trigger-race-fix

## 의도

Bug 1 (TriggerListener `__exit__` 후 `prompt_end_or_iterate` readline byte 절도 race, validation.md C-015) 정공법 fix. **에이전트 응답(codex/claude 실 호출 = API 비용) 생략한 reproduction harness 구축** + 사용자 반복 시연 cycle로 race 검증·fix·재검증.

## 배경 / 동기

- plan 011 e2e 시연 중 Ctrl+F → prompt 표시 → 'y'/한글 입력 → 빈 줄 처리 → INVALID_RETRY_LIMIT 도달 → fallback 결함 반복 발생
- 3차 hot fix 누적 (plan 011 commit `2c2bc2a`: TCSAFLUSH + fd-level os.read + listener join 강화) 후에도 일부 환경(WSL2 PTY) race 잔존 — 사용자 보고 "여전히 문제임"
- partial fix는 사용자 신뢰 잃음 + 매 시연마다 codex/claude 실 호출 ($+ 시간) 필요 → 빠른 fix iteration 불가능

## Phase 흐름

A · repro harness → B · 반복 cycle (가설 5회 한계) → C · 정공법 메커니즘 (① main thread polling + thread-safe Queue 단일 채택) → D · cleanup + cascade

## 핵심 의사결정

- **agent 응답 생략 harness**: dummy AgentRunner stub 또는 `DIALECTIC_HARNESS_MOCK_RESPONSE` 환경변수로 즉시 1줄 응답 → listener + prompt cycle만 격리 시연. 외부 의존성 0 정합 (stdlib `pty` 활용)
- **자동 재현 + 수동 재현 병렬**: pytest pty 기반 자동 (CI 회귀 보호) + standalone script 수동 (사용자 환경 의존성 검증)
- **정공법 메커니즘 ① 채택 (단일 결정)**: listener thread 유지 + stdin byte를 thread-safe `queue.Queue`에 push → main thread `poll_trigger_byte()` helper로 검사 (byte 절도 0). ② signal/③ fd close/④ TRIGGER_BYTE 변경은 fallback narrative만 (④는 사용자 환경 사전 검증 실패 — `src/ui.py:323-325` 주석)
- **반복 cycle은 Phase B 안에 narrative**: 1차 fix → 사용자 시연 결과 보고 → 추가 fix → 재시연 → race 0건 도달까지. plan execute-plan은 Phase B를 사용자 결과 의존 분기로 수행
- **plan 009 산출 (TriggerListener UX) 회귀 X**: Ctrl+F 키 매핑 + 매 턴 trigger 가능 동작 보존 (메커니즘만 변경)

## 핵심 위험

- harness가 race를 자동 재현 못 할 수 있음 (PTY 환경 차이) → Phase A 수동 시연 cycle 보강
- 정공법 메커니즘 변경이 plan 009 critical 모드 회귀 → Phase D 산출 후 plan 009 시연 매트릭스 재실행
- 사용자 환경 의존성 (WSL2 PTY) — 다른 환경에서 재현 불가 시 정공법 설계 어려움 → Phase A에서 사용자 환경 narrative 수집 (terminal emulator, locale, WSL 버전)
- 반복 cycle 무한 루프 — Phase B 5회 cycle 한계 + 도달 시 Phase C 정공법 강제 진입

## DoD 요약

- [ ] (Phase A) repro harness 자동(pytest pty) + 수동(standalone) 모두 race 재현 가능
- [ ] (Phase B) 가설 fix → 사용자 시연 5회 중 race 0회 도달 (race 재현률 0/5), 또는 5 cycle 도달 시 Phase C 정공법 진입
- [ ] (Phase C) ① main thread polling + thread-safe Queue 적용 + harness 재현 0/5 + 사용자 시연 0/5 + plan 009 critical 모드 회귀 0
- [ ] (Phase D) validation.md C-015 → R-NNN 환원 또는 status update + cascade docs (systems/ui.md TriggerListener narrative)
- [ ] sync-docs 누락 0 / `pytest -q` 회귀 0 + 신규 ≥4

→ 상세: [01-plan.md](01-plan.md), Phase별 [phase-a-repro-harness.md](phase-a-repro-harness.md) · [phase-b-iterative-cycle.md](phase-b-iterative-cycle.md) · [phase-c-canonical-fix.md](phase-c-canonical-fix.md) · [phase-d-cleanup-cascade.md](phase-d-cleanup-cascade.md)
