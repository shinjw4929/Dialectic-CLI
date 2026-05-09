# Phase C · 정공법 메커니즘 채택 + 적용 — 015-trigger-race-fix

## 0. 메타

- Phase ID: C
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: B (반복 cycle 결과 — race 해소 가설 채택 또는 5회 도달 narrative)
- 병렬 그룹: —
- 예상 LOC: ~80 (TriggerListener 메커니즘 변경) + ~30 (테스트)
- 진입 조건: Phase B에서 (a) 채택된 가설 fix 정식 적용, 또는 (b) 5 cycle 도달 + race 잔존 → 메커니즘 자체 변경

## 1. 목표

채택된 정공법 메커니즘으로 TriggerListener race 완전 제거. plan 009 critical 모드 UX(매 턴 Ctrl+F trigger 가능) 보존. harness 자동 재현 0건 + 사용자 수동 시연 5회 race 0건.

## 2. 입력

- Phase B 결과 — 채택된 가설 또는 메커니즘 강제 변경 narrative
- Phase A harness — race 재현 검증 도구
- 정공법 메커니즘 후보 4종 (01-plan.md §2.3):

  | # | 메커니즘 | 장점 | 단점 |
  |---|---|---|---|
  | ① | listener thread 유지 + thread-safe Queue + main thread polling | byte 절도 0 (queue 보존), readline race 0 | queue → main thread forward 정책 결정 필요 (queue 잔존 byte 처리) |
  | ② | signal-based trigger (SIGUSR1) | readline lib 영향 0, race 0 | 키 입력 매핑 어려움 (terminal에서 직접 signal 발생 X) |
  | ③ | listener fd dup + close 강제 종료 | thread 강제 종료 가능 | stdin fd 점유 복잡 + dup된 fd vs main thread fd 동기화 어려움 |
  | ④ | TRIGGER_BYTE 변경 (0x06 → 0x14 등) | 가장 작은 변경, readline forward-char 매핑 충돌 회피 | 사용자 익숙도 낮아짐 + race 자체는 잔존 (메커니즘 동일) |

- 채택 우선순위 (Phase B 결과 의존):
  - **1순위: ① main thread polling + thread-safe Queue (채택, §3.2 단일 결정)**
  - 2순위: ② signal-based (race 0이지만 UX 비친화)
  - 3순위: ③ fd dup/close (위험)
  - 4순위: ④ TRIGGER_BYTE 변경 — 사전 검증 실패 (`src/ui.py:323-325` 코드 주석 narrative상 Ctrl+T 시도 동일 결함, fallback narrative만)

## 3. 출력

### 3.1 채택 메커니즘 narrative (본 phase 본문 기록)

Phase B 결과 + Phase C 진입 시 채택 결정 narrative 1줄 + 근거 (사용자 시연 결과 또는 harness 통계).

### 3.2 채택 메커니즘별 코드 변경 안내 (실제 채택 후 1개만 적용)

#### 채택 ① main thread polling — thread-safe Queue 버전 (단일 결정)

설계: listener thread 유지하되 stdin byte를 thread-safe `queue.Queue`에 push → main thread가 매 cycle queue.get_nowait()로 검사. listener thread는 byte를 절도하지 않고 queue에 전달만 — main thread readline은 queue 비어있는 byte만 받음 (race 0). §6 위험 1 narrative 정합 (이전 §3.2 "thread 폐기" 표현 정정).

