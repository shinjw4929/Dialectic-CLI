# Summary · 인터랙티브 UI

## 의도

`src/ui.py`(6지선다 + directive + spinner) + `src/cli.py` 메뉴 진입(default 동작) wiring으로 outline/03-ux §3.2/§3.3 SSOT 코드 GAP 제거. 기획자 페르소나(outline/03-ux §3.1 line 19, Q14) 1차 사용자 — `dialectic` 단독 실행이 default 진입로, CLI 인자는 자동화/CI용. mock 어댑터는 본 plan 범위 외 — 동영상 시연 결과 보고 후속 plan 007 진행/폐기 결정 (deferred).

## 배경 / 동기

- plan 005까지: 비대화형 1턴(`--interactive end-only`)만 동작. 6지선다·directive·메뉴 모두 코드 0
- outline/03-ux §3.3 (line 254-269) 6지선다 + Enter default + outline §3.2 (line 104-252) 메뉴 단계 SSOT는 정의되어 있으나 wiring 부재
- 본 plan은 UI 단일 의도 minimum cut — mock 어댑터는 동영상 시연 후 평가자 직접 실행 시도 시나리오 정보 모아 별도 결정

## Phase 흐름

```
A · UI 모듈 → B · CLI 메뉴 진입 (default) + sync-docs
```

A는 src/ui.py 자급자족 (외부 호출자 0). B가 cli.py 메뉴 진입 + UI 함수 호출 wiring.

## 핵심 의사결정

- **UI 키셋 = outline/03-ux §3.3 SSOT (`a/r/m/i/e/s`)** — accept driver / accept reviewer / merge / iterate / end / skip review 1:1 매핑
- **Enter = iterate + empty directive** (outline §3.3 default UX)
- **EOF/Ctrl-C 안전망** — `prompt_decision`이 `EOFError`/`KeyboardInterrupt` catch → `("e", None)` 반환. 비대화형 환경(파이프·CI) raise 누수 차단
- **default 메뉴 minimum cut** — Day 2는 모드 'run' 고정 + task 한 줄 입력 후 즉시 실행. outline §3.2 단계 1(환경 점검) / 2(모드 선택) / 4(매핑·workdir)는 후속 plan 분리
- **mock 어댑터 deferred** — `src/agents/mock.py`, `--mock`/`--record`/`--mock-decisions` 인자, 녹음 자산 모두 본 plan 범위 외. 동영상 시연 결과 + 평가자 직접 실행 시도 시나리오 정보 모은 후 plan 007 진행/폐기 결정

## 핵심 위험

- **R-001 P-ENCODING** — 신규 read_text/write_text/open() 모두 `encoding="utf-8"` 명시 (validation.md §2). 위반 P0
- **stdin EOF / Ctrl-C** — UI가 비대화형 환경 raise 누수 차단. test 케이스로 검증
- **메뉴 진입 시 stdin 닫힘** — `_interactive_menu`도 EOF 시 안전 종료 exit 0
- **spinner ANSI 호환** — Windows cmd.exe·일부 CI 터미널에서 `⠋⠙` 깨질 가능. `not sys.stderr.isatty()` 가드로 silent. `--no-spinner` flag는 본 plan 범위 외 (후속 옵션)

## DoD 요약

- [ ] (Phase A) `src/ui.py` + `tests/test_ui.py` (≥4 케이스: 6 키 매핑 / Enter default / EOF / invalid retry) pass
- [ ] (Phase B) `dialectic` (default 진입) → 메뉴 → task 입력 → run 호출 + `tests/test_cli_menu.py` EOF 안전 종료 검증 pass
- [ ] sync-docs cascade — `dev-docs/systems/orchestrator.md §cli` 메뉴 진입 (default) narrative + `runtime-docs/systems/run-mode.md §1` 진입로 narrative
- [ ] 전체 회귀 0 (8 → ≥10 파일 모두 pass)
- [ ] review-code P0 = 0 (R-001 encoding 포함)

→ 상세: [01-plan.md](01-plan.md), Phase별 [phase-a-ui.md](phase-a-ui.md) · [phase-b-cli-menu.md](phase-b-cli-menu.md)
