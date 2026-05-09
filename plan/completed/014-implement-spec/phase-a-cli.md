# Phase A · CLI subparser + 메뉴 helper — 014-implement-spec

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: —
- 예상 LOC: ~40 (코드) + ~30 (테스트)

## 1. 목표

`src/cli.py`에 `--spec <path>` 인자 + `dialectic implement` alias subparser + `_input_spec_path` 메뉴 helper 추가. `_input_mode` 단계 2 implement 분기를 deferred 안내에서 active(`return "implement"`)로 변경. `_interactive_menu_body` 단계 3에서 mode에 따라 task 또는 spec 경로 입력 분기.

## 2. 입력

- [`src/cli.py:56-83`](../../src/cli.py) — `p_run` subparser AS-IS (`--task required` + `--mode choices` 정의)
- [`src/cli.py:198-216`](../../src/cli.py) — `_input_task` helper 패턴 참고
- [`src/cli.py:219-250`](../../src/cli.py) — `_input_mode` deferred implement 안내 AS-IS
- [`src/cli.py:380~`](../../src/cli.py) — `_interactive_menu_body` 단계 3 task 입력 호출 AS-IS
- [`src/cli.py:129-152`](../../src/cli.py) — `_safe_input` + `_MenuExit` 패턴 (spec 입력 EOF/Ctrl-C 처리)
- [`outline/03-ux.md:50`](../../outline/03-ux.md) — `dialectic implement --spec ./workdir-tmp/specs/dijkstra.md --workdir ./workdir-tmp` UX SSOT
- 사전 검증 사실: `args.spec`은 argparse default=None — mode!=implement 시 무시 (run_session 책임)
- 사전 검증 사실: post-010 default workdir이 `~/.local/share/dialectic/runs/<ts-id>/` — 사용자가 plan 모드 산출 spec.md 경로를 입력할 때 자동 탐색 가능 narrative는 `?` 도움말에 포함

## 3. 출력

### 3.1 `src/cli.py` `--spec` 인자 추가 (`p_run` 확장)

```python
# spec
p_run.add_argument(
    "--spec",
    type=str, default=None,
    help=(
        "implement 모드 입력 — `<workdir>/specs/<slug>.md` 또는 임의 spec.md 경로. "
        "mode==implement 시 required (run_session 진입 시 검증). "
        "다른 모드에선 무시."
    ),
)
```

### 3.2 `dialectic implement` alias subparser

```python
# spec
p_implement = subs.add_parser(
    "implement",
    help="dialectic implement 모드 — spec.md 본문을 task 자리에 주입 + driver(implementer) ↔ reviewer(spec-reviewer)",
)
p_implement.add_argument("--spec", required=True, type=str, help="implement 모드 spec.md 경로 (필수)")
p_implement.add_argument("--driver", choices=["codex", "claude"], default="codex")
p_implement.add_argument("--reviewer", choices=["codex", "claude"], default="claude")
p_implement.add_argument("--max-turns", type=_positive_int, default=1)
p_implement.add_argument("--workdir", default=None)
p_implement.add_argument("--convergence-streak", type=_positive_int, default=2)
p_implement.add_argument("--interactive", choices=["end-only", "critical", "full"], default="end-only")
# implement subparser는 args.mode 자동 = "implement", args.task 자동 = "" (run_session에서 spec body로 substitution)
p_implement.set_defaults(
    func=lambda args: orchestrator.run_session(args),
    mode="implement",
    task="",
)
```

DRY 권고 (P2 — Phase A §6): `_add_common_args(parser)` helper 추출하여 `p_run`/`p_implement` 공통 인자 단일 정의. 1차 구현은 단순 복사.

### 3.3 `_input_mode` implement 분기 active 변경

```python
# spec — :236-242 deferred 블록 교체
if raw == "3":
    return "implement"
```

기존 deferred 안내 + `continue` 제거. compare(`raw == "4"`) deferred는 유지 (별도 plan).

`_input_mode` docstring `:222-227` 갱신:
- 기존: "implement → '... 별도 plan에서 ... 추가 예정 ...' 안내 + retry"
- 변경: "implement → 'implement' 반환 → 단계 3에서 `_input_spec_path` 분기 (mode-aware)"

