# Phase C · Runtime Role Self-checks — 002-interactive-default-convergence

## 0. 메타

- Phase ID: C
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: A (ADR-9 + Q18 결정 인용)
- 병렬 그룹: B (Phase B와 동시 실행 가능)
- 예상 LOC: ~25 (.md narrative, 2 파일 분산)

## 1. 목표

reviewer 4 role 중 spec-reviewer / plan-reviewer 2 ROLE에 **`[CONVERGED]` 출력 약속** + **fix-induced regression 검사 셀프체크**를 추가. driver(implementer/planner) ROLE은 본 변경 무관 (검증은 reviewer 단독 책임).

## 2. 입력

- Phase A 산출:
  - `docs/dev-docs/architecture.md` ADR-9 (interactive critical + K턴 수렴 종료)
  - `outline/README.md` Q6 ✅ b, Q18 ✅ critical
- 현 ROLE 본문 위치:
  - `docs/runtime-docs/roles/spec-reviewer.md` 출력 형식 (line 36-63), 셀프체크 (line 69-78)
  - `docs/runtime-docs/roles/plan-reviewer.md` 출력 형식 (line 36-69), 셀프체크 (line 75-85)
- 참조 cross-check 대상:
  - `docs/runtime-docs/protocol.md` 4섹션 prompt 정의 (수정 필요 여부 검증, 본 plan 스코프상 필요 없음 예상)
  - `outline/01-harness-layers.md` §1.4 4 role 셀프체크 동기화 (Phase C 끝에 점검)

## 3. 출력

### 3.1 `docs/runtime-docs/roles/spec-reviewer.md` 변경

#### 3.1.1 출력 형식 — `[CONVERGED]` 마커 약속

`line 36-63` 출력 형식 마지막 (line 63 "전체 1500자 이내" 직전, line 62 다음)에 한 단락 추가:

```markdown
<!-- paste -->
## 수렴 마커 (P0/P1 = 0일 때만 출력)

P0와 P1 섹션이 모두 비어 있으면 (P2 또는 Cross-vendor만 있어도 OK) 응답 **마지막 줄에 `[CONVERGED]` 단독 출력**. orchestrator가 이를 감지해 수렴 카운터에 반영 (ADR-9, `outline/02-communication.md` §2.9 참조).

P0 또는 P1이 1개 이상이면 마커 출력 X. 본문 인용에 `[CONVERGED]` 문자열을 우연히 쓰지 말 것 — 정규식 `^\[CONVERGED\]$` (단독 한 줄)로 매칭됨.
```

#### 3.1.2 셀프체크 항목 추가

`line 69-78` 셀프체크 리스트 (line 76 "1500자 이내인가" 직전)에 2 항목 추가:

```markdown
<!-- paste -->
- [ ] **regression 검사**: 직전 턴 driver의 fix가 새 P0/P1을 도입했는지 명시 검증 (HISTORY 마지막 driver proposal과 그 이전 proposal의 diff 시각으로). 새 결함 발견 시 P0 또는 P1로 보고.
- [ ] **수렴 마커**: P0/P1 모두 0이면 응답 마지막 줄에 `[CONVERGED]` 단독 출력. P0 또는 P1 ≥ 1이면 마커 출력 X.
```

### 3.2 `docs/runtime-docs/roles/plan-reviewer.md` 변경

#### 3.2.1 출력 형식 — `[CONVERGED]` 마커 약속

`line 36-69` 출력 형식 마지막 (line 71 "전체 1500자 이내" 직전, line 70 다음)에 같은 단락 추가:

```markdown
<!-- paste -->
## 수렴 마커 (P0/P1 = 0일 때만 출력)

P0와 P1 섹션이 모두 비어 있으면 (P2 또는 빠진 엣지케이스만 있어도 OK) 응답 **마지막 줄에 `[CONVERGED]` 단독 출력**. orchestrator가 이를 감지해 수렴 카운터에 반영 (ADR-9 참조).

plan 모드의 [CONVERGED] 의미: **spec.md가 implement 모드에 넘길 만큼 정교화됨**. 사용자가 e 누르거나 K턴 streak 도달 시 이 spec이 implement 모드 입력.
```

#### 3.2.2 셀프체크 항목 추가

`line 75-85` 셀프체크 리스트 (line 83 "1500자 이내인가" 직전)에 2 항목 추가:

```markdown
<!-- paste -->
- [ ] **regression 검사**: 직전 턴 planner의 spec 수정이 새 P0/P1(명세 부재 / 부족)을 도입했는지 검증. 새 모순·시그니처 변경으로 인한 엣지케이스 누락 짚기.
- [ ] **수렴 마커**: P0/P1 모두 0이면 응답 마지막 줄에 `[CONVERGED]` 단독 출력.
```

## 4. 작업 단위

> **anchor 원칙**: 줄 번호 직접 인용 X. grep 키워드 + 위치 한정자로 위치 명시.

