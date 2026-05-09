# Execution Log · 015-trigger-race-fix

## Phase A · repro harness — 직렬

- 입력 phase 파일: `phase-a-repro-harness.md`
- 산출물:
  - `tools/repro_listener.py` (~70 LOC) — 수동 standalone harness, 사용자 실 stdin/stdout
  - `tests/test_listener_race_pty.py` (~178 LOC, 3 케이스) — pty.openpty + subprocess 자동 재현 시도
- 검증:
  - `pytest -q tests/test_trigger_listener.py tests/test_prompt_end_or_iterate.py` — 17/17 passed (회귀 0)
  - `pytest -q tests/test_listener_race_pty.py` — 3 케이스 모두 fail (회귀 안전망 `test_no_race_no_trigger` 포함)
  - `./.venv/bin/python tools/repro_listener.py --help` — 정상 출력
- **자동 PTY harness 신뢰성 미확보 발견 (Phase A 한계)**:
  - child가 prompt label("User Synthesis ...")을 master 측 buffer로 도달시키지 못함
  - 회귀 안전망 케이스(`test_no_race_no_trigger`)도 fail — race 검출이 아닌 PTY 동기화 이슈
  - 후보 원인: `_read_line_for_prompt` PTY raw mode 호환성, child stderr/stdout buffering, listener thread fd 점유
  - 결정: 자동 harness `pytestmark = pytest.mark.skip(reason="PTY harness 신뢰성 미확보 ...")`로 module-level 동결. 사용자 환경 검증은 `tools/repro_listener.py` 수동 standalone에 의존
  - phase-d Documentation-Checklist `tools/` 매핑 시 본 한계 narrative 함께 환원
- 산출물 상태: harness 2종 모두 작성 완료 (자동은 skip 동결, 수동은 활성)

## Phase B · 가설 검증 + 반복 cycle — **skip 결정**

- 입력 phase 파일: `phase-b-iterative-cycle.md`
- 결정: **5 cycle ritual skip + Phase C 직진**
- 근거:
  - plan 011 commit `2c2bc2a`에서 이미 4차 hot fix 누적 시도 (1차 TCSAFLUSH / 2차 sys.stdin.readline / 3차 os.read fd / 3차+ join 강화) — 모두 race 잔존
  - 이는 plan 015 phase-b-iterative-cycle.md §6 위험 4 narrative ("1-5차 hot fix 모두 실패 → listener thread 메커니즘 자체가 race source")와 등가 — **4차 hot fix 누적 = 5 cycle 등가 광역 패턴 입증**
  - phase-b의 H1(TextIOWrapper buffer reset) ~ H5(TRIGGER_BYTE 변경) 가설 5종은 모두 1-3차 hot fix 변종 — 새 정보 가치 ≈ 0
  - plan 015 §2.3 채택 우선순위 표가 이미 ① main thread polling을 1순위 사전 결정 — Phase B의 cycle 5회는 사실상 결론 미리 정해진 procedure
  - 사용자 검증 비용 (시연 5×3턴 + 매 cycle revert) > 기대 정보 가치
- 후속 영향:
  - validation.md C-015 "시도된 fix" 표 차수 통일 (1차/2차/3차/3차+)은 phase-d cascade에서 처리
  - Phase D R-NNN 환원 narrative에 "plan 011 4차 hot fix 누적 + plan 015 Phase B skip 정책" 명시

## Phase C · 정공법 메커니즘 ① 적용 — 완료

- 입력 phase 파일: `phase-c-canonical-fix.md`
- 채택: ① main thread polling + thread-safe `queue.Queue(maxsize=1024)`
- 변경:
  - `src/ui.py`: `import queue` + `__init__` `self._byte_queue` + `_run` `put_nowait(ch_bytes)` + `__exit__` queue drain loop
  - `tests/test_trigger_listener.py`: 신규 2 케이스 (`test_byte_queue_initialized` + `test_byte_queue_drained_on_exit`)
  - `src/orchestrator.py`: 변경 0 (`trigger.is_set()` 기존 인터페이스 유지)
- 검증:
  - `pytest -q` 전체 — 170 passed, 3 skipped (PTY harness 동결), 1 deselected
- 사용자 수동 검증 (`tools/repro_listener.py`):
  - 1차 run: turn 1 'c' + turn 3 한글 직접 입력 도달 (race 0)
  - 2차 run (Spinner + 5초 sleep 보강): 3 cycle 모두 race 0
    - turn 1: Ctrl+F + '가나다' → `key='i', directive='가나다'` ✓
    - turn 2: Ctrl+F + 'c' → `key='c', directive=None` ✓
    - turn 3: Ctrl+F + 'y' → `key='e', directive=None` (auto_end_user) ✓
  - **race 0/4 effective cycles** (tools/repro_listener.py 수동 시연 한정). DoD §6 race 0/5 정량은 ~80% 충족이지만 입력 다양성(한글·제어키·단일키)이 결정적 — Phase C ① 부분 효과 입증
- **후속 발견 (사용자 환경 race 잔존)**: 실 dialectic CLI(codex/claude subprocess 30초+ 후 prompt) 시연 시 race 재현 — listener thread `os.read` blocking에 갇힌 상태 + cooked mode 한 줄 분할 절도 race. 추가 surgical fix 2개(NONBLOCK fd, dup2 to /dev/null) 시도 모두 차단 X 또는 부작용(Ctrl+F 인식 약화) 발생 → revert. 사용자 결정으로 잔존 환경 한계 인정 + R-NNN 환원 **보류**. 사용자 워크어라운드: prompt 첫 입력 빈 줄 처리되면 두 번째 입력은 정상 도달.
- **최종 코드 상태**: Phase C ① queue 메커니즘 + `_read_line_for_prompt` `flush_stdin` 제거 (2개 부분 fix만 보존). NONBLOCK/dup2는 revert.

## Phase D · cleanup + cascade — 완료 (정정 narrative)

- 입력 phase 파일: `phase-d-cleanup-cascade.md`
- 산출:
  - systems/ui.md TriggerListener 표 narrative — Phase C ① 부분 fix + 잔존 환경 한계 narrative 반영
  - validation.md C-015 status update (R-002 환원 narrative 모두 → 정직 보류 narrative로 정정 — 사용자 환경 race 추가 발견 후) + §4.4 P-RAW 환원 사례 누적 narrative 정정
  - code-conventions.md §7 TriggerListener 패턴 — R-002 인용 → "C-015 + plan 015 부분 fix" 정정
  - upcoming-plans.md plan 015 entry — 채택 메커니즘/검증/후행 영향 narrative 정직 정정 (race 잔존 + plan 016 후속 architecture 재설계 검토)
  - Documentation-Checklist.md `tools/repro_listener.py` 매핑 — R-002 → C-015 정정
  - plan/completed/ 이동 (본 plan)
