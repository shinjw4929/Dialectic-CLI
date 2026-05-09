# Summary · plan 011 menu-expansion

## 의도

`dialectic` 단독 실행 시 진입하는 default 메뉴(`src/cli.py:_interactive_menu_body` `:234-284`, plan 009 적용 후 line 번호)를 outline §3.2 narrative 5단계로 확장 — 현재 단계 1(환경 점검) + task 입력 + max-turns + 단계 5(execute)만 wiring된 상태에서 단계 2(모드 선택) + 단계 4 매핑·workdir 슬롯 추가. outline 단계 번호 기준 단계 1·2·3·4·5 모두 노출.

## 배경 / 동기

- plan 008까지 메뉴는 task 입력 + execute만 노출. mode/매핑/workdir은 default 고정 (`run` / `codex→claude` / `tempfile.mkdtemp`)
- 기획자 페르소나(Q14, `outline/03-ux.md:19`)의 메뉴 진입 narrative와 현재 구현 차이 ↑ — 평가 시연 폭 좁음
- orchestrator MODE_ROLES (`src/orchestrator.py:45-49`)는 run/plan/implement 3종 이미 지원 — CLI argparse choices만 `["run"]`으로 좁힘 (`src/cli.py:66`). 메뉴 수면화 비용 ↓

## Phase 흐름

A → B → C 직렬 (모두 `_interactive_menu_body` 같은 함수 수정 → conflict 회피)

## 핵심 의사결정

- Phase D(model 선택) 제외 — plan 012 미진행 의존 (upcoming-plans.md `:309` 명시)
- 단계 4 workdir default는 plan 010 미진행 상태 그대로 `tempfile.mkdtemp` 유지 — plan 010 진입 시 default만 바뀌고 메뉴 코드 무변경 (Phase C §6 위험 1)
- mode 메뉴 4종(run/plan/implement/compare) 노출 + 메뉴에서는 run/plan만 진행 가능, implement/compare는 후속 plan wiring 예정 안내 + back (본문 §2.1·phase-a §3.1 outline `:50`/`:53-57` 인용)
- 매핑 메뉴 2종(`codex→claude` / `claude→codex`) — outline §3.2 `:166-170` SSOT 정확 추종. same-vendor 4종 확장은 별도 plan(디버깅·single-vendor regression 비교 용도)
- workdir 직접 입력 분기는 client-side ADR-6 검증 X — orchestrator `:616-625` SSOT 위임 (사용자가 입력 → orchestrator 진입 시 SystemExit으로 차단). 메뉴는 안내만 (단일 진실원 보존)
- `--interactive`는 plan 009 책임 (메뉴 default = `critical`, plan 009 Phase A 산출) — 본 plan은 Namespace `interactive` 라인 손대지 X (plan 009 산출 `"critical"` 보존)

## 핵심 위험

- plan 009/010 동시 진행 가능성 — `_interactive_menu_body` 본문 수정 충돌 위험. 본 plan 진입 시 plan 009 phase 진행 상황 사전 확인 (§5 위험 2)
- mode=plan 메뉴 진입 시 spec.md 산출 정상 동작 검증 필요 — orchestrator는 지원하지만 실 호출 검증 0 (§5 위험 3)
- compare 모드는 본 plan에서 메뉴 fallback만 — 진짜 wiring은 별도 plan (compare subparser 부재)

## DoD 요약

- [ ] (Phase A·B·C) `dialectic` 단독 실행 시 5단계 모두 화면 표시 + 각 단계 EOF/Ctrl-C 안전 종료
- [ ] (Phase A) mode=run/plan 선택 시 run_session 정상 진입 (Namespace `mode` 동적). implement/compare 선택 시 안내 + back
- [ ] (Phase B) 매핑 2종(codex→claude / claude→codex) 선택 가능, default Enter = `codex→claude`
- [ ] (Phase C) workdir 2분기(자동 생성 / 직접 입력) 선택 가능. 직접 입력 분기는 orchestrator SSOT 위임 (repo-root 차단은 orchestrator `:616-625`에서 SystemExit)
- [ ] sync-docs 누락 0 / review-code P0 = 0 / 단위 테스트 ≥14

→ 상세: [01-plan.md](01-plan.md), Phase별 [phase-a-mode-select.md](phase-a-mode-select.md) · [phase-b-mapping-select.md](phase-b-mapping-select.md) · [phase-c-workdir-select.md](phase-c-workdir-select.md)
