# Plan · 011-menu-expansion

## 0. 메타

- 작업 ID: `011-menu-expansion`
- 의도: `dialectic` 단독 실행 default 메뉴를 outline §3.2 narrative 5단계로 확장. outline 단계 번호 기준 단계 2(mode) + 단계 4의 매핑·workdir 슬롯 추가 (단계 1·3·5는 plan 008까지 wiring 완료, `--interactive` mode dial은 plan 009에서 wiring 완료)
- 관련 ADR / Q번호: Q14 (메뉴 + CLI 두 진입로, `outline/03-ux.md:19`), ADR-6 (cwd 격리 — workdir repo-root 차단은 orchestrator `:616-625` SSOT 위임)
- 예상 영향 범위: `src/cli.py` (argparse 1행 + `_interactive_menu_body` 흐름 정렬 + 신규 input helper 3개 + `_input_confirm` 시그니처 2단계 확장 + docstring 갱신), 신규 단위 테스트 ≥14 (`tests/test_interactive_menu_expansion.py`)
- LOC 추정: ~85 LOC (코드) + ~40 LOC (테스트)
- 백로그 SSOT: [`docs/dev-docs/Plans/upcoming-plans.md`](../../docs/dev-docs/Plans/upcoming-plans.md) `:281-333`

## 1. AS-IS

> 본 §1 line 번호는 plan 009 완료 (uncommitted 작업 트리) 기준. plan 009 commit 전후 line shift 가능 — execute-plan 진입 시 grep으로 재확인 권장.

### 1.1 메뉴 본문 — `src/cli.py:_interactive_menu_body` `:234-284`

- 단계 1(환경 점검) `:238-241` + 단계 5(execute) `:264-284`만 wiring
- task 입력 `:255` + max-turns 입력 `:256` + 진행 확인 `:257` 호출
- `:264-269` Namespace 하드코딩 (plan 009 산출 `interactive="critical"` 적용):
  ```python
  args = argparse.Namespace(
      cmd="run", task=task, workdir=None,
      driver="codex", reviewer="claude",
      max_turns=max_turns, mode="run",
      convergence_streak=2, interactive="critical",
  )
  ```
- mode/매핑/workdir 사용자 선택 0 — 모두 default 고정 (`interactive`는 plan 009가 wiring 완료, 본 plan 무관)

### 1.2 CLI argparse — `src/cli.py:50-90`

- `:62-63` `--driver` / `--reviewer` choices=`["codex", "claude"]`
- `:65-68` `--mode` choices=`["run"]` + 주석 "Day 2는 'run' 모드만 노출"
- `:74-80` `--interactive` choices=`["end-only", "critical", "full"]` (plan 009 산출, 본 plan 무관)
- `:57-61` `--workdir` default=None → orchestrator가 `tempfile.mkdtemp(prefix='dialectic-')` 자동 생성

### 1.3 orchestrator 모드 지원 — `src/orchestrator.py:45-49`

```python
MODE_ROLES = {
    "run":       {"driver": "implementer", "reviewer": "spec-reviewer"},
    "plan":      {"driver": "planner",     "reviewer": "plan-reviewer"},
    "implement": {"driver": "implementer", "reviewer": "spec-reviewer"},
}
```

- run/plan/implement 3 모드 ROLE 매핑 이미 정의 (`docs/runtime-docs/roles/{implementer,spec-reviewer,planner,plan-reviewer}.md` 4 role.md 존재)
- compare 모드는 `MODE_ROLES`에 없음 — 별도 subcommand (병렬, 비대화형) 필요
- implement 모드는 `--task` 대신 `--spec` 입력 가정 (outline `:50` `dialectic implement --spec ...`)

### 1.4 cwd 격리 검증 — `tests/test_cwd_isolation.py` + `tests/test_cwd_isolation_integration.py`

ADR-6 — repo-root workdir 차단 회귀 테스트 2종 존재. orchestrator `:616-625`의 SystemExit 차단 메커니즘이 SSOT. workdir 직접 입력 분기 추가 시 본 테스트 2종 통과 유지 필수 — 본 plan 메뉴는 입력만 수집하고 차단 검증은 orchestrator 위임 (SSOT 보존).

## 2. TO-BE

### 2.1 `src/cli.py:_interactive_menu_body` 5단계 풀 노출 (outline `:104-179` 정확 추종)

```
단계 1 (기존)  환경 점검 spinner
단계 2 (NEW)   mode 선택       1) run  2) plan  3) implement  4) compare  (default Enter = run)
단계 3 (기존)  task 입력       (기존 _input_task 그대로 — outline `:138-149`)
단계 4 (NEW)   매핑 선택       1) codex→claude  2) claude→codex  (default = 1, outline `:166-170` 2종 추종)
                workdir 선택   1) 자동 생성(orchestrator default)  2) 직접 입력  (default = 1)
                max-turns 입력 (기존 _input_max_turns 재사용)
단계 5 (기존)  진행 확인 + execute (Namespace 동적 구성)
```

