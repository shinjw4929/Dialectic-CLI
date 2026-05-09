# Phase A · 단계 2 mode 선택 — 011-menu-expansion

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: —
- 예상 LOC: ~30 (코드) + ~15 (테스트)

## 1. 목표

`dialectic` 단독 실행 메뉴 단계 2(모드 선택)를 outline `:124-136` narrative대로 노출 — run/plan/implement/compare 4종 표시, run/plan만 진행 가능, implement/compare는 안내 + back. argparse `--mode` choices 확장 동시 적용.

## 2. 입력

- [`src/cli.py:50-90`](../../src/cli.py) — argparse AS-IS (특히 `:65-68` `--mode choices=["run"]`. `:74-80` `--interactive`은 plan 009 산출 — 본 Phase 무관)
- [`src/cli.py:234-284`](../../src/cli.py) — `_interactive_menu_body` AS-IS (단계 2 wiring 자리 = `:241` `_print_env_summary(res)` 직후, `:246` task 안내 print 직전)
- [`src/orchestrator.py:45-49`](../../src/orchestrator.py) — MODE_ROLES 정의 (run/plan/implement 지원, compare 없음)
- [`outline/03-ux.md:124-136`](../../outline/03-ux.md) — 단계 2 narrative SSOT
- 기존 helper 패턴 참고: `_input_task` `:162-180` / `_input_max_turns` `:183-198` (retry 루프 + `_safe_input` wrap + `_MenuExit` propagate)

## 3. 출력

### 3.1 `src/cli.py` 변경

`--mode` choices 확장 (`:65-68`):

```python
# paste
p_run.add_argument(
    "--mode", choices=["run", "plan", "implement"],
    default="run",
    help="run/plan/implement 3 모드. compare는 별도 subcommand 필요 (본 plan 외).",
)
```

argparse 3종(run/plan/implement) vs 메뉴 4종(+compare) 비대칭 결정: argparse는 `dialectic run --mode <X>` CLI 직접 호출 path. compare는 `dialectic compare --configs ...` 별도 subparser path (본 plan 외 — compare subparser 부재). 메뉴 4종은 사용자 안내용 표면 (4 모드 narrative 노출), compare 선택 시 안내 + back으로 사용자에게 별도 subparser 안내. 비대칭은 의도된 결정.

신규 helper `_input_mode` (cli.py 신규 함수, `_input_max_turns` 위치 부근에 추가):

```python
# spec
def _input_mode() -> str:
    """단계 2 mode 선택. 4 옵션 표시 (1=run / 2=plan / 3=implement / 4=compare).

    - default Enter = "run" (현재 동작 보존)
    - implement → "implement 모드는 spec.md 경로 입력 wiring이 본 plan 외 — 별도 plan에서
      `dialectic implement` subparser 추가 예정 (outline `:50`)." 안내 + retry
    - compare → "compare 모드는 별도 subparser(`dialectic compare --configs ...`,
      outline `:53-57`)가 본 plan 외 — 별도 plan에서 wiring 예정." 안내 + retry
    - 그 외 입력 → 재입력
    """
```

`_interactive_menu_body` 단계 2 wiring (현재 `:243-244` 안내 출력 직전 또는 직후):

```python
# spec
mode = _input_mode()
# (이후 task/max-turns/confirm은 기존 흐름 유지)
```

Namespace 구성 (`:264-269`) `mode="run"` → `mode=mode`로 변경 (interactive 라인은 plan 009 산출 `"critical"` 보존):

```python
# spec
args = argparse.Namespace(
    cmd="run", task=task, workdir=None,
    driver="codex", reviewer="claude",
    max_turns=max_turns, mode=mode,
    convergence_streak=2, interactive="critical",  # plan 009 산출 보존, 본 Phase 무관
)
```

### 3.2 단위 테스트 추가 — `tests/test_interactive_menu_expansion.py` (신규)

```python
# spec
def test_input_mode_run():
    """1 입력 → 'run' 반환"""

def test_input_mode_plan():
    """2 입력 → 'plan' 반환"""

def test_input_mode_implement_back():
    """3 입력 → 안내 출력 + 재입력 (back to mode 메뉴)"""

def test_input_mode_compare_back():
    """4 입력 → 안내 출력 + 재입력"""

def test_input_mode_default_enter():
    """빈 입력 (Enter) → 'run' 반환"""

def test_input_mode_invalid_retry():
    """'9' 같은 invalid → 재입력 (retry)"""
```

