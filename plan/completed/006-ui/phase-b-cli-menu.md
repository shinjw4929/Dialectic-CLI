# Phase B · CLI default 메뉴 진입 + sync-docs cascade — 006-ui

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: A (UI 모듈)
- 병렬 그룹: —
- 예상 LOC: ~30 (cli.py 수정) + ~30 (단위 테스트) + 문서 cascade

## 1. 목표

본 Phase 종료 시 기획자 페르소나(outline/03-ux §3.1 line 19, Q14)가 `dialectic` 단독 실행(default 진입) → 메뉴 표시 → task 한 줄 입력 → run 분기 자동 호출. EOFError 시 안전 종료(exit 0). systems/ 문서 갱신으로 sync-docs `BLOCKED` 0.

## 2. 입력

### 2.1 의존 Phase 산출물

- Phase A 산출: `src/ui.py` (`Spinner` import용, 메뉴 출력 단계에서 활용)

### 2.2 참조 .md (줄 번호까지)

- `outline/03-ux.md` §3.1 (`:19-69`) — 진입로 1·2 + `--interactive` 강도 dial
- `outline/03-ux.md` §3.2 (`:104-252`) — 메뉴 단계 1~5 narrative (본 phase는 단계 1·3 minimum cut)
- `docs/dev-docs/systems/orchestrator.md` (`:148-153`) — `--task`(필수), `--workdir`, `--driver`, `--reviewer`, `--max-turns`, `--mode`, `--convergence-streak`, `--interactive` 인자 표 + default 메뉴 진입 narrative 추가 대상
- `docs/runtime-docs/systems/run-mode.md` (`:1-110`) — 진입로 narrative 보강 대상
- `docs/dev-docs/Documentation-Checklist.md §1.1` (`:64`) — `src/cli.py` 행 매핑 (변경 없음 — 본 phase 수정이 명세 그대로)
- `src/cli.py` (`:1-85`), `src/env_check.py` (`:36-49` `check_env()` 결과 형식)
- `plan/006-ui/01-plan.md §2.2`, §5-2, §5-4

### 2.3 사전 검증된 사실

- `args.cmd is None` 분기는 현재 `parser.print_help() + return 0` (`cli.py:64-66`) — 변경 대상
- `env_check.check_env()` 반환은 `dict[str, dict[str, dict[str, Any]]]` — 메뉴 첫 줄 요약 출력에 활용 가능
- `argparse.Namespace` 직접 구성 채택 — `parser.parse_args(["run", ...])` 재호출은 sys.exit 부작용(`--task` 누락 등 edge에서 SystemExit) 위험으로 기각

## 3. 출력

### 3.1 `src/cli.py` 수정 (~30 LOC)

```python
# spec
def _interactive_menu() -> int:
    """outline/03-ux §3.2 단계 1·3 minimum cut.

    Day 2 한정: run 모드 + default 매핑(driver=codex, reviewer=claude) +
    max-turns=1 + --interactive end-only 고정.
    단계 2(모드 선택) / 4(매핑·workdir) / 5(턴 진행 화면)는 후속 plan 분리.

    EOFError / KeyboardInterrupt → exit 0 (안전 종료).

    parser 인자 미수령 — Namespace 직접 구성으로 argparse 분기 우회 (cli.py
    args.func(args) 패턴과 비대칭은 minimum cut 한정, 후속 plan에서 정합화 검토).
    """
    print("Dialectic-CLI · Day 2 minimum cut: run 모드 + default 매핑 (codex/claude).")
    print("다른 옵션은 CLI 인자로 직접 지정.\n")

    # 환경 점검 1줄 요약 (env_check.check_env() 결과 → 활성 N/2 형태)
    res = check_env()
    active = sum(1 for tool in res.values() for r in tool.values() if r["ok"])
    total = sum(1 for tool in res.values() for _ in tool.values())
    print(f"환경 점검: 활성 {active}/{total}\n")

    try:
        task = input("task (한 줄): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()  # newline 정리
        return 0
    if not task:
        print("task 비어 있음 — 종료.")
        return 0

    # default 매핑으로 run_session 직접 호출 (parser.parse_args 재호출 회피 — sys.exit 부작용 차단).
    # argparse Namespace 직접 구성: run subparser default 값 + task input 합성.
    args = argparse.Namespace(
        cmd="run", task=task, workdir=None,
        driver="codex", reviewer="claude",
        max_turns=1, mode="run",
        convergence_streak=2, interactive="end-only",
    )
    return orchestrator.run_session(args)


# main() 안 if not args.cmd 분기 변경
if not args.cmd:
    return _interactive_menu()
```

### 3.2 `tests/test_cli_menu.py` (~30 LOC, 신규)

```python
# spec
def test_interactive_menu_eof_exits_zero(monkeypatch, capsys):
    """input() EOFError raise → _interactive_menu return 0 + traceback 노출 X."""

def test_interactive_menu_empty_task_exits(monkeypatch, capsys):
    """빈 task 입력 → return 0 ('task 비어 있음' 메시지)."""

def test_interactive_menu_keyboard_interrupt(monkeypatch):
    """KeyboardInterrupt → return 0 안전 종료."""
```

### 3.3 sync-docs cascade

