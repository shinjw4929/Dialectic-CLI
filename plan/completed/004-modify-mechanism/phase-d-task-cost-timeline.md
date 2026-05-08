# Phase D · Task & Cost & Timeline — 004-modify-mechanism

## 0. 메타

- Phase ID: D
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: A (Q23 결정 텍스트 인용)
- 병렬 그룹: B-D 병렬 (C는 B 완료 후 직렬 진입)
- 예상 LOC: ~25 줄 추가 / ~12 줄 변경 (`outline/04-requirements-and-modes.md` + `outline/05-timeline.md` 2 파일, 후자에 날짜·요일 라벨 폐기 작업 포함)

## 1. 목표

`outline/04-requirements-and-modes.md` §4.3 데모 task 후보에 modify 전용 task 신규 추가(Q23=c). §4.6 비용 표에 patch apply 모듈 행 추가. `outline/05-timeline.md` Day 2 작업 항목에 `src/patch_apply.py` 추가 — search-replace 메커니즘 구현 작업이 일정에 명시되도록.

## 2. 입력

- AS-IS:
  - `outline/04-requirements-and-modes.md:27-43` §4.3 데모 task 후보 표 4행 + 결정 잠정 단락
  - `outline/04-requirements-and-modes.md:307-315` §4.6 모드별 구현 비용 정리 표 5행
  - `outline/05-timeline.md:67-80` §5.1 Day 2 상세 펼침 본문 (15 줄, 절대 날짜·요일 라벨 포함 — §4.3에서 폐기 대상)
  - `outline/05-timeline.md:170-180` §5.3 Day 2 작업 목록 9 항목 (26~34)
- Phase A 산출물: Q23 = c (modify 전용 task 신규 추가) 결정 텍스트
- 결정 사실:
  - modify task ID는 placeholder `<modify_task_id>` (실 ID는 별도 후속 plan에서 — buggy_rule_review 또는 wave_difficulty_v2 등 후보)
  - patch apply 모듈 = `src/patch_apply.py` (~30 LOC, 단계 1: 정규식 추출 + 단계 2: path/SEARCH 검증 + 단계 3: 트랜잭션 REPLACE)
  - Day 2 minimum cut에 영향: 어댑터 1개로 cut되어도 patch apply는 Day 3로 밀어도 OK (modify 시연은 Day 4 데모에서)

## 3. 출력

### 3.1 §4.3 후보 표 (line 27-34) 5번째 행 추가

기존 표:
```
| 후보 | 모드 적합성 | 장점 |
| wave_difficulty | ... | ... |
| reward_curve | ... | ... |
| buggy_rule_review | 일반 | ... |
| inventory_balance | 계획 → 구현 2단계 | ... |
```

→ 표 끝에 행 추가:
```markdown
# paste
| **`<modify_task_id>`** (예: `wave_difficulty_v2` 또는 `buggy_rule_review` 승격) — 기존 코드 수정 task | 일반 (run·implement) | search-replace 메커니즘(Q22 ✅) 시연. 신규 작성과 다른 시각 — driver가 기존 코드 읽고 변경 의도 표현, reviewer가 회귀 검증 |
```

### 3.2 §4.3 결정 단락 (line 36-43) 갱신

실제 줄 위치: line 36 = "**결정 (잠정)**:", line 37 = 1순위, line 38 = 2순위, line 39 = compare 모드 결합 행, line 41 = 최종 확정 시점, line 43 = Task 본문 톤.

기존 line 37-38:
```
- 1순위 task = `wave_difficulty` (Q4 = 잠정 결정). README 기본 데모, mock 녹음 자산도 이 task로 캡처.
- 2순위 task = `reward_curve` 또는 `buggy_rule_review` 1개. 시간 여유 시 `tasks/`에 추가.
```

→ 갱신 (line 37-38 두 줄을 다음 3 줄로 치환, line 39 compare 모드 행은 그대로 유지):
```markdown
# paste
- 1순위 task = `wave_difficulty` (Q4 = 잠정 결정, 신규 작성 시연). README 기본 데모, mock 녹음 자산도 이 task로 캡처.
- **2순위 task = modify 전용** (Q23 ✅ c). `buggy_rule_review` 승격 또는 `wave_difficulty_v2` 신규 — 기존 코드 수정 시연. tasks/<modify_task_id>/task.md 본문 작성은 별도 후속 plan.
- 3순위 task = `reward_curve` 또는 `inventory_balance`. 시간 여유 시 `tasks/`에 추가.
```