```python
# spec
"""src/ui.py TriggerListener — thread-safe Queue 패턴으로 메커니즘 변경.

기존: listener thread + select + os.read → byte 절도 → race 잔존
변경: listener thread + select + os.read → byte를 thread-safe queue.Queue에 push.
     main thread `poll_trigger_byte(timeout_s=0.0)` helper가 queue.get_nowait()로
     검사 → 0x06 byte 발견 시 trigger.set. byte 절도 0 (queue가 byte 보존).
     readline 호출 시점에 queue를 비우고 stdin 직접 read → race 0.

신규 helper:
    def poll_trigger_byte(*, timeout_s: float = 0.0) -> bool:
        '''queue.Queue에서 byte 검사 — TRIGGER_BYTE 발견 시 trigger.set + True.
        timeout_s=0.0 즉시 반환 (non-blocking). 그 외 byte는 queue에 보존
        (다음 prompt readline 시 stdin으로 forward).
        '''

TriggerListener 변경:
    __init__: self._byte_queue: queue.Queue[bytes] 추가 (maxsize=1024)
    _run thread: os.read(fd, 1) → self._byte_queue.put_nowait(byte) — TRIGGER_BYTE
                 검사 X (main thread polling 책임)
    __exit__: queue 안 잔존 byte는 **폐기** (단일 결정). forward 시 trigger byte(0x06)가 stdin readline에 흘러 사용자 'y' 입력에 prefix 발생 — race 0 보장 위반. tcflush(TCIFLUSH)로 kernel queue도 동시 비움 (3차 fix 누적 패턴 보존)

orchestrator 통합 지점:
    src/orchestrator.py:_run_session_critical (line 738-790 부근, plan 009 산출)
        for turn in range(1, max_turns_runtime + 1):
            with TriggerListener() as listener:
                run_turn(...)  # subprocess 호출 — blocking
            # __exit__ 후 main thread polling
            triggered = poll_trigger_byte()  # queue 검사
            if triggered or converged or last_turn:
                key, directive = prompt_end_or_iterate(...)
                # readline은 stdin 직접 read — listener queue 영향 0
"""
```

주요 변경 위치 (line 번호는 현재 코드 기준):
- `src/ui.py:297-547 TriggerListener` — `__init__`/`_run`/`__exit__`에 queue 메커니즘 추가, `_run` byte 검사 로직 단순화 (queue.put만)
- `src/ui.py` — 신규 `poll_trigger_byte(*, timeout_s: float = 0.0) -> bool` 함수 (TriggerListener 외부, listener instance 참조용)
- `src/orchestrator.py:_run_session_critical` (실측 line 위치 — Phase B 진입 시 grep) — `with TriggerListener` 블록 종료 직후 `poll_trigger_byte()` 호출
- 기존 `_read_line_for_prompt` (Bug 1 fix 2차) **보존** — fd-level os.read 우회 자체는 유효 (TextIOWrapper buffer race 차단 효과)

#### 기타 후보 (채택 안 함 시 narrative)

채택 ②/③/④는 ① 채택 시 무관. ① 검증 실패 시 fallback narrative — phase-c §6 위험 4 참조.

#### 채택 ② signal-based trigger

```python
# spec
"""src/ui.py — SIGUSR1 핸들러로 trigger.

import signal로 SIGUSR1 핸들러 등록 → 사용자가 별도 터미널에서 `pkill -USR1 dialectic` 또는 키보드 매크로(예: Ctrl+F → SIGUSR1 매핑)로 trigger.

장점: stdin race 0
단점: 사용자 매핑 부담 — 안내 narrative 강화 필요
"""
```

#### 채택 ④ TRIGGER_BYTE 변경

```python
# spec
"""src/ui.py — TRIGGER_BYTE 변경.

기존: TRIGGER_BYTE: int = 0x06  # Ctrl+F (readline forward-char 매핑)
변경: TRIGGER_BYTE: int = 0x14  # Ctrl+T (readline transpose, 덜 중요)
또는: TRIGGER_BYTE: int = 0x07  # Ctrl+G (readline abort-line, 덜 중요)

stderr 안내 갱신: "Ctrl+T 2회 연타 = 다음 턴 끝 개입"
사용자 narrative cascade — 모든 안내 + docs.
"""
```

### 3.3 단위 테스트 보강

- `tests/test_listener_race_pty.py` — Phase A 산출 + 채택 메커니즘 케이스 ≥3 추가
- `tests/test_trigger_listener.py` — 메커니즘 변경에 따른 회귀 정합 (fake termios mock 패턴 갱신)
- plan 009 critical 모드 회귀 시연 — `dialectic` 메뉴 진입 → 1턴 진행 도중 trigger → 턴 끝 prompt 정상 (memory: plan 009 산출 시연 매트릭스)

