# Phase C · 메뉴 입력 보강 — 008-ui-polish

## 0. 메타

- Phase ID: C
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음) — A·B와 독립 병렬 가능
- 병렬 그룹: A·B 직렬과 무관, C 단독 (`src/cli.py` 단독 수정)
- 예상 LOC: ~30 (코드: task input while True 루프 + `?` 도움말 분기 ~10 / 진행 확인 input + n 거부 분기 ~10 / prompt 문자열 보강 ~5) + ~15 (테스트 3 케이스)

## 1. 목표

본 Phase 종료 시 `src/cli.py:_interactive_menu()`가 (1) task input prompt에 example 명시, (2) task 입력 후 진행 확인 단계 (`driver=codex, reviewer=claude, 1턴 — 진행? [Y/n]:`), (3) `?` 입력 시 도움말 retry 통로를 제공. 기획자 페르소나가 무엇을 입력해야 할지 추측 차단.

## 2. 입력

### 2.1 의존 Phase 산출물

- (없음) — Phase A·B의 print_message·Spinner는 본 phase에서 활용 X (메뉴 단계 자체는 호출 전이라 spinner 무관)

### 2.2 참조 .md (줄 번호까지)

- `outline/03-ux.md` §3.2 (`:140-148`) — task 선택 narrative (직접 입력 옵션 SSOT)
- `outline/03-ux.md` §3.2 (`:160-178`) — 매핑·workdir 선택 narrative (본 phase는 default 매핑 진행 확인 1줄로 minimum cut, 단계 4 정식 메뉴는 plan 010 후속)
- `docs/dev-docs/code-conventions.md` §6 (CLI 인자 처리)
- `src/cli.py` (`:69-107`) `_interactive_menu` 현 구현 (plan 006 산출)
- `plan/008-ui-polish/01-plan.md §2.3`, §5-4
- `plan/completed/006-ui/phase-b-cli-menu.md §3.1` — 메뉴 minimum cut SSOT (변경 X, 본 phase는 보강)

### 2.3 사전 검증된 사실

- `_interactive_menu` (`:69-107`)는 환경 점검 1줄 요약 + task input + EOF/KeyboardInterrupt 안전 종료 + `argparse.Namespace` 직접 구성 + `orchestrator.run_session(args)` 호출 — 본 phase는 task input prompt 보강 + 진행 확인 단계 추가만, `Namespace` 구성·`run_session` 호출 부분 변경 X
- `tests/test_cli_menu.py` 기존 파일 존재 — plan 006에서 EOF/KeyboardInterrupt/empty task 케이스 추가됨. 본 phase는 케이스 추가 형태 (신규 파일 X)
- `input()` raise는 `EOFError`/`KeyboardInterrupt` 둘 다 — 진행 확인 단계도 동일 catch 필요

## 3. 출력

### 3.1 `src/cli.py:_interactive_menu` 수정 (~30 LOC)

```python
# spec
def _interactive_menu() -> int:
    """outline/03-ux §3.2 단계 1·3 minimum cut + UI polish (plan 008-ui-polish).

    Day 2 한정: run 모드 + default 매핑(driver=codex, reviewer=claude) +
    max-turns=1 + --interactive end-only 고정.
    단계 2(모드 선택) / 4(매핑·workdir) / 5(턴 진행 화면)는 후속 plan 분리.

    추가 기능 (plan 008):
    - task input에 example 표시 + '?' 도움말 키
    - task 입력 후 '진행? [Y/n]' 확인 단계 (n 거부 시 안전 종료)
    """
    print("Dialectic-CLI · Day 2 minimum cut: run 모드 + default 매핑 (codex/claude).")
    print("다른 옵션은 CLI 인자로 직접 지정.\n")

    res = check_env()
    active = sum(1 for tool in res.values() for r in tool.values() if r["ok"])
    total = sum(1 for tool in res.values() for _ in tool.values())
    print(f"환경 점검: 활성 {active}/{total}\n")

    # task input — '?' 도움말 retry 루프
    task_prompt = (
        "task (한 줄, 예: 'wave 5의 적 수와 HP를 dict로 반환하는 함수 작성', '?'=도움말): "
    )
    while True:
        try:
            raw = input(task_prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if raw == "?":
            print(
                "도움말: task는 driver(codex)가 구현할 한 줄 작업 의도. "
                "예: 'JSON 파싱 함수 작성', '리스트 중복 제거'. Enter만 입력하면 종료."
            )
            continue
        task = raw
        break

    if not task:
        print("task 비어 있음 — 종료.")
        return 0

    # 진행 확인 단계 — n 거부 시 안전 종료, 빈 입력/y/invalid 모두 Y default
    try:
        confirm = input("driver=codex, reviewer=claude, 1턴 — 진행? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0
    if confirm in ("n", "no"):
        print("취소.")
        return 0

    args = argparse.Namespace(
        cmd="run", task=task, workdir=None,
        driver="codex", reviewer="claude",
        max_turns=1, mode="run",
        convergence_streak=2, interactive="end-only",
    )
    return orchestrator.run_session(args)
```