(치환 후 line 39 "compare 모드(§4.5.4)와 결합 — `wave_difficulty`로 두 매핑 비교 데모." 행은 4번째 항목으로 자연 이동, 의미상 그대로 유지.)

### 3.3 §4.6 비용 표 갱신 (line 307-313)

기존 표 끝(`mock` 행 직후)에 행 추가:
```markdown
# paste
| patch apply (search-replace) | `src/patch_apply.py` — 정규식 추출 + SEARCH 정확 일치 검색 + REPLACE 치환 + `kind=patch_applied` append (R2.6/R2.7 단계) | ~1.5시간 | Day 2 후반 (orchestrator turn loop 직후) |
```

표 직후 단락 갱신 (line 315):

기존:
```
→ Day 3 오전(~5시간)에 plan + implement + compare + mock 모두 처리 가능.
```

→ 갱신 (1줄 추가):
```markdown
# paste
→ Day 3 오전(~5시간)에 plan + implement + compare + mock 모두 처리 가능. patch apply는 Day 2 후반에 통합 — minimum cut 시 Day 3 오전으로 밀려도 modify 데모는 Day 4 풀 데모 시점에 시연 가능.
```

### 3.4 §5.1 Day 2 펼침 본문 갱신 (line 67-80)

line 76 ("`src/orchestrator.py` 최소 turn loop") 직후에 행 추가:
```markdown
# paste
  · src/patch_apply.py (~30 LOC) — search-replace 블록 정규식 추출 + 정확 일치 검색 + REPLACE 치환 + apply_status 반환 (Q22 ✅ A2)
```

line 80 commit 단위 행에 추가:
```markdown
# paste
  "Add JSONL bus + schema", "Add AgentRunner protocol + cwd isolation",
  "Implement codex/claude adapters", "Add search-replace patch apply", "Wire minimum turn loop"
```
(기존 4 commit 단위에 `"Add search-replace patch apply"` 1개 삽입)

### 3.5 §5.3 Day 2 작업 목록 갱신 (line 173-181)

line 179 (`src/orchestrator.py` 최소 turn loop) 직후에 항목 추가:
```markdown
# paste
33b. `src/patch_apply.py` — search-replace 블록 추출·적용 (Q22 ✅ A2). orchestrator R2(추출) + R2.6(apply) + R2.7(append patch_applied) 단계에서 호출
```

기존 33번이 turn loop, 33b를 그 직후에 둠. 후속 번호(34) 유지 — 환경 점검 함수.

또는 번호 재정렬: 33 = patch_apply, 34 = orchestrator turn loop, 35 = 환경 점검. 재정렬 시 line 174 (32) 이후 모든 번호 +1 — 변경 폭 큼. **권장: `33b` placeholder 사용으로 변경 최소화**.

## 4. 작업 단위

- [ ] `outline/04-requirements-and-modes.md` §4.3 후보 표 line 34 (inventory_balance 행 = 표 끝) 직후에 modify 전용 task 행 추가 (§3.1, 5번째 데이터 행이 됨)
- [ ] `outline/04-requirements-and-modes.md` §4.3 결정 단락 line 37-38 두 줄을 §3.2의 3 행으로 치환 (line 39 compare 모드 행은 그대로 유지)
- [ ] `outline/04-requirements-and-modes.md` §4.6 비용 표(line 313 직후)에 patch apply 행 추가 (§3.3)
- [ ] `outline/04-requirements-and-modes.md` §4.6 직후 단락(line 315)에 patch apply 통합 시점 1줄 추가
- [ ] `outline/05-timeline.md` §5.1 Day 2 펼침 본문(line 76 직후)에 `src/patch_apply.py` 행 추가 (§3.4)
- [ ] `outline/05-timeline.md` §5.1 commit 단위 목록에 `"Add search-replace patch apply"` 삽입
- [ ] `outline/05-timeline.md` §5.3 Day 2 작업 목록(line 179 직후)에 `33b` 항목 추가 (§3.5)

