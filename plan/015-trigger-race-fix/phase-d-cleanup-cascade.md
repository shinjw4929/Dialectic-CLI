# Phase D · cleanup + cascade docs + C-015 환원 — 015-trigger-race-fix

## 0. 메타

- Phase ID: D
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: C (정공법 메커니즘 적용 완료 + race 0 검증)
- 병렬 그룹: —
- 예상 LOC: ~30 (cascade docs narrative)

## 1. 목표

Phase C 채택 메커니즘을 docs SSOT cascade로 반영 + validation.md C-015 → R-NNN 환원 (3+회 hot fix 광역 패턴 입증) + plan 015 entry 갱신 + plan/completed/ 이동 준비.

## 2. 입력

- Phase C 산출 — 채택 메커니즘 narrative + 코드 변경 위치
- [`docs/dev-docs/systems/ui.md`](../../docs/dev-docs/systems/ui.md) TriggerListener 표 — cascade 대상
- [`docs/dev-docs/validation.md`](../../docs/dev-docs/validation.md) §3 C-015 + §4 P-id 표 — 환원 대상
- [`docs/dev-docs/Plans/upcoming-plans.md`](../../docs/dev-docs/Plans/upcoming-plans.md) — plan 015 entry 추가 대상
- [`docs/dev-docs/Documentation-Checklist.md`](../../docs/dev-docs/Documentation-Checklist.md) §1.1 src/ui.py 매핑 — sync-docs cascade 자동 catch
- (옵션) Phase A 산출 `tools/repro_listener.py` + `tests/test_listener_race_pty.py` — `tools/` 디렉토리 신설 시 Documentation-Checklist 매핑 추가 검토

## 3. 출력

### 3.1 `docs/dev-docs/systems/ui.md` TriggerListener 표 갱신

채택 메커니즘 narrative SSOT는 phase-c §3.2 (단일 결정 위치) — 본 phase는 그 narrative를 systems/ui.md 표 형식에 맞게 옮김. `# spec` 라벨 X (markdown 표 본문이라 paste/spec 무관 — narrative 단순 인용).

```markdown
TriggerListener 표 행 갱신 narrative (Phase C 채택 ① 반영):

| `TriggerListener()` | 클래스 (컨텍스트) | Ctrl+F (`0x06`, `TRIGGER_BYTE` 상수) raw mode listener.
  plan 015 채택 메커니즘 ① main thread polling + thread-safe Queue:
  - listener thread는 byte 절도 X — `os.read(fd, 1)` 결과를 `self._byte_queue.put_nowait()`로 전달
  - main thread `poll_trigger_byte()` helper가 `queue.get_nowait()`로 검사 + TRIGGER_BYTE 발견 시 `trigger.set`
  - `__exit__` 시 queue 잔존 byte 처리 narrative (forward to stdin 또는 폐기 — Phase C 결정 따름)
  - cleanup-restart 패턴 유지 (매 turn 새 인스턴스). plan 011 hot-fix history 누적 (TCSAFLUSH + _read_line_for_prompt + join 강화)는 보존
  | critical 모드 turn loop wrap | P-RAW + plan 009/011/015 hot-fix history. validation.md C-015 → R-NNN 환원 |
```

### 3.2 `docs/dev-docs/validation.md` C-015 → R-NNN 환원

```markdown
# spec
## §2 R-NNN: TriggerListener race 정공법 fix (P-RAW 환원)

- **계층**: Knowledge / Validation
- **도메인**: 안전성 — listener thread + readline race 광역 패턴 환원
- **근거**: C-015 4+회 hot fix 누적 (1차/2차/3차/3차+ 모두 race 잔존, plan 015 차수 통일 후) + plan 015
  Phase B 5 cycle 가설 시도 narrative + Phase C 채택 메커니즘 narrative
- **규칙**: TriggerListener는 listener thread + thread-safe `queue.Queue` 패턴으로
  byte 절도 0 보장 (Phase C §3.2 채택 ①, plan 015 산출). 직접 `os.read` byte 절도
  + main thread readline 동시 점유 패턴 금지 — race source. cleanup 시 queue 잔존
  byte는 폐기 (forward 시 0x06이 readline prefix로 누수).
- **review-code 검사 항목 추가**: src/ui.py에서 listener thread + os.read fd 패턴 등장 시
  R-NNN 위반 → P0
```

### 3.3 `docs/dev-docs/Plans/upcoming-plans.md` plan 015 entry

```markdown
# spec
## plan 015-trigger-race-fix (✓ completed → `plan/completed/015-trigger-race-fix/`)

### 의도

Bug 1 (TriggerListener __exit__ → prompt readline byte 절도 race, validation.md
C-015) 정공법 fix. 에이전트 응답 생략 reproduction harness 구축 + 사용자 반복 시연
cycle.

### Phase 분할

A · repro harness (자동 pytest pty + 수동 standalone) → B · 가설 검증 + 반복 cycle
(5회 한계) → C · 정공법 메커니즘 채택 (4 후보 중 1) → D · cleanup + cascade.

### 채택 메커니즘

(Phase C 산출 narrative — 예: ① main thread polling)

### 후행 영향

- plan 007 mock 어댑터 진입 시 채택 메커니즘과 호환 narrative 추가
```

