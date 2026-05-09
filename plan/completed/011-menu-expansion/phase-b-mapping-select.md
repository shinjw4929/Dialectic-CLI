# Phase B · 단계 4 매핑 선택 (단계 4 묶음의 매핑 슬롯) — 011-menu-expansion

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: A (mode 선택 wiring 완료 후 진입)
- 병렬 그룹: —
- 예상 LOC: ~20 (코드) + ~8 (테스트)
- outline 단계 매핑: outline `:161-170` 단계 4의 매핑 슬롯. Phase C가 같은 단계 4의 workdir·max-turns 슬롯 담당 — 함께 단계 4 묶음 형성

## 1. 목표

`dialectic` 단독 실행 메뉴 단계 4의 매핑 슬롯을 outline `:166-170` narrative 정확 추종 — driver/reviewer 2 조합 표시 (`codex→claude` 기본, `claude→codex` 스왑). default Enter = `codex→claude` (현재 메뉴 하드코딩 동작 보존). same-vendor 4종 확장은 별도 plan(디버깅·single-vendor regression 비교 용도, outline narrative 외).

## 2. 입력

- [`src/cli.py:62-63`](../../src/cli.py) — `--driver` / `--reviewer` argparse choices=`["codex", "claude"]` (변동 없음)
- [`src/cli.py:266`](../../src/cli.py) — Namespace 매핑 하드코딩 `driver="codex", reviewer="claude"` (Phase B 대상). 참고: line 번호는 plan 009 적용 후 (uncommitted)
- Phase A 산출 — `mode` 변수가 `_interactive_menu_body` 안에 존재
- [`outline/03-ux.md:161-170`](../../outline/03-ux.md) — 단계 4 매핑 narrative SSOT (2 옵션 정확 추종)
- 기존 helper 패턴: Phase A `_input_mode` (4 분기 retry 루프)

## 3. 출력

### 3.1 `src/cli.py` 변경

신규 helper `_input_mapping`:

```python
# spec
def _input_mapping() -> tuple[str, str]:
    """단계 4 driver/reviewer 매핑 선택. 2 조합 표시 (outline `:166-170` 정확 추종).

    1) codex → claude   (default)
    2) claude → codex   (스왑)

    default Enter = (1) → ("codex", "claude")
    invalid → 재입력
    EOF/Ctrl-C → _safe_input이 종료 확인 prompt → _MenuExit propagate
    """
```

`_interactive_menu_body` 단계 4 매핑 wiring (Phase A `mode = _input_mode()` + 기존 `task = _input_task()` 후 단계 4 묶음 진입 시점):

```python
# spec
driver, reviewer = _input_mapping()
```

Namespace 구성 (`:266` 매핑 라인) 매핑 동적화 (interactive 라인은 plan 009 산출 `"critical"` 보존):

```python
# spec
args = argparse.Namespace(
    cmd="run", task=task, workdir=None,
    driver=driver, reviewer=reviewer,
    max_turns=max_turns, mode=mode,
    convergence_streak=2, interactive="critical",  # plan 009 산출 보존, 본 Phase 무관
)
```

`_input_confirm` 시그니처 1차 확장 (`:201-211`) — Phase C에서 workdir 추가 예정 (호출부 인자 누락 회피, 본 Phase 작업 단위에 명시):

```python
# spec
def _input_confirm(*, max_turns: int, task: str, mode: str, driver: str, reviewer: str) -> bool:
    """진행 확인 — task + mode + 매핑 + max-turns echo back.

    print: f"mode={mode}, {driver}→{reviewer}, {max_turns}턴"

    NOTE: Phase C에서 workdir 인자 추가 예정. 본 시그니처는 1차 확장이며,
    Phase C 진입 시 함수 시그니처 + 호출부 양쪽 동시 갱신 필요.
    """
```

### 3.2 단위 테스트 추가 — `tests/test_interactive_menu_expansion.py`

```python
# spec
def test_input_mapping_codex_claude():
    """1 → ('codex', 'claude')"""

def test_input_mapping_claude_codex():
    """2 → ('claude', 'codex')"""

def test_input_mapping_default_enter():
    """빈 입력 → ('codex', 'claude') default"""

def test_input_mapping_invalid_retry():
    """'3' (outline 외) → 재입력"""
```

## 4. 작업 단위

- [ ] `src/cli.py`에 `_input_mapping` 함수 추가 (`_input_mode` 직후 위치)
- [ ] 2 조합 분기(`1→codex→claude` / `2→claude→codex`) + default Enter + invalid retry 구현
- [ ] `_interactive_menu_body` 단계 4 묶음의 매핑 슬롯(기존 `task = _input_task()` 직후)에 `driver, reviewer = _input_mapping()` 호출 삽입
- [ ] `_input_confirm` 시그니처 1차 확장(`*, max_turns, task, mode, driver, reviewer`) + docstring에 "Phase C에서 workdir 추가 예정" 명시
- [ ] `_input_confirm` 호출부(`:257`) 인자 추가
- [ ] Namespace `driver=driver, reviewer=reviewer` 동적화
- [ ] 단위 테스트 4 케이스 추가
- [ ] **Phase C 진입 시 본 함수 시그니처 + 호출부 + Namespace 모두 workdir 추가 필요 — 작업 단위 사전 메모로 인지 보장**

## 5. 검증

- `python -c "from src.cli import _input_mapping; print(_input_mapping.__doc__)"` 성공
- `pytest -q tests/test_interactive_menu_expansion.py` Phase A·B 누적 10 케이스 pass
- `pytest -q` 전체 회귀 0
- 실 호출 시연: `dialectic` 실행 → mode=run → 매핑=2 (`claude→codex`) → 1턴 실 호출 → driver가 claude 어댑터로 호출되는지 JSONL `meta.vendor` 확인

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **same-vendor 매핑은 본 plan 외 (별도 plan)**
   - outline `:166-170`은 narrative SSOT이며 2 옵션 정확 추종이 본 plan 결정
   - same-vendor (codex→codex / claude→claude)는 dialectic 다양성 thesis와 충돌 — 디버깅·single-vendor regression 비교 가치는 인정하되 별도 plan에 위임
   - 본 Phase는 outline 정확 추종 — 메뉴 UI도 2 옵션만 노출 (sync-docs cascade 회피)

2. **`_input_confirm` 시그니처 확장 호환성 + Phase C 인지**
   - 현재 `_input_confirm`을 직접 호출하는 외부 코드 없음(grep 검증 필요)
   - 인자 추가는 keyword-only(`*`) 강제 — 호출부 명시성 보장
   - Phase C가 본 함수에 workdir 추가 예정 — Phase B 작업 단위에 사전 메모 + Phase C 작업 단위에 "Phase B에서 1차 확장된 시그니처에 workdir 추가" 양쪽 명시

3. **`--driver`/`--reviewer` argparse 변동 없음**
   - 이미 `choices=["codex", "claude"]` 모든 조합 지원
   - 본 Phase는 메뉴 UI만 추가, argparse 영향 0

4. **mode + 매핑 조합 의미 검증 부재**
   - 예: mode=plan + driver=claude + reviewer=codex 같은 조합이 의미 있는지 검증 X
   - 본 Phase는 단순 wiring만 — 의미 검증은 사용자 책임 (또는 별도 plan)
