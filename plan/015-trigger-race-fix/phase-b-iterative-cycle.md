# Phase B · 가설 검증 + 반복 cycle — 015-trigger-race-fix

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: A (harness 구축 완료 — 가설 fix 즉시 검증 가능)
- 병렬 그룹: —
- 예상 LOC: ~30 (가설 fix 누적, 채택 X) + ~10 (테스트 narrative)
- cycle 한계: **5회**. 5회 도달 + race 잔존 시 Phase C 정공법 강제 진입

## 1. 목표

Phase A 산출 harness로 가설 fix → 사용자 시연 → race 재현 여부 확인 → 추가 fix → 재시연 cycle. 본 Phase 산출은 race 0 (cycle 통과) 또는 5회 도달 narrative (Phase C 진입 단서).

## 2. 입력

- Phase A 산출 — `tools/repro_listener.py` (수동) + `tests/test_listener_race_pty.py` (자동)
- Phase A 사용자 환경 narrative (terminal emulator, locale, WSL 버전, race 재현률)
- 현재 `src/ui.py:297-547 TriggerListener` + `src/ui.py:146-247 prompt_end_or_iterate` (3차+ fix 누적 코드, plan 011 commit `2c2bc2a`)
- [`docs/dev-docs/validation.md`](../../docs/dev-docs/validation.md) §3 C-015 — 1차/2차/3차/3차+ 시도 narrative (plan 015 차수 통일 후) + 실패 패턴
- 가설 후보 (각 cycle 1개씩 시도):
  - **H1**: Python `sys.stdin.flush()` + `sys.stdin.buffer` reset 명시 추가 (TextIOWrapper buffer 강제 비움)
  - **H2**: `tcdrain(fd)` + `tcsetattr` 직후 추가 호출 (output queue drain 보장)
  - **H3**: `prompt_end_or_iterate` 호출 직전 100ms sleep + flush_stdin 강화 (listener thread 잔여 활동 정리 시간)
  - **H4**: listener `__exit__`에서 self.fd dup → close (원본 fd 보존하면서 listener 측 read 차단)
  - **H5**: TRIGGER_BYTE 변경 (0x06 → 0x14 Ctrl+T 등 — readline lib 매핑 충돌 회피)

## 3. 출력

### 3.1 Cycle 진행 narrative (본 phase 본문 누적 기록)

각 cycle 결과를 본 §3.1에 추가 — Phase C/D narrative 결정 근거:

```
Cycle 1: H? 적용 → 사용자 시연 결과 (race 재현률 N/M) → 결정 (해소/추가 시도)
Cycle 2: H? 적용 → ...
...
Cycle 5: 도달 시 Phase C 정공법 강제 진입 narrative
```

본 §3.1은 Phase B 진행 중 누적 갱신 — 사용자 시연 결과 받을 때마다 1줄 추가.

### 3.2 가설 fix 시도 — `src/ui.py` (cycle별 **revert**, 누적 X)

각 cycle (단일 결정 — base 코드 일관성):
1. 1 가설 적용 (1-5 LOC fix) — base는 plan 011 commit `2c2bc2a` (`master` HEAD)
2. `pytest -q tests/test_listener_race_pty.py + 회귀` 자동 검증
3. 사용자에게 수동 시연 요청: `./.venv/bin/python tools/repro_listener.py --turns 3` + Ctrl+F + 'y'/한글 입력 → **race 재현률 보고 (시연 5회 중 N회 발생)**
4. race 0 (5회 중 0회) → 채택 (Phase C·D 진행) / race 잔존 (5회 중 ≥1회) → **`git checkout HEAD -- src/ui.py`로 revert + 다음 가설 진입** (untracked harness `tools/repro_listener.py` + `tests/test_listener_race_pty.py`는 stash 무관 — Phase A 산출 그대로 보존)

### 3.3 가설 fix 시도 narrative — `docs/dev-docs/validation.md` C-015 갱신

C-015 §"시도된 fix" 표는 hot fix 차수 통일 (1차/2차/3차/3차+ — 1.5차 표기 폐기, plan 015 신규 차수는 4차부터). 각 cycle 끝에 행 추가:

```markdown
| 차수 | 가설 | 적용 위치 | 효과 |
|---|---|---|---|
| 4차 (Cycle 1) | H1 (TextIOWrapper buffer reset) | src/ui.py:NNN | race 재현률 N/5 |
| 4차 (Cycle 2) | H2 (tcdrain) | src/ui.py:NNN | race 재현률 N/5 |
| ... | ... | ... | ... |
```