- [ ] `docs/runtime-docs/roles/spec-reviewer.md` 출력 형식 코드 블록(```` ``` ````) 종료 직후, 다음 H2 헤더("## 응답 전 셀프체크") 직전에 `## 수렴 마커` 절 신설 (§3.1.1 본문)
- [ ] `docs/runtime-docs/roles/spec-reviewer.md` 셀프체크 리스트에서 "1500자 이내인가" 항목 직전에 regression 항목 + 수렴 마커 항목 2개 삽입 (§3.1.2)
- [ ] `docs/runtime-docs/roles/plan-reviewer.md` 동일 위치 패턴: 출력 형식 코드 블록 종료 직후·다음 H2 직전에 `## 수렴 마커` 절 신설 (§3.2.1 본문)
- [ ] `docs/runtime-docs/roles/plan-reviewer.md` 셀프체크 리스트의 "1500자 이내인가" 항목 직전에 regression 항목 + 수렴 마커 항목 2개 삽입 (§3.2.2)
- [ ] `docs/runtime-docs/roles/plan-reviewer.md` "P 라벨 적용 원칙" 표(`grep "## P 라벨 적용 원칙"`)의 P1 행 **의미 cell 끝**(`grep "P1.*명세 부족"` 행, 두 번째 cell)에 한 문장 추가: `"빠진 엣지케이스 1개+ 발견 시 P1로 분류"`. 표 cell 안 inline 추가 (별도 행·표 다음 단락 X). [CONVERGED] 마커 조건과 일관 (P0/P1=0 → 빠진 엣지케이스도 0)
- [ ] `outline/01-harness-layers.md` §1.4 spec-reviewer 셀프체크(grep "spec-reviewer.md") 부근에 regression + 수렴 마커 2 항목 추가
- [ ] `outline/01-harness-layers.md` §1.4 plan-reviewer 셀프체크(grep "plan-reviewer.md") 부근에 동일 2 항목 추가
- [ ] `docs/runtime-docs/protocol.md` 4섹션 prompt 정의에 `[CONVERGED]` 마커 출력 약속 인용 (해당 위치 검토 후 필요 시만)

## 5. 검증

- `grep -n "CONVERGED" docs/runtime-docs/roles/spec-reviewer.md docs/runtime-docs/roles/plan-reviewer.md`: 각 파일 ≥ 2행 (출력 형식 절 + 셀프체크)
- `grep -n "regression" docs/runtime-docs/roles/spec-reviewer.md docs/runtime-docs/roles/plan-reviewer.md`: 각 파일 ≥ 1행 (셀프체크)
- 셀프체크 항목 count: spec-reviewer.md `line 69-78` 직전 6 항목 → 8 항목, plan-reviewer.md `line 75-85` 직전 7 항목 → 9 항목
- `outline/01-harness-layers.md` §1.4 spec-reviewer 셀프체크 표시 항목 수가 위 변경과 일치
- 정규식 약속 일관: 두 파일 모두 `^\[CONVERGED\]$` (단독 한 줄) 표현 사용

## 6. 엣지케이스 / 위험 (Phase 한정)

| 위험 | 차단 |
|---|---|
| ROLE이 `[CONVERGED]`를 P2 섹션 바로 다음에 출력 vs 응답 마지막 줄? | "응답 **마지막 줄에** 단독 출력" 명시. P2 섹션이 마지막이면 P2 다음 빈 줄 후 마커 |
| reviewer가 1500자 한도에 마커 못 끼움 | 마커는 12 byte ([CONVERGED]) — 무시 가능. 셀프체크에 "한도 안에 마커 포함" 명시 X (자명) |
| plan-reviewer "빠진 엣지케이스" 별도 섹션과 [CONVERGED] 조건 모호 | §4 작업 단위에 "P 라벨 적용 원칙 표 P1 행에 '빠진 엣지케이스 ≥1개면 P1' 한 줄 보강" 명시 (검토 → 실행 격상, Patch 7) |
| 기존 mock 녹음(현 시점에 없음, Day 4 작성 예정)이 [CONVERGED] 마커 미포함 → critical/auto-end 모드에서 종료 안 됨 | 본 plan 시점에는 mock recordings 부재라 영향 없음. Day 4 녹음 시 본 phase의 갱신된 ROLE이 자동 적용되어 마커 포함. 후속 mock 녹음 작업의 의존 사항 명시 (Patch 2) |
| regression 검사가 첫 턴(N=1)에는 적용 불가 (직전 턴 부재) | 셀프체크에 "(N≥2일 때만)" 한정 표시 추가 |
| `outline/01-harness-layers.md` §1.4 동기화 누락 | 작업 단위 7번 명시. 본 Phase 종료 시 grep 검증 |
| `docs/runtime-docs/protocol.md`에 마커 약속 인용 누락 | 작업 단위 8번 — 검토 후 필요 시만. 현 protocol.md는 4섹션 prompt 형식만 정의했을 가능성 높음, 마커는 출력 형식이라 ROLE.md만으로 충분할 수도 |
