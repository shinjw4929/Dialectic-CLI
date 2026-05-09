# Phase B · TriggerListener (termios raw mode) — 009-user-synthesis-wiring

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A·B·C (의존성 0)
- 예상 LOC: ~50 LOC + 테스트 ~20 LOC

## 1. 목표

`src/ui.py`에 `TriggerListener` 컨텍스트 매니저 신설. POSIX termios raw mode + 별도 thread + `select.select` 비동기 stdin 읽기로 Ctrl+F (`chr(0x06)`) 단일 byte 캡처 → `threading.Event` set. main thread는 `Event.is_set()`로 트리거 확인. cleanup-restart 패턴 — 매 턴 끝 `__exit__` 시 thread join + tcsetattr 복원, 다음 턴 진입 시 새 인스턴스 `__enter__`.

## 2. 입력

- `src/ui.py:111-155 Spinner` — 동일 패턴 ref (isatty 가드 line 122, threading.Thread daemon line 146, threading.Event line 120, `__enter__` line 144 / `__exit__` line 150 + try/finally는 `_run` line 124-142)
- `src/ui.py:209-287 stdin_canonical_off` — 기존 raw mode 자산. 동일 fd 점유 자산이라 가동 시점 분리 정책 (R5)
- 표준 라이브러리: `termios`, `tty`, `select`, `threading`, `sys`, `signal`
- 참조: `docs/dev-docs/code-conventions.md` §2 — 외부 의존성 0
- 참조: `docs/dev-docs/architecture.md` ADR-6 — cwd 격리 (raw mode가 위반하지 않는지 검증)
- 참조: `docs/dev-docs/validation.md` P-RAW — raw mode 견고성

## 3. 출력

`src/ui.py` 추가 (Spinner 클래스 아래):

```python
# spec
class TriggerListener:
    """Ctrl+F (chr(0x06)) 단일 byte 비동기 listener.

    Spinner와 동일 패턴 (isatty 가드, threading.Thread daemon, threading.Event).
    POSIX termios raw mode → listener thread fd 한정. main thread stdout/stderr 영향 X.
    Windows native cmd는 termios import 실패 → no-op fallback (self._enabled=False).

    cleanup-restart 패턴: __exit__ 시 thread.join + tcsetattr 복원 → 매 턴 끝
    `with TriggerListener() as trigger:` 블록 종료 → main thread `prompt_end_or_iterate`
    호출 (canonical mode 회복) → 다음 턴 진입 시 새 인스턴스 `with`. fd 동시 점유 0
    (P-RAW R5 차단). 비용 ms 단위, 사용자 인지 0.

    컨텍스트 매니저 사용 (한 턴 단위):
        for turn in ...:
            with TriggerListener() as trigger:
                run_turn(...)
                if trigger.is_set() or converged:
                    pass  # block exit → cleanup
            # 여기서 prompt_end_or_iterate (canonical mode)

    __enter__: stderr 안내 1줄 + thread.start(). isatty=False면 no-op
    __exit__: stop event set + thread.join(timeout=THREAD_JOIN_TIMEOUT_S)
              + try/finally tcsetattr 복원 (R3 안전망 필수)
    """

    TRIGGER_BYTE: int = 0x06  # Ctrl+F (paste — 변형 금지, Linux ASCII control char)

    def __init__(self) -> None:
        ...

    def is_set(self) -> bool:
        """트리거 발생 여부 (threading.Event proxy)."""
        ...

    def __enter__(self) -> "TriggerListener":
        ...

    def __exit__(self, *exc: object) -> None:
        ...
```

`tests/test_trigger_listener.py` 신규 (~20 LOC):
- `is_set` 초기값 False
- `not isatty()` 환경에서 모든 메서드 no-op (`monkeypatch sys.stderr.isatty` False)
- `__exit__` 후 raw mode 해제 — `termios.tcgetattr(0)`이 진입 전 attrs와 일치 (실 tty 환경 한정 또는 mock)
- `__exit__` 예외 발생 시도 cleanup 보장 — `with TriggerListener(): raise RuntimeError` try/except 후 attrs 복원 단언
- cleanup-restart round-trip: `with TriggerListener(): pass` 두 번 연속 → 매번 raw mode 진입·복원 정상

## 4. 작업 단위