기존 함수 본문 전체를 위 시그니처로 교체. import 변경 0 (이미 `argparse`, `orchestrator`, `check_env` 보유).

### 3.2 단위 테스트 (~15 LOC, 기존 파일 확장)

`tests/test_cli_menu.py`에 케이스 ≥3 추가.

```python
# spec
def test_interactive_menu_task_prompt_shows_example(monkeypatch, capsys):
    """task input prompt에 'wave 5' substring 포함 (example 표시 회귀 차단).
    monkeypatch: input() lambda return EOFError 또는 빈 문자열로 즉시 종료.
    capsys.readouterr().out에 'wave 5' 또는 prompt 문자열 검증."""

def test_interactive_menu_confirm_n_rejects(monkeypatch):
    """task 입력 후 진행 확인 단계에서 'n' 입력 시 return 0 + capsys '취소' substring.
    monkeypatch: input() 두 번 호출 (task='test', confirm='n')."""

def test_interactive_menu_help_key_retries(monkeypatch, capsys):
    """task input '?' → 도움말 출력 + retry. 두 번째 input에서 빈 문자열 → 종료.
    monkeypatch: input() iter(['?', '']) — '?' 분기 진입 후 retry."""
```

## 4. 작업 단위

- [ ] `src/cli.py:_interactive_menu` task input prompt 변경 (example + '?' 도움말 키 안내 substring 추가)
- [ ] `src/cli.py:_interactive_menu` task input을 `while True` 루프로 — `?` 입력 시 도움말 출력 후 continue, 그 외 break
- [ ] `src/cli.py:_interactive_menu` task 입력 후 진행 확인 단계 추가 — `input("driver=codex, reviewer=claude, 1턴 — 진행? [Y/n]: ")` + `n`/`no` 분기 + EOF/KeyboardInterrupt catch
- [ ] `tests/test_cli_menu.py`에 ≥3 케이스 추가 (example / confirm n / help retry)
- [ ] `pytest tests/test_cli_menu.py -q` 전체 pass (기존 케이스 + 신규 ≥3)
- [ ] `pytest -q` 전체 회귀 0

## 5. 검증

- `pytest tests/test_cli_menu.py -q` 기존 + 신규 모두 pass
- `grep -n "wave 5\|진행?\|도움말" src/cli.py` substring 단언
- `grep -nE "while True:" src/cli.py` 1건 (task input 루프) 단언
- (수동) `echo "" | dialectic` exit 0 (stdin 즉시 EOF → 안전 종료, 회귀 0)
- (수동) `dialectic` (default 진입, stdin tty) → 메뉴 출력 → task 입력 → 진행 확인 prompt → `n` 입력 시 즉시 종료
- review-code P0 = 0 (R-001 — 본 phase는 stdin/stdout만이라 vacuously OK)

## 6. 엣지케이스 / 위험 (Phase 한정)

- **stdin EOF 두 단계**: task input + 진행 확인 input 양쪽 모두 EOFError catch. test 케이스로 각각 검증
- **`?` 입력이 도움말이 아닌 task로 의도된 경우**: 한 글자 `?`는 의미 task 가능성 0 (driver가 처리할 수 있는 의도 X). 도움말 분기로 일관 처리, 사용자가 retry에서 정상 task 입력
- **진행 확인 invalid 입력 (`abc`, `1`)**: 빈 입력·`y`·invalid 모두 Y default — 친절 동작 (사용자 1번 Enter로 통과). `n`/`no`만 명시 거부
- **task 입력에 leading/trailing whitespace**: `raw.strip()` 후 분기 — `?` 매칭은 strip 결과 정확 매치 (`"?  "`는 `"?"`로 정규화)
- **회귀 0**: 기존 plan 006 케이스 (EOF / empty task / KeyboardInterrupt) 모두 그대로 동작. test 회귀 0. 본 phase는 모드/role 매핑 변경 0이라 P-MODE 영향 vacuously OK
- **R-001 P-ENCODING**: 본 phase는 stdin/stdout만 — file I/O 부재. vacuously OK
- **Namespace 직접 구성 패턴 유지**: 본 phase는 진행 확인 단계 추가만, `argparse.Namespace(...)` 구성 부분 변경 X. plan 006 patterns of `parse_args 재호출 회피 — sys.exit 부작용 차단` 그대로 유효
- **사용자 페르소나 마찰**: `진행? [Y/n]` 1단계 추가는 1번 Enter로 통과 — 마찰 최소. `--no-confirm` flag 후속 plan 검토 (본 plan 범위 외)