### 4.3 날짜·요일 라벨 폐기 (사용자 결정 — 절대 날짜 의존 패턴 자체가 잘못)
- [ ] `outline/05-timeline.md` line 1-2 머리: "평일(5/7 수, 5/8 목) 회사 후 ... 토요일(5/9 마감일) 종일" → "평일 회사 후 ~4.5h, 토요일(마감일) 종일" — 요일·날짜 표기 제거
- [ ] `outline/05-timeline.md` §5.1 mermaid gantt 블록(line 9-35) 전체 폐기 또는 일반 표로 대체 (gantt는 dateFormat 의존이라 절대 날짜 제거 시 기능 상실 — 단순 4 day breakdown 표 권장)
- [ ] `outline/05-timeline.md` §5.1 펼침 본문 헤더 4곳: `Day 1 (5/6 화 → 5/7 새벽, 23:30~02:30)`, `Day 2 (5/7 수, 회사 후 19:30+, ~4.5h 가용)`, `Day 3 (5/8 목, 회사 후 19:30+, ~4.5h 가용)`, `Day 4 (5/9 토, 마감일, 종일 가용)` → 모두 `Day N (가용 시간 ...)` 형태로 절대 날짜·요일 제거
- [ ] `outline/05-timeline.md` §5.3 Day 1~4 헤더에서 날짜·요일 표기 (있다면) 제거 — Day index만 유지
- [ ] `outline/05-timeline.md` 본문에 산재한 절대 날짜 (`2026-05-08`, `5/9 19시 마감` 등) 검토 후 절대 표기를 "마감일", "Day N" 같은 추상 표현으로 일괄 치환

## 5. 검증

- `grep -n "modify_task_id\|<modify" outline/04-requirements-and-modes.md` — §4.3 후보 표 + 결정 단락 양쪽에 등장
- `grep -n "patch apply\|patch_apply" outline/04-requirements-and-modes.md` — §4.6 표 + 단락
- `grep -n "patch_apply\.py" outline/05-timeline.md` — §5.1 Day 2 펼침 + §5.3 Day 2 목록 양쪽
- `grep -n "Q23" outline/04-requirements-and-modes.md` — §4.3 결정 단락에 등장 (Q23 ✅ c)
- 사람 검토: §4.3 modify task ↔ §4.6 patch apply 비용 ↔ §5 Day 2 일정 정합 (모두 Q22/Q23 ✅에 묶임)

## 6. 엣지케이스 / 위험 (Phase 한정)

- **task ID placeholder** — `<modify_task_id>`로 둔 이유: 실 task 본문(`tasks/<id>/task.md`)은 별도 후속 plan 스코프. outline에 실 ID 박으면 후속 plan 시점에 outline 재수정 필요. 후속 plan에서 ID 확정 시 outline의 placeholder 일괄 치환.
- **`buggy_rule_review` 후보 중복** — 기존 §4.3 표 3행에 `buggy_rule_review`가 이미 있음. modify 전용 task 행은 이를 "승격 또는 신규" 옵션으로 명시 — 후속 plan에서 둘 중 결정.
- **`33b` 번호 표기** — 기존 작업 목록은 26~34 순차. 33b는 markdown 번호 매김 흐름을 깬다. 가독성 vs 변경 최소화 트레이드오프 — 본 plan은 변경 최소화 채택. 후속 outline 정돈 plan에서 33→34→35 재번호 검토 가능.
- **Day 2 시한 압박 (`outline/05-timeline.md` 위험 #1 인용)** — patch apply 모듈 추가 시 Day 2 작업 단계가 1개 늘어남. minimum cut 정책 (어댑터 1개)에 patch apply도 포함 — Day 3로 밀려도 OK 명시. §3.3 단락에 이미 반영.
- **commit 단위 표기** — 기존 4 commit이 5 commit으로 늘어남. commit 스킬 호출 시 분류표가 자연스럽게 처리. 별도 위험 없음.
- **날짜·요일 폐기 영향** — outline/05-timeline.md §5.1 mermaid gantt가 dateFormat 의존이라 절대 날짜 제거 시 gantt 기능 상실. 옵션: (a) gantt 폐기 + 단순 표 대체, (b) gantt 유지하되 dateFormat 제거 후 추상 day index 사용. 본 plan은 (a) 기본 — execute-plan 시점에 사용자 재확인.
- **calendar mismatch 차단**: timeline의 절대 날짜·요일 표기가 외부 calendar와 어긋날 risk가 본 폐기 작업의 핵심 동기. 사용자 feedback `feedback_no_dates_in_plan.md`(plan 작성 시 절대 날짜 금지)와 정합 — outline도 동일 정책 적용.