- [ ] `src/ui.py`에 `TriggerListener` 클래스 추가 (Spinner 아래)
- [ ] `__init__`: termios import 가능 여부 가드 (`try: import termios except ImportError: termios=None`) → `self._enabled = sys.stderr.isatty() and termios is not None`
- [ ] `__enter__`: `self._enabled` 시 stderr `"[i] Ctrl+F = 다음 턴 끝에 개입 단계 진입"` 1줄 출력 + 진입 전 `termios.tcgetattr(fd)` 보존 + thread.start()
- [ ] thread `_run`: `tty.setcbreak(fd)` 진입 → `while not self._stop.is_set(): if select.select([sys.stdin],[],[],0.1)[0]: ch=sys.stdin.read(1); if ch and ord(ch)==self.TRIGGER_BYTE: self._triggered.set(); return`
- [ ] `__exit__` try/finally: `self._stop.set()` + `self._thread.join(timeout=THREAD_JOIN_TIMEOUT_S)` + `termios.tcsetattr(fd, termios.TCSADRAIN, self._old_attrs)` (try/except OSError silent)
- [ ] `is_set` 인터페이스 (threading.Event proxy)
- [ ] `tests/test_trigger_listener.py` 신규 ≥4 케이스 (R3 cleanup 단언 + cleanup-restart round-trip 포함)
- [ ] `pytest tests/test_trigger_listener.py -q` pass

## 5. 검증

- `pytest tests/test_trigger_listener.py -q` ≥4 케이스 pass
- **R1 실 호출 검증** (Phase D 진입 전 필수): 임시 스크립트로 `with TriggerListener() as trigger: subprocess.run(["sleep","3"])` 실행 + 사용자가 Ctrl+F 입력 → `trigger.is_set()=True` 단언. 자식 subprocess가 stdin을 점유해도 listener가 capture 가능한지 확인
- **R3 안전망 단위 테스트**: `with TriggerListener(): raise RuntimeError` 후 `termios.tcgetattr(0)` 비교 단언 (try/finally 동작 검증)
- **R5 분리 검증**: `_check_env_with_spinner_retry`(`stdin_canonical_off` 사용) 호출 후 `with TriggerListener()` 진입 전후 fd 상태 확인 — 동시 active 0 보장 (가동 시점 격리)
- 기존 회귀 0 — `src/ui.py:Spinner`/`stdin_canonical_off`/`stdin_utf8_mode`/`flush_stdin`/`print_message` 동작 변경 X

## 6. 엣지케이스 / 위험 (Phase 한정)

- **R1 (subprocess stdin 충돌)**: subprocess.run(input=prompt) 자식 stdin이 PIPE로 격리됐다는 가정이 OS·Python 버전·자식 CLI 동작에 의존. 실 호출 검증에서 capture 실패 시 SIGUSR1 signal handler fallback 검토 (kill -USR1 PID 명령 — 다른 터미널에서 입력)
- **R2 (raw mode 영향 범위)**: raw mode = stdin 한정이라 main thread stdout/stderr 영향 X. spinner·`print_message` 출력 정상 동작 확인 (plan 008 산출과 동시 가동)
- **R3 (tcsetattr 복원 실패)**: 본 도구 abort/예외 시 raw mode 복원 안 되면 사용자 terminal echo·canonical mode 부재로 사용 불가. `__exit__` try/finally 필수 + SIGINT 핸들러 등록(abort 시 복원) — 단 SIGINT 핸들러 등록은 plan 횡단 영향이라 Phase D wiring 시 검토
- **R4 (POSIX 한정)**: Windows native cmd는 termios 부재. `try: import termios except ImportError: termios=None` 가드 → `self._enabled=False` no-op. `docs/dev-docs/code-conventions.md`에 narrative 추가 (Phase E sync-docs cascade)
- **R5 (기존 raw mode 자산 중첩)**: `src/ui.py:209-287 stdin_canonical_off` 가 메뉴 진입 + spinner 동안 canonical mode off. TriggerListener는 turn loop 진입 후 가동. 가동 시점 분리 → 동시 active 0 — Phase D §3 cleanup-restart 패턴 + `run_session` 내부에서만 listener wrap (메뉴는 wrap 외부)
- 키 입력 race: 사용자가 thread.start 전 Ctrl+F 누른 byte는 OS 입력 버퍼에 남음. tty.setcbreak 후 select가 즉시 read해서 처리 — 정상 동작 (§5 실 호출에서 확인)
- 단위 테스트의 termios mock 한계: pytest 환경은 isatty=False가 default라 raw mode 진입 path 미실행. 실 tty 환경 검증은 §5 실 호출 단계에서 보강 (R3 단위 테스트는 monkeypatch로 isatty=True 강제 + termios.tcgetattr stub)