mock 패턴: `monkeypatch`로 `_safe_input` 또는 `_readline_input` 교체 (기존 plan 008 산출 테스트 패턴 따름).

## 4. 작업 단위

- [ ] `src/cli.py:66` `--mode choices=["run"]` → `["run", "plan", "implement"]` 변경, help 문구 갱신
- [ ] `src/cli.py`에 `_input_mode` 함수 신규 추가 (위치: `_input_max_turns` 직전 또는 직후)
- [ ] `_input_mode` 본문: `_safe_input` retry 루프 + 1/2/3/4/Enter/invalid 분기
- [ ] implement/compare 안내 문구는 단일 print 라인 + 재입력 (loop continue)
- [ ] `_interactive_menu_body` 단계 2 자리에 `mode = _input_mode()` 호출 삽입 (환경 점검 직후, task 입력 직전 자연스러운 위치)
- [ ] `:261` Namespace `mode="run"` → `mode=mode` 변경
- [ ] `tests/test_interactive_menu_expansion.py` 신규 작성 + 6 테스트 케이스

## 5. 검증

- `python -c "from src.cli import _input_mode; print(_input_mode.__doc__)"` 성공
- `pytest -q tests/test_interactive_menu_expansion.py` 신규 6 케이스 pass
- `pytest -q` 전체 회귀 0 (특히 `tests/test_cwd_isolation.py` + `tests/test_cwd_isolation_integration.py` + plan 008 산출 회귀)
- `dialectic run --help` 출력의 `--mode` choices에 `plan, implement` 포함 확인 (`--mode`는 `run` subparser 옵션)
- 실 호출 시연: `dialectic` 실행 → `2` 입력 (plan 모드) → task 입력 → orchestrator `run_session(mode="plan")` 정상 진입 → 1턴 실 호출 → JSONL `messages.jsonl`에 `from="driver"` + `meta.role` planner 응답 1건 이상 보존 확인 (spec.md 자동 저장은 본 Phase 외)

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **mode=plan 실 호출 검증 — orchestrator 진입까지만 책임**
   - orchestrator `:469 roles = MODE_ROLES[mode]`에서 plan ROLE은 `planner`/`plan-reviewer`로 매핑됨
   - 본 Phase 책임: menu에서 mode=plan 선택 시 Namespace `mode="plan"` 정확 전달 + `run_session` 정상 진입
   - 본 Phase 외 책임: planner ROLE이 spec.md narrative를 produce하는 것은 `docs/runtime-docs/roles/planner.md` SSOT. spec.md 파일 auto-save 메커니즘은 orchestrator/role.md 책임 (현재 미구현 — JSONL에 텍스트로만 보존). 본 plan은 메뉴 wiring 한정
   - 실패 시(예: planner.md 본문이 prompt 생성 시 에러): 본 plan 외 — 별도 plan으로 role.md 보강 분리

2. **implement 모드 spec 입력 누락**
   - implement는 `--spec` 입력 가정인데 메뉴는 task만 받음
   - 본 Phase는 implement 선택 시 즉시 안내 + back으로 회피 (spec 입력 UI는 별도 plan)
   - 안내 문구 명확: "implement는 spec.md 경로 필요. CLI 직접 호출 권장."

3. **compare subparser 부재**
   - `dialectic compare` 서브커맨드 자체가 없으므로 안내 문구도 "별도 plan 진입 후" 명시
   - 사용자가 안내 보고 `dialectic compare ...` 시도하면 argparse 에러 — 안내 문구는 "현재 미구현, 후속 plan에서 wiring 예정" 표현 권장

4. **mode 메뉴와 `--interactive` 메뉴 자리 충돌 (plan 009 완료 산출 보존)**
   - plan 009 Phase A가 메뉴 default `interactive="critical"` 산출 적용 완료 (uncommitted 작업 트리, cli.py L268)
   - 본 Phase는 `--interactive`는 손대지 X — Namespace `interactive` 라인은 plan 009 산출 `"critical"` 보존 (mode 라인만 동적화)
   - 향후 메뉴에 `--interactive` 선택 UI 추가 시 본 Phase mode 메뉴 직후 또는 별도 단계 자연 삽입 가능 — 별도 plan