- implement 선택 시: "implement 모드는 spec.md 경로 입력(outline `:50` `--spec <path>`)이 본 plan 외 — 별도 plan에서 `dialectic implement` subparser 추가 예정. 현재는 `dialectic run --mode implement --task <text>`로 임시 호출 가능하나 outline narrative와 어긋남." 안내 + back to mode 선택
- compare 선택 시: "compare 모드는 별도 subparser(`dialectic compare --configs ...`, outline `:53-57`)가 본 plan 외 — 별도 plan에서 wiring 예정." 안내 + back to mode 선택
- workdir 직접 입력 분기는 입력 문자열만 수집 — repo-root 차단은 orchestrator `:616-625` SystemExit이 SSOT (메뉴 client-side 검증 X, 단일 진실원 보존)
- argparse `--mode` choices는 `["run", "plan", "implement"]` 3종 (compare는 별도 subcommand path). 메뉴 4종 표시 vs argparse 3종 비대칭은 의도된 결정 — 메뉴는 사용자 안내용 표면 (4 모드 narrative 노출), argparse는 CLI 직접 호출 path

### 2.2 argparse 확장

- `:66` `--mode choices=["run", "plan", "implement"]` (compare는 별도 subparser 필요 — 본 plan 외)
- `:62-63` driver/reviewer choices 변동 없음 (이미 codex/claude 지원)
- `--interactive` 변동 없음 (plan 009 책임)

### 2.3 단계별 input helper 신규

| 함수 | 책임 | LOC |
|---|---|---|
| `_input_mode()` → str | 모드 메뉴 표시·선택, implement/compare 안내 + back | ~25 |
| `_input_mapping()` → tuple[str, str] | (driver, reviewer) 2 조합 선택 (outline `:166-170`) | ~15 |
| `_input_workdir()` → str \| None | None=자동(orchestrator default 위임) / str=입력 그대로 (검증 위임) | ~20 |

기존 `_input_task` / `_input_max_turns` / `_input_confirm` 유지 — `_input_confirm`은 mode·매핑·workdir 정보 echo 추가 (Phase B에서 1차, Phase C에서 2차 확장).

### 2.4 단위 테스트 신규 — `tests/test_interactive_menu_expansion.py`

- mode 4 분기 (run/plan/implement/compare) 입력 시 helper 반환값 + back 동작 + default Enter + invalid retry
- 매핑 2 조합 (codex→claude / claude→codex) + default Enter + invalid retry
- workdir 자동 / 직접 입력 (단순 문자열 통과) / EOF
- max-turns 회귀 (기존 `_input_max_turns` 그대로)
- 통합: `_interactive_menu_body` mock으로 5단계 통과 시나리오

## 3. Phase 인덱스

### 3.1 의존성 그래프

```mermaid
flowchart LR
    A["Phase A · 단계 2 mode 선택"]
    B["Phase B · 단계 4 매핑 선택"]
    C["Phase C · 단계 4 workdir 선택"]
    A --> B
    B --> C
```

직렬 — 세 Phase 모두 `_interactive_menu_body` 같은 함수에 작업 단위 삽입. 병렬 실행 시 함수 본문 충돌 → 직렬 강제.

### 3.2 Phase 파일 경로

| Phase | 경로 | 의존 | 병렬 그룹 |
|---|---|---|---|
| A · 단계 2 mode 선택 | [phase-a-mode-select.md](phase-a-mode-select.md) | (없음) | — |
| B · 단계 4 매핑 선택 (단계 4 묶음의 매핑 슬롯) | [phase-b-mapping-select.md](phase-b-mapping-select.md) | A | — |
| C · 단계 4 workdir 선택 (단계 4 묶음의 workdir 슬롯, max-turns 호출 정렬) | [phase-c-workdir-select.md](phase-c-workdir-select.md) | B | — |

## 4. 비기능 요구

- 외부 의존성 추가 0 (표준 라이브러리만 — 기존 `_safe_input` / `_readline_input` 재사용)
- 모든 input helper EOF/Ctrl-C 안전 (`_safe_input` 통과 — `_MenuExit` propagate)
- isatty 가드 영향 없음 (Spinner는 단계 1만 사용)
- 기존 회귀 0 — `tests/test_cwd_isolation.py` (ADR-6) + plan 008 산출 회귀 모두 유지

## 5. 위험 (Phase 횡단)

1. **plan 010 미진행 — workdir default 변경 미반영**
   - 본 plan Phase C는 workdir "자동 생성" 분기를 `_interactive_menu_body` 단계 4에 노출하지만 실제 default 경로 결정은 orchestrator (`tempfile.mkdtemp`) 책임
   - plan 010 Phase C가 default를 `~/.local/share/dialectic/runs/<...>`로 바꿔도 본 plan 메뉴 코드 무변경 (단계 4 안내 문구만 갱신 필요할 수 있음)
   - 차단: Phase C 안내 문구는 "자동 생성된 임시 디렉토리" 추상 표현 사용 — 경로 형식 노출 X