### 3.4 신규 helper `_input_spec_path` (`src/cli.py`)

```python
# spec
def _input_spec_path() -> str:
    """단계 3 implement 모드 — spec.md 경로 입력.

    절대 또는 상대 경로 (Path.resolve()로 정규화 후 절대 경로 반환).
    파일 부재·디렉토리·UTF-8 디코딩 실패 시 retry + 안내.
    '?' 도움말 키 — post-010 default workdir narrative 포함
    (`~/.local/share/dialectic/runs/<...>/specs/<slug>.md` 자동 탐색 가능 안내).
    EOF/Ctrl-C → `_safe_input`이 `_MenuExit` raise (기존 `_input_task` 패턴 정합).

    반환: 절대 경로 문자열 (str, Path 아님 — argparse 호환).
    """
```

본문 시그니처 명세:
- `while True:` 루프 + `_safe_input("> ")`
- `?` → 도움말 출력 + `continue`
- 빈 입력 → "spec 경로가 비었습니다 — 다시 입력하거나 Ctrl-C로 종료." + `continue`
- `Path(raw).resolve()` 정규화 → `is_file()` 검증 → 실패 시 안내 + `continue`
- UTF-8 디코딩 검증 (`Path.read_text(encoding="utf-8")` raise → catch → 안내 + `continue`)
- 모두 통과 시 `return str(path)`

### 3.5 `_interactive_menu_body` 단계 3 mode 분기

`src/cli.py:385-446` 인근 `_interactive_menu_body` 본문:

```python
# spec — 단계 2 mode 결정 후 단계 3 분기
mode = _input_mode()
if mode == "implement":
    task = ""
    spec = _input_spec_path()
else:  # run, plan
    task = _input_task()
    spec = None
```

이후 단계 4(매핑/workdir/max-turns) + 진행 확인 prompt(`_input_confirm`)는 그대로. `_input_confirm` 시그니처 확장은 §3.5.1 단일 명세 참조 (중복 회피).

### 3.5.1 `_input_confirm` 시그니처 확장

`src/cli.py:338` 기존 `_input_confirm` helper에 `spec: str | None = None` keyword-only 인자 추가. 본문에서 mode==implement이면 task echo 대신 spec 경로 echo back:

```python
# spec — 기존 _input_confirm 확장 (본 plan 3 줄 추가)
def _input_confirm(
    *, max_turns: int, task: str, mode: str, driver: str, reviewer: str,
    workdir: str | None,
    spec: str | None = None,  # plan 014 신규
) -> bool:
    """진행 확인 prompt — task 또는 spec echo back (mode-aware)."""
    # ... 기존 logic 유지
    if mode == "implement" and spec is not None:
        print(f"spec: {spec!r}")
    else:
        preview = task if len(task) <= 60 else task[:60] + "..."
        print(f"task: {preview!r}")
    # ... 나머지 logic 유지
```

### 3.6 entry-point dispatch

`_interactive_menu_body` 마지막에 args Namespace 구성 시 mode==implement이면 spec 인자 포함:

```python
# spec — Namespace 구성 (단계 4 이후, run_session 호출 직전)
# 메뉴 진입은 alias subparser를 거치지 않으므로 cmd="run" 고정 (mode 필드로 분기 충분)
# alias `dialectic implement` 진입은 별도 path — set_defaults(mode="implement", task="") 자동 적용
args = SimpleNamespace(
    cmd="run",
    task=task, mode=mode, spec=spec,
    driver=driver, reviewer=reviewer,
    max_turns=max_turns, workdir=workdir,
    convergence_streak=2, interactive="end-only",
)
orchestrator.run_session(args)
```

### 3.7 신규 단위 테스트 — `tests/test_implement_spec.py`

```python
# spec — Phase A 케이스 (≥3)
def test_input_spec_path_basic(tmp_path, monkeypatch):
    """tmp_path/spec.md 생성 후 입력 → 절대 경로 반환."""

def test_input_spec_path_missing_retry(tmp_path, monkeypatch):
    """미존재 입력 → retry → 정상 입력으로 수렴."""

def test_input_spec_path_directory_retry(tmp_path, monkeypatch):
    """디렉토리 입력 → retry."""
```