또한 mermaid 의존 그래프에 P015 노드 추가 (P011 → P015 의존):

```mermaid
# spec
P011[plan 011<br/>menu-expansion<br/>completed]
P015[plan 015<br/>trigger-race-fix<br/>completed]
P011 --> P015
```

### 3.4 plan/015 → plan/completed/ 이동 준비

- mv plan/015-trigger-race-fix → plan/completed/015-trigger-race-fix
- commit 스킬 호출 시 분류 (cleanup commit + plan/015 archive commit 분리)

### 3.5 `tools/` 디렉토리 sync-docs 매핑 (필수, phase-d 단일 책임)

- Phase A 산출 `tools/repro_listener.py`가 `tools/` 신규 디렉토리 신설 → Documentation-Checklist.md §1 매핑 행 추가 (phase-a §6 위험 4 narrative 단일 책임 위치 확정)
- 추가할 매핑: `tools/repro_listener.py | (테스트 도구, src/ui.py:TriggerListener 변경 시 시연 검증) | docs/dev-docs/systems/ui.md TriggerListener 표 narrative` (sync-docs 자동 catch 대상)
- §1.X 행 위치 결정 — §1.5 (task·녹음 인접) 또는 §1.6 (인프라·배포) 인접 — 도메인상 §1.5 후보. 단일 결정 narrative

## 4. 작업 단위

- [ ] systems/ui.md TriggerListener 표 행 + narrative 갱신 (Phase C 채택 메커니즘 반영)
- [ ] validation.md §2 R-NNN 신규 추가 + §3 C-015 → "R-NNN으로 환원 (2026-MM-DD)" status update
- [ ] validation.md §4.4 P-id 표에 R-NNN 매핑 갱신
- [ ] upcoming-plans.md plan 015 entry 추가 + mermaid P015 노드 + plan 011 → P015 의존 화살표
- [ ] (옵션) Documentation-Checklist.md §1.X `tools/` 디렉토리 매핑 추가
- [ ] sync-docs 호출 → SYNC_DOCS_STATUS: OK 확인
- [ ] plan/015 → plan/completed/ 이동 (commit 스킬 분류)

## 5. 검증

- `pytest -q` 전체 회귀 0 (Phase C 적용 후 누적)
- sync-docs 호출 결과 SYNC_DOCS_STATUS: OK
- `docs/dev-docs/systems/ui.md` TriggerListener 행이 채택 메커니즘 narrative 정확 반영
- `docs/dev-docs/validation.md` C-015 status가 "R-NNN 환원 완료" 표기
- `docs/dev-docs/Plans/upcoming-plans.md` plan 015 entry + mermaid P015 노드 등장
- plan/completed/015-trigger-race-fix/ 디렉토리 존재 (mv 완료)
- commit 분류 (Phase D 산출은 보통 2 commit: docs cascade + archive plan)

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **C-015 → R-NNN 환원 임계 (3회 vs 5회)**
   - validation.md §3 C-015는 3차 hot fix 누적으로 이미 R-NNN 환원 후보
   - Phase B 5 cycle 추가 시도 시 8+ hot fix 누적 → R-NNN 환원 강하게 정합
   - 차단: Phase D narrative에 "총 N회 시도 후 메커니즘 변경 정공법" 명시

2. **review-code-checklist.md 항목 추가 (R-NNN 자동 catch)**
   - validation.md R-NNN 환원 시 review-code-checklist.md §1 안전성 P0 행에 검사 항목 추가 권고
   - 본 plan 015 외 — sync-docs 자체 cascade (validation.md → review-code-checklist.md 매핑 §1.3 정합)

3. **upcoming-plans.md mermaid 노드 위치**
   - P015 노드 추가 시 다른 plan(P010/P012/P013/P014) 의존 화살표와 충돌 X 검증
   - 차단: mermaid 렌더링 검증 (GitHub preview 또는 mermaid live editor)

4. **`tools/` 디렉토리 매핑 sync-docs 누락 (옵션)**
   - 본 plan은 옵션으로 분류 — sync-docs가 신규 매핑 필요 보고 시 사용자 결정
   - 차단: Phase D §3.5 옵션 narrative 유지

5. **Phase D 진입 후 Phase C 산출 회귀 발견**
   - 매우 드문 케이스 — Phase D 검증 단계에서 race 재현 시 Phase B 재진입
   - 차단: Phase D §5 검증을 Phase C와 분리 (cascade docs commit 전 race 검증 한 번 더)
