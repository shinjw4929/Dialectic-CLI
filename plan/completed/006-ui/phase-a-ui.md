# Phase A · UI 모듈 — 006-ui

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: — (Phase B가 본 산출 import 의존, 직렬)
- 예상 LOC: ~80 (코드) + ~30 (테스트)

## 1. 목표

본 Phase 종료 시 `src/ui.py`가 6지선다 + directive + spinner를 제공하는 단일 모듈로 자급자족 존재. cli.py default 메뉴 진입 wiring은 Phase B 책임.

## 2. 입력

### 2.1 의존 Phase 산출물

- (없음)

### 2.2 참조 .md (줄 번호까지)

- `outline/03-ux.md` §3.3 (`:254-269`) — 6 키 표 SSOT (`a/r/m/i/e/s` + Enter=iterate)
- `outline/03-ux.md` §3.2 단계 5 (`:180-252`) — 진행 spinner 표시 narrative
- `docs/dev-docs/code-conventions.md` §2 (외부 의존성 0), §6 (CLI 인자 처리)
- `docs/dev-docs/validation.md` R-001 (P-ENCODING — file I/O encoding 명시)
- `plan/006-ui/01-plan.md §2.1`, §5-1, §5-2, §5-3 (UI 키셋·EOF·spinner ANSI 결정)

### 2.3 사전 검증된 사실

- `Meta.is_mock` 필드 이미 존재 (`src/schema.py:32`) — UI는 직접 schema 변경 0
- spinner는 `not sys.stderr.isatty()` 환경에서 silent — pytest 실행 시 noise 0

## 3. 출력

### 3.1 `src/ui.py` (~80 LOC, 신규)

```python
# spec
"""사용자 개입 UI — 6지선다 + directive + spinner.

outline/03-ux.md §3.3 SSOT 키 매핑 (a/r/m/i/e/s).
Enter = iterate + empty directive (default UX).
EOF/KeyboardInterrupt = end (비대화형 환경 안전망).
"""
```

```python
# paste
DECISION_KEYS = ("a", "r", "m", "i", "e", "s")  # outline/03-ux §3.3 SSOT 1:1

KEY_LABEL = {
    "a": "accept driver",
    "r": "accept reviewer",
    "m": "merge",
    "i": "iterate",
    "e": "end",
    "s": "skip review",
}

# spinner ANSI 프레임 — code-conventions §2 외부 의존성 0
SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

INVALID_RETRY_LIMIT = 3  # 잘못된 키 입력 retry 한계 — 비대화형 환경 fallback 트리거
```

```python
# spec
def prompt_decision(
    turn_id: int,
    *,
    interactive_mode: str = "end-only",
) -> tuple[str, str | None]:
    """6지선다 + directive 한 줄 입력. 반환 (key, directive_or_None).

    - turn_id: prompt 라벨 출력에 사용 (outline §3.2 line 216 형식
      `[User Synthesis · Turn {turn_id}]`). retry 시도 N회 안에서 turn_id 불변
    - Enter (빈 입력) → ("i", None)
    - 잘못된 키 → 안내 + retry. INVALID_RETRY_LIMIT 회 fail → ("i", None) fallback
    - KeyboardInterrupt / EOFError → ("e", None) — Ctrl-C·파이프·CI 안전망
    - interactive_mode == "end-only" 시 directive 입력 단계 skip (key만)

    호출자: 본 plan 범위 내 0건 (test 외). 후속 plan(`--interactive critical/full`)에서
    orchestrator.run_session 또는 turn loop 내 호출 wiring.
    """

class Spinner:
    """ANSI spinner (frames=SPINNER_FRAMES). threading.Thread daemon.
    `not sys.stderr.isatty()` 시 모든 메서드 no-op (CI·파이프 silent).
    컨텍스트 매니저로 `with Spinner("running..."): ...` 사용.
    __exit__에서 Event.set() + thread.join(timeout=1) — daemon이지만 명시 정리.
    """
    def __enter__(self) -> "Spinner": ...
    def __exit__(self, *exc) -> None: ...
```

### 3.2 `tests/test_ui.py` (~30 LOC)

```python
# spec
def test_prompt_decision_six_keys(monkeypatch):
    """a/r/m/i/e/s 6 키 모두 정확히 매핑."""

def test_prompt_decision_enter_default(monkeypatch):
    """빈 입력 → ('i', None) (outline/03-ux §3.3 default)."""

def test_prompt_decision_eof_returns_end(monkeypatch):
    """EOFError → ('e', None) — 파이프·CI 안전망."""

def test_prompt_decision_invalid_retry(monkeypatch):
    """잘못된 키 INVALID_RETRY_LIMIT(=3)회 → ('i', None) fallback."""
```

## 4. 작업 단위

- [ ] `src/ui.py` 신규: `DECISION_KEYS`, `KEY_LABEL`, `SPINNER_FRAMES`, `INVALID_RETRY_LIMIT` 상수
- [ ] `prompt_decision(turn_id, *, interactive_mode)` 구현 — keyword-only `*`, try/except `(EOFError, KeyboardInterrupt)` 명시
- [ ] retry counter (INVALID_RETRY_LIMIT 한계) 사용, 비대화형 환경 무한 루프 차단
- [ ] `Spinner` 컨텍스트 매니저 — `threading.Thread(daemon=True)` + `sys.stderr.isatty()` 가드 + `__exit__`에 `Event.set() + thread.join(timeout=1)`
- [ ] `tests/test_ui.py` 신규: 4 케이스 (DoD 항목 1:1)
- [ ] `pytest tests/test_ui.py -q` 4 passed 단언

## 5. 검증

- `pytest tests/test_ui.py -q` ≥4 passed
- `python -c "from src.ui import prompt_decision, Spinner, DECISION_KEYS, KEY_LABEL, INVALID_RETRY_LIMIT; assert DECISION_KEYS == ('a','r','m','i','e','s')"` exit 0
- `grep -nE "(read_text|write_text|open)\(" src/ui.py | grep -v "encoding=\"utf-8\""` exit 1 (encoding 누락 0; file I/O 자체가 부재해도 OK)
- `grep -n "def prompt_decision" src/ui.py` 시그니처에 `*,` 마커 단언

## 6. 엣지케이스 / 위험 (Phase 한정)

- **stdin 닫힘 (`EOFError`)**: `input()` raise → catch → `("e", None)` 반환. test로 검증 (monkeypatch `builtins.input` to raise EOFError)
- **terminal control character**: 사용자 `Ctrl-D` 입력 → EOFError 동치. `Ctrl-C` → KeyboardInterrupt → `("e", None)`
- **spinner thread leak**: `__exit__`에 `Event.set()` + `thread.join(timeout=1)` — daemon이라 main exit 시 자동이지만 명시 join이 안전
- **multi-line directive**: 본 phase는 `--editor` 옵션 미구현 (outline §3.3 line 267, 후속 plan). `input()`은 한 줄만 — narrative 명시
- **encoding (R-001)**: 본 phase 산출은 stdin/stderr만 사용. `read_text`/`write_text`/`open()` 자체가 부재 → vacuously 정합. 후속 plan에서 file I/O 추가 시 명시 강제
- **Windows cmd.exe spinner 깨짐**: `not sys.stderr.isatty()` 가드만 본 phase 처리. isatty=True인 깨진 터미널 명시 catch는 후속 plan(`--no-spinner` flag) (01-plan §5-3)
