# Summary · 010-observability

## 의도

dialectic 1턴 시연(workdir `/tmp/dialectic-XXXX`)에서 발견된 관찰 가능성 결함 3건 — `logs` 서브커맨드 부재 / 메뉴 진입 시 env_check 직렬 호출 지연 / `/tmp` 기반 workdir 접근성 — 을 통합 처리.

## 배경 / 동기

- plan 008 UI polish 완료 후 시연하면서 사용자가 (a) 진행 결과를 raw JSONL로만 확인 (`outline/03-ux.md §3.5` line 341-378 SSOT 미구현), (b) 메뉴 진입 시 점검 spinner 회전 시간이 길어 멈춘 듯한 인상, (c) 결과 workdir 경로(`/tmp/...`)가 WSL에서 cd 부담을 호소.
- 본 plan 진입 결정은 `upcoming-plans.md` 의존 그래프 `P008 → P010` (소프트). plan 009 활성과 무관한 병렬 가능 영역.
- ADR-6 cwd 격리 안전망은 유지 (workdir default 변경의 사이드 이펙트 검증 필수).

## Phase 흐름

```
A (logs) · B (env-parallel) · C (workdir)
   세 Phase 의존성 0 — execute-plan 병렬 분기 후보
```

## 핵심 의사결정

- workdir default = `~/.local/share/dialectic/runs/<timestamp>-<short-id>/` + `DIALECTIC_RUNS_DIR` env override (XDG_DATA_HOME 준수, ADR-6 안전, `/mnt/c`·repo 하위 기각) — `phase-c-workdir-default.md §1`
- env_check 4개 sub-check를 `concurrent.futures.ThreadPoolExecutor`로 병렬 (외부 의존성 0, 표준 라이브러리) — `phase-b-env-parallel.md §3`
- `dialectic logs` 1차 범위 = `--workdir / --session / --tail N / --follow / --kind <filter> / --full` (6 flag). path SSOT는 plan 011 Bug 2 fix 후 `<workdir>/<UTC-ts>/messages.jsonl` (`src/orchestrator.py:662-666`). 자동 탐색은 2-tier(`find_latest_session_dir`). `outline/03-ux.md §3.5`의 `--turn / --since / --summary / --run`은 후속 plan deferred — `phase-a-logs-subcmd.md §1`

## 핵심 위험

- workdir default 변경이 ADR-6 차단 로직(`src/orchestrator.py:612-625`, post-009)·`tests/test_cwd_isolation.py` 회귀와 충돌 가능 → Phase C 검증에 회귀 테스트 통과 명시
- env_check 병렬화 시 출력 순서 보존 — `executor.map` 채택으로 입력 순서 yield 보장 (`as_completed` 미사용, 별도 재정렬 불필요)
- Step 1.5 신호 2개(S2 독립 기능 3 + S4 영향 모듈 3) — **사용자 단일 plan 결정**: 3 phase 모두 1~2 작업 단위라 분리 시 `Phase 1개` 안티패턴
- README.md 동시 수정 충돌 — Phase A·C 모두 README 갱신 → "사용 예시"(A) / "결과 위치"(C) 섹션 분담
- **진행 순서 9→11→10**: 010은 plan 009(완료) + plan 011(선행) 산출 위에. cli.py line 인용 stale → execute 진입 시 grep 재확인. 011 Phase C 메뉴 단계 4 narrative와 default 경로 변경 cross-check

## DoD 요약

- [ ] (Phase A) `dialectic logs --tail 10` exit 0 + 마지막 세션 자동 탐색
- [ ] (Phase B) 메뉴 진입 spinner 시간 ≤ max(개별 timeout) (직렬 합 X)
- [ ] (Phase C) 새 세션 workdir = `~/.local/share/dialectic/runs/<...>` + `DIALECTIC_RUNS_DIR` override 동작
- [ ] sync-docs 누락 0 / review-code P0 = 0

→ 상세: [01-plan.md](01-plan.md), Phase별 [phase-a-logs-subcmd.md](phase-a-logs-subcmd.md) · [phase-b-env-parallel.md](phase-b-env-parallel.md) · [phase-c-workdir-default.md](phase-c-workdir-default.md)