**기존 C-015 §"시도된 fix" 표 (plan 011 commit `2c2bc2a` 산출) 차수 통일 갱신**:
- "1차" `TCSADRAIN → TCSAFLUSH` 유지
- "1.5차" `input() → sys.stdin.readline()` → **"2차"로 재명명**
- "2차" `sys.stdin.readline() → os.read(fd, 4096)` → **"3차"로 재명명**
- "2차+" `listener __exit__ join 강화` → **"3차+"로 재명명**
- 본 plan 015 cycle 1-5 산출은 4차+ (Phase D R-NNN 환원 narrative 정합)

## 4. 작업 단위

- [ ] **Cycle 1**: H1 (TextIOWrapper buffer reset) 가설 1줄 fix → 자동 회귀 + 사용자 시연 → 결과 narrative 기록 → 결정
- [ ] **Cycle 2** (race 잔존 시): H2 (tcdrain) 적용 → 동일 검증
- [ ] **Cycle 3** (race 잔존 시): H3 (sleep + flush_stdin 강화) 적용 → 동일 검증
- [ ] **Cycle 4** (race 잔존 시): H4 (fd dup/close) 적용 → 동일 검증
- [ ] **Cycle 5** (race 잔존 시): H5 (TRIGGER_BYTE 변경) 적용 → 동일 검증
- [ ] cycle별 결과 §3.1 narrative 누적 + validation.md C-015 §시도된 fix 표 갱신
- [ ] race 0 도달 시 → 채택 narrative + Phase C 진입 결정 (혹은 본 cycle 가설을 정공법으로 승격)
- [ ] 5회 도달 + race 잔존 시 → Phase C 정공법 메커니즘 강제 진입 (가설 fix 포기, listener 메커니즘 자체 변경)

## 5. 검증

- 각 cycle 끝 `pytest -q` 회귀 0 (특히 `tests/test_trigger_listener.py` 5개 + `tests/test_prompt_end_or_iterate.py` 12개 + `tests/test_listener_race_pty.py` Phase A 산출)
- 사용자 시연: `tools/repro_listener.py --turns 3` 실행 → Ctrl+F → prompt → 'y' 또는 한글 입력 → race 재현률 보고 (10회 시연 중 N회 발생, race 0 또는 race 정량)
- harness 자동 재현 (pytest pty) — race 0 통과 또는 fail narrative 기록

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **사용자 시연 비용 (사용자 시간)**
   - 매 cycle 사용자에게 수동 시연 요청 — UX 부담 ↑
   - 차단: cycle 1당 최소 1회 + 최대 3회 시연 (race 재현률 통계 충분)
   - 사용자가 "시연 못 함" 보고 시 → harness 자동 재현만으로 결정 (덜 정확)

2. **가설 fix base 일관성 — revert 정책 (단일 결정)**
   - cycle별 가설을 누적 적용하지 않고 **1 가설씩 시도 + revert**
   - 채택된 가설만 최종 commit (Phase C 산출)
   - 차단: cycle 시작 시 base = `master` HEAD (plan 011 commit `2c2bc2a`) — 가설 적용 → 검증 → revert는 `git checkout HEAD -- src/ui.py` (untracked harness `tools/`/`tests/test_listener_race_pty.py`는 영향 X). **git stash 사용 X — untracked harness 일관성 보존**

3. **harness 자동 재현 vs 사용자 수동 시연 결과 불일치**
   - harness는 race 0이지만 사용자 환경에서 race 재현
   - 또는 그 반대 (사용자 환경 race 0이지만 harness fail)
   - 차단: 양쪽 결과 모두 §3.1 narrative 기록 — 불일치 narrative도 가설 결정 input

4. **5 cycle 한계 도달 narrative**
   - race 5회 가설 fix 모두 실패 시 → Phase C 정공법 강제 진입
   - narrative: "1-5차 hot fix 모두 실패 — listener thread 메커니즘 자체가 race source. main thread polling 또는 alternative 메커니즘 정공법 필요"
   - validation.md C-015 → R-NNN 환원 input (광역 패턴 입증)

5. **가설 H1-H5가 모두 부적합 (다른 가설 발견)**
   - cycle 진행 중 새 가설 발견 시 H6/H7 추가 가능
   - 단 5 cycle 한계 유지 (무한 시도 방지)