2. **plan 009 완료 산출 보존 — Namespace `interactive="critical"` 라인**
   - plan 009 Phase A가 `:268` `interactive="critical"` 적용 완료 (uncommitted 작업 트리)
   - 본 plan은 `interactive` 필드 손대지 X — Namespace `# spec` 라벨 유지, execute-plan subagent가 dynamic field(mode/driver/reviewer/workdir)만 동적화하고 `interactive` 라인은 plan 009 산출 그대로 보존
   - plan 009 commit 전 plan 011 진입 시: working tree에서 plan 009 변경분 보존 + plan 011 변경분 add — git stage 분리

3. **mode=plan 실 호출 검증 부재**
   - orchestrator MODE_ROLES에 plan 정의 있지만 dialectic 1턴 실 호출 검증 0 (`docs/runtime-docs/roles/{planner,plan-reviewer}.md` 본문은 존재)
   - 본 plan Phase A DoD에 mode=plan 실 호출 1회 시연 포함 — 실패 시 별도 plan으로 분리

4. **compare subparser 부재**
   - mode 메뉴에 compare 노출하지만 `dialectic compare` subparser 자체가 없음 (`src/cli.py:50-87`에 compare 행 0)
   - 본 plan은 메뉴 안내 + back으로 처리 — 진짜 compare wiring은 별도 plan 책임 (upcoming-plans.md 외)
   - 차단: 안내 문구 명확화 — "compare는 별도 plan 진입 후 사용 가능"

## 6. 완료 기준 (Definition of Done)

- [ ] (Phase A) `src/cli.py:66` `--mode` choices=`["run", "plan", "implement"]` 확장 (compare는 별도 subparser, 본 plan 외)
- [ ] (Phase A) `_input_mode` helper 추가 + 6 단위 테스트 (run/plan/implement-back/compare-back/default Enter/invalid retry)
- [ ] (Phase A) `dialectic` 단독 실행 → mode=plan 선택 → orchestrator `run_session(mode="plan")` 정상 진입 + JSONL `messages.jsonl`에 planner ROLE 응답 메시지 1개 이상 보존 (spec.md 자동 저장은 orchestrator/role.md 책임 — 본 plan 외)
- [ ] (Phase B) `_input_mapping` helper 추가 + 4 단위 테스트 (codex→claude / claude→codex / default Enter / invalid retry)
- [ ] (Phase C) `_input_workdir` helper 추가 + 4 단위 테스트 (자동 default / 자동 명시 / 직접 입력 통과 / EOF)
- [ ] (Phase C) `tests/test_cwd_isolation.py` + `tests/test_cwd_isolation_integration.py` 회귀 통과 유지
- [ ] (Phase C) `dialectic` 단독 실행 → workdir 직접 입력 → 1턴 실 호출 시연 (repo-root 입력 시 orchestrator SystemExit으로 차단되는 시연 포함)
- [ ] (전 Phase) `_interactive_menu_body` 5단계 모두 EOF/Ctrl-C 안전 종료 (return 0)
- [ ] (전 Phase) Namespace 동적 구성 — mode/driver/reviewer/workdir/max_turns 모두 사용자 입력 반영
- [ ] sync-docs 누락 0 (`docs/dev-docs/Documentation-Checklist.md` §1.1 `src/cli.py` 행 매핑)
- [ ] review-code P0 = 0
- [ ] `pytest -q` 회귀 0 + 신규 케이스 ≥14

## 7. 참조 .md

- [`outline/03-ux.md`](../../outline/03-ux.md) §3.2 `:104-179` — 메뉴 단계 narrative SSOT
- [`docs/dev-docs/Plans/upcoming-plans.md`](../../docs/dev-docs/Plans/upcoming-plans.md) `:281-333` — plan 011 backlog SSOT
- [`docs/dev-docs/architecture.md`](../../docs/dev-docs/architecture.md) ADR-6 — cwd 격리
- [`docs/dev-docs/systems/orchestrator.md`](../../docs/dev-docs/systems/orchestrator.md) §cli — 갱신 대상
- [`docs/runtime-docs/systems/INDEX.md`](../../docs/runtime-docs/systems/INDEX.md) — 4 모드 매트릭스 (mode 확장 영향)
- [`docs/dev-docs/Documentation-Checklist.md`](../../docs/dev-docs/Documentation-Checklist.md) §1.1 — `src/cli.py` 변경 매핑
- [`docs/dev-docs/code-conventions.md`](../../docs/dev-docs/code-conventions.md) §6 — CLI 인자 처리 규약
- [`tests/test_cwd_isolation.py`](../../tests/test_cwd_isolation.py) — ADR-6 회귀
- [`src/cli.py:234-284`](../../src/cli.py) — `_interactive_menu_body` AS-IS (plan 009 적용 후)
- [`src/orchestrator.py:45-49`](../../src/orchestrator.py) — MODE_ROLES 정의