| 문서 | 갱신 내용 |
|---|---|
| `docs/dev-docs/systems/orchestrator.md §cli` (`:148-153`) | default 메뉴 진입 narrative 추가: "기획자 페르소나의 default 진입로. `dialectic` 단독 실행 시 `_interactive_menu` 호출. Day 2 minimum cut: run 모드 + default 매핑 + task 한 줄 입력 후 즉시 run 분기. EOFError/KeyboardInterrupt 안전 종료." |
| `docs/runtime-docs/systems/run-mode.md §1` | 진입로 narrative 보강: "`dialectic` (default 진입) → 메뉴 → task 입력 → run 분기 (default 매핑). CLI 인자 명시는 자동화/CI용." |
| `README.md` §사용 (또는 §빠른 시작) | 진입로 1(메뉴) 5초 데모 한 줄: `$ dialectic` + 결과 narrative 1줄. Day 2 한정 동작 (모드/매핑 미선택) 명시. 위치: 기존 `dialectic run --task ...` 예시 직전 또는 직후 |
| `docs/dev-docs/Documentation-Checklist.md §1.1` (`:66`) | `src/ui.py` 행 outline 매핑 사실 오류 정정 — `outline/03-ux.md §2.2/2.3` → `§3.2/3.3` (실제 outline 헤더와 정합. §2.x는 outline에 부재) |

## 4. 작업 단위

- [ ] `src/cli.py:_interactive_menu()` 신규 함수 (인자 0) — env_check 1줄 요약 + task input + EOF/KeyboardInterrupt catch + `argparse.Namespace` 직접 구성 후 `orchestrator.run_session(args)` 호출 (parser.parse_args 재호출 회피)
- [ ] `src/cli.py:main()` `if not args.cmd:` 분기 변경 → `return _interactive_menu()`
- [ ] **Spinner import 부재** — 본 phase에서 Spinner 사용처 0 (env_check은 비용 0). dead import 차단 위해 import X. 후속 plan(`--interactive critical/full` 추가 시)에서 Spinner를 driver/reviewer 호출 wrapping에 사용
- [ ] `tests/test_cli_menu.py` 신규 — ≥3 케이스 (EOF / empty task / KeyboardInterrupt)
- [ ] `pytest tests/test_cli_menu.py -q` pass 단언
- [ ] `pytest -q` 전체 회귀 0 (8 → ≥10 파일 모두 pass)
- [ ] `docs/dev-docs/systems/orchestrator.md §cli` default 메뉴 진입 narrative 추가
- [ ] `docs/runtime-docs/systems/run-mode.md §1` 진입로 narrative 보강
- [ ] `README.md` 진입로 1 5초 데모 + Day 2 한정 narrative
- [ ] `docs/dev-docs/Documentation-Checklist.md:66` `src/ui.py` 행 outline 매핑 정정 (§2.2/2.3 → §3.2/3.3)
- [ ] sync-docs 스킬 호출 → BLOCKED 0 단언

## 5. 검증

- `pytest tests/test_cli_menu.py -q` 3 passed
- `pytest -q` 전체 회귀 0
- `echo "" | dialectic` exit 0 (stdin 즉시 EOF → 안전 종료, traceback 0)
- `echo "test task" | dialectic` exit 0 (task 입력 후 run 분기 — codex/claude 인증 부재 시 `kind=error` JSONL 라인 + meta 종료, 정상 동작)
- `dialectic` (default 진입, stdin tty) → 메뉴 출력 → Ctrl-D → exit 0
- `sync-docs` 스킬 호출 → BLOCKED 0
- `grep -n "interactive_menu\|default 메뉴\|default 진입" docs/dev-docs/systems/orchestrator.md docs/runtime-docs/systems/run-mode.md` 매핑 갱신 확인
- review-code P0 = 0 (R-001 — 본 phase는 file I/O 0이라 vacuously OK)

## 6. 엣지케이스 / 위험 (Phase 한정)

- **stdin EOF**: `input()` raise → catch → `print()` (newline 정리) + `return 0`. test 케이스 1
- **빈 task 입력**: `task.strip() == ""` 시 안내 1줄 + `return 0`. 평가자가 enter만 누른 시나리오 안전
- **task 입력에 `--` 같은 argparse 토큰**: 본 phase는 `argparse.Namespace`를 직접 구성하므로 task 문자열이 argparse 파싱 단계 거치지 않음 → `--help`/`--version` 같은 corner case 자연 안전 (parse_args 재호출 회피의 부수 이점)
- **default 매핑 시 인증 부재**: 사용자가 `dialectic` 진입 + task 입력했지만 codex/claude 인증 부재 → run_session 진입 후 `kind=error` JSONL 기록 + `auto-end (error: ...)` 메타 (orchestrator 정상 동작). 메뉴 자체는 exit 0
- **회귀 0 (P-MODE)**: `if not args.cmd` 분기 변경만, 기존 `run`/`doctor` subcommand 동작 무영향. 기존 8 테스트 파일 회귀 0
- **sync-docs 누락**: orchestrator.md / run-mode.md / README 3 문서 cascade — 1개라도 누락 시 BLOCKED → commit 차단. 작업 단위에 3 행 명시
- **R-001 P-ENCODING**: 본 phase는 stdin/stdout만 사용 (file I/O 0). `_interactive_menu` 안에 `read_text`/`write_text`/`open()` 부재 → vacuously OK
