# Phase A · Decision Board — 002-interactive-default-convergence

## 0. 메타

- Phase ID: A
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: — (B·C가 본 Phase에 의존)
- 예상 LOC: ~30 (.md narrative)

## 1. 목표

Q6 = b 확정 라인, Q18 = critical 신설 라인, ADR-9 행을 SSOT(결정 보드 + ADR 표)에 추가. **Phase B·C는 본 Phase 결과 라인을 그대로 인용**해서 narrative 채움.

## 2. 입력

- `outline/README.md` 현 §6 결정 보드 (line 47-65, Q1~Q17)
- `docs/dev-docs/architecture.md` 현 §6 ADR 표 (line 122-137, ADR-1~ADR-8)
- 사전 검증된 사실:
  - Q6 = "🟡 a/b/c 셋 다 권고" 보류 상태 (`outline/README.md` line 53)
  - Q18 항목 부재 (`outline/README.md` line 47-65에 없음)
  - ADR-1 ~ ADR-8 8행 (`docs/dev-docs/architecture.md` line 128-135)

## 3. 출력

### 3.1 `outline/README.md` §6 변경

`line 53` 갱신 (Q6 보류 → 확정):
```
<!-- paste -->
✅ Q6  종료 조건 = b 우선 (reviewer [CONVERGED] 마커 + 연속 K=2턴 P0/P1=0 → 자동 e). 안전망: a (--max-turns), c (사용자 e/Ctrl-C). K는 --convergence-streak 조정.
```

`line 64` (Q17) 다음에 Q18 신설 라인 추가:
```
<!-- paste -->
✅ Q18 사용자 개입 default = critical (P0/P1 발견 시만 prompt, P2/0이면 자동 진행). --interactive {full,critical,end-only} 3단계 dial. Enter = iterate(빈 directive).
```

### 3.2 `docs/dev-docs/architecture.md` §6 변경

`line 135` (ADR-8) 다음에 ADR-9 행 추가:

```
<!-- paste -->
| **ADR-9** | 사용자 개입 default = `critical` + 연속 K=2턴 [CONVERGED] 자동 종료. **`--max-turns < --convergence-streak + 1`이면 K=1 자동 fallback + stderr 경고** | thesis "synthesis 생성자"는 개입 권한이지 빈도 아님. fix-induced regression은 K턴 streak로 차단. 경계 케이스(낮은 max-turns)는 fallback으로 처리 | 매 턴 강제 prompt — 피로감↑, 의미 있는 결정 희석 / K=1 단발 — fix 후 새 P0 도입 못 봄 / K=3+ — max-turns 소진, 종료 어려움 |
```

표 다음 line 137 ("각 ADR의 더 깊은 논의는 `outline/` 사고 흔적에...") 텍스트는 그대로 (ADR 9 추가만).

## 4. 작업 단위

> **anchor 원칙**: 줄 번호 직접 인용 X. grep 키워드 + 위치 한정자(직전/직후/단락 다음 등)로 위치 명시. .md 갱신 시 줄 번호 흔들림 차단.

- [ ] `outline/README.md` Q6 시작 라인(`grep "🟡 Q6"`) 전체를 §3.1 첫 블록(`✅ Q6 ...`)으로 교체
- [ ] `outline/README.md` Q17 라인(`grep "✅ Q17"`) 다음 줄, 결정 보드 코드 펜스 ` ``` ` 닫기 직전에 §3.1 둘째 블록(`✅ Q18 ...`) 삽입
- [ ] `outline/README.md` 첫 인용 단락(`grep "갱신: 2026"`) "Q1~Q17" 표현을 "Q1~Q18"로 + "Q1~Q3·Q5·Q7·Q9~Q17 결정 반영, Q4·Q6·Q8 보류"를 "Q1~Q3·Q5~Q7·Q9~Q18 결정 반영, Q4·Q8 보류"로 갱신 (Q6 확정 반영)
- [ ] `docs/dev-docs/architecture.md` §6 ADR 표의 ADR-8 행(`grep "ADR-8"`) 다음 행으로 §3.2 블록(ADR-9) 삽입
- [ ] `docs/dev-docs/architecture.md` §6 제목 라인(`grep "^## 6\. ADR"`)의 "8개"를 "9개"로 + 본문 첫 단락 "5분 안에 핵심 결정 훑기" 단락 안 "8개"가 있으면 "9개"로 (있는지 확인)
- [ ] `docs/dev-docs/Documentation-Checklist.md` **§1.7 (큰 결정·아키텍처 변경 매핑 표)**에 신규 행 3개 추가 (Q번호·ADR 동반 결정성 변경이므로 §1.2 런타임이 아니라 §1.7):
  - `"interactive default 변경 (Q18)"` → `outline/03-ux.md §3.1·§3.3, outline/02-communication.md §2.3, outline/04-requirements-and-modes.md §4.1·§4.5.1`
  - `"[CONVERGED] 마커 약속 (ADR-9)"` → `docs/runtime-docs/roles/{spec,plan}-reviewer.md, outline/02-communication.md §2.9, outline/01-harness-layers.md §1.4`
  - `"ADR 추가 (ADR-9)"` → `docs/dev-docs/architecture.md §6, outline/README.md §6`
  - 만약 §1.7이 부재하면 §1 마지막 하위 절로 신설 후 행 추가

## 5. 검증

- `grep -E "Q6|Q18" outline/README.md` 결과: ✅ 표시된 두 라인 정확히 출력
- `grep "ADR-9" docs/dev-docs/architecture.md` 결과: 1행 (표 안)
- `grep "결정 9개" docs/dev-docs/architecture.md` 결과: 1행 (제목 + 본문)
- 본 Phase 변경 후 `git diff --stat`: 2 파일 변경, ~30줄 추가/수정
- 후속 Phase B·C가 본 Phase 결과 라인을 그대로 인용 가능하도록 라인 식별자(`Q6`, `Q18`, `ADR-9`)가 grep 친화적

## 6. 엣지케이스 / 위험 (Phase 한정)

| 위험 | 차단 |
|---|---|
| Q1~Q17 표기 갱신 누락 (line 3 "갱신:" 주석에 Q1~Q17만 인용된 상태로 잔존) | line 3·5 같이 갱신 (위 §4 셋째 항목) |
| ADR-9 추가 시 ADR-8 거부 대안 칸과 정렬 차이로 표 깨짐 | markdown 표 행 길이 수동 검증 — 각 셀 trailing space 0 |
| Q18 라인 한 줄이 너무 김 → README 가독성↓ | 한 줄에 "default + 플래그명 + Enter 동작" 3 정보만. 상세는 outline/03-ux.md §3.3 (Phase B에서 채움) |
| 결정 보드 ✅/🟡 표시 일관성 | Q6 🟡 → ✅, Q18 처음부터 ✅. 다른 항목 손대지 않음 |