### 3.4 cascade — Phase D 위임

- `docs/dev-docs/systems/ui.md` TriggerListener 표 + narrative 갱신 → Phase D
- `docs/dev-docs/validation.md` C-015 → R-NNN 환원 narrative → Phase D
- 본 Phase는 코드만 책임

## 4. 작업 단위

- [ ] Phase B 결과 review → 채택 메커니즘 결정 (4 후보 중 1)
- [ ] 채택된 메커니즘 코드 변경 (`src/ui.py` ~50-80 LOC)
- [ ] 기존 hot fix 누적 코드 정리 — plan 011 commit `2c2bc2a`의 1차/2차/2차+ fix 중 채택 메커니즘과 충돌하는 부분 revert
- [ ] `_read_line_for_prompt` helper는 보존 권장 (Bug 1 fix 2차의 fd-level os.read 우회 자체는 유효 — TextIOWrapper buffer 영향 차단)
- [ ] 단위 테스트 갱신 (`tests/test_trigger_listener.py` + `tests/test_listener_race_pty.py`)
- [ ] harness 자동 재현 (`pytest -q tests/test_listener_race_pty.py`) race 0건 통과
- [ ] 사용자 수동 시연 5회 (`./.venv/bin/python tools/repro_listener.py --turns 3`) — race 0건 확인
- [ ] plan 009 critical 모드 시연 회귀 — `dialectic` 메뉴 진입 → mode=run + 매핑 default + workdir /tmp/dialectic-c-test → 1턴 진행 도중 Ctrl+F → 턴 끝 prompt 정상

## 5. 검증

- `pytest -q` 전체 회귀 0 (특히 `tests/test_trigger_listener.py` + `tests/test_prompt_end_or_iterate.py` + `tests/test_orchestrator_decision_wiring.py` + `tests/test_listener_race_pty.py`)
- harness 자동 재현 0건 (race 재현 case 모두 race 0 통과)
- 사용자 수동 시연 narrative 보고 — 5회 cycle 모두 race 0 + UX 보존
- plan 009 critical 모드 시연: dialectic 1턴 진행 도중 Ctrl+F → 턴 끝 prompt → 'y' 입력 → auto_end_user 정상

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **메커니즘 ① 채택 — thread-safe Queue 패턴 (단일 결정)**
   - §3.2 채택 narrative와 정합: listener thread 유지 + byte 절도 X + queue로 byte 전달
   - main thread polling은 `with` 블록 종료 직후 `poll_trigger_byte()` 단일 호출 (subprocess 호출 사이 cycle polling 불필요)
   - 코드 변경 ↓ (TriggerListener 본문 + 신규 helper 1개 + orchestrator 1줄 호출 추가)

2. **메커니즘 ④ TRIGGER_BYTE 변경 — 사전 검증 실패 narrative**
   - `src/ui.py:323-325` 코드 주석: "Ctrl+T로 변경 시도했으나 동일 결함. 환경 특성으로 받아들임"
   - 즉 ④ 후보는 사용자 narrative상 race 해소 X — Phase B/C 채택 우선순위에서 사실상 4위 (이전 2위는 narrative 부정확)
   - 차단: ① 채택 narrative + ④는 fallback 후보로만 명시 (§3.2 narrative 갱신 시 우선순위 표 정정)

3. **plan 009 산출 회귀 — Ctrl+F UX 변경**
   - ④ 채택 시 Ctrl+F → Ctrl+T 등 변경 → 사용자 narrative 변경 (안내 문구 + docs)
   - 차단: validation.md C-015 narrative + commit message에 명시

4. **harness 자동 재현 vs 사용자 시연 결과 불일치 (Phase B와 동일)**
   - 차단: 양쪽 모두 검증 + 본 Phase §3.1 narrative 명시

5. **채택 ②/③ 메커니즘 시 plan 007 mock 어댑터 (deferred) 영향**
   - mock 어댑터는 stdin 처리 X — TriggerListener 메커니즘 변경과 무관
   - 차단: plan 007 진입 시 채택 메커니즘과 호환 narrative만 추가