mock 패턴: `monkeypatch.setattr("builtins.input", lambda *args: ...)` 또는 `_safe_input` 직접 monkeypatch (기존 `tests/test_cli_menu.py` 패턴 재사용).

## 4. 작업 단위

- [ ] (Pre-execute) `grep -n "def _input_task\|def _input_mode\|def _interactive_menu_body\|p_run\.add_argument" src/cli.py`로 본 phase 인용 줄 재확인 (post-010/013 line drift 흡수)
- [ ] `src/cli.py:56-83` `p_run`에 `--spec` 인자 추가 (default None)
- [ ] `src/cli.py`에 `p_implement` alias subparser 신규 (위 §3.2 spec 그대로)
- [ ] `src/cli.py:236-242` `_input_mode` implement 분기를 deferred → `return "implement"` 변경 + docstring 갱신
- [ ] `src/cli.py`에 `_input_spec_path` 함수 신규 (위 §3.4 spec — `_safe_input` + Path.resolve + is_file + UTF-8 검증 + `?` 도움말 + retry)
- [ ] `src/cli.py:380~` `_interactive_menu_body` 단계 3 mode 분기 (mode==implement 시 `_input_spec_path` 호출, 그 외 `_input_task`)
- [ ] `_input_confirm` 시그니처에 `spec: str | None = None` 추가 + echo back 분기
- [ ] Namespace 구성 시 `spec=spec` 포함
- [ ] `tests/test_implement_spec.py` 신규 작성 — `_input_spec_path` 3 케이스 (정상/부재retry/디렉토리retry)

## 5. 검증

- `dialectic run --task x --mode implement --spec /tmp/x.md --max-turns 1 --workdir /tmp/test 2>&1 | grep -i spec` → spec 부재 SystemExit 메시지 노출 (Phase B wiring 후 검증)
- `dialectic implement --help` → subparser 인자 표 + `--spec` required 명시 확인
- `dialectic run --help | grep -- --spec` → `--spec` 인자 노출 확인 (`p_run` 확장)
- `pytest -q tests/test_implement_spec.py -k "test_input_spec_path"` 3건 pass
- `pytest -q` 전체 회귀 0 (특히 plan 011 메뉴 wiring 회귀 — `_input_mode` 변경)

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **`--spec`을 다른 mode에 줘도 무시**
   - `--mode run --spec <path>`: argparse는 통과, run_session에서 mode==run이면 spec 무시
   - 사용자 실수 가능 — stderr 경고? 1차 plan 외 (단순 무시 + Phase B `run_session` docstring narrative)

2. **`_add_common_args(parser)` helper 미추출 (DRY)**
   - `p_run` + `p_implement` 인자 중복 — `--driver`/`--reviewer`/`--max-turns`/`--workdir`/`--convergence-streak`/`--interactive`
   - 한쪽 갱신 누락 시 회귀 (P2)
   - **mitigation**: 본 plan 산출 후 별도 cleanup plan에서 추출 권고. Phase A §3.2 코드 블록에 narrative 명시

3. **`_input_spec_path` 한글 경로**
   - WSL/Linux UTF-8 default — `Path.resolve()` + `is_file()` + `read_text(encoding="utf-8")` 모두 한글 path 정합
   - macOS NFD normalization은 본 도구 미지원 (CLAUDE.md §환경)

4. **`_safe_input` EOF 종료 확인 prompt 회귀**
   - 기존 `_input_task` 패턴 그대로 — `_MenuExit` propagate
   - `_input_spec_path`도 동일 패턴 사용 (catch 안 함)

5. **메뉴 단계 3 분기 — `_input_task` 호출 시점 회귀**
   - mode==implement 분기 추가로 `_input_task` 호출 path 1개 줄어듦
   - `_input_task` 자체 시그니처 변경 0 — 회귀 0
   - `_interactive_menu_body` docstring 갱신 (단계 3 narrative `_input_task` → "mode-aware: `_input_task` (run/plan) 또는 `_input_spec_path` (implement)")
