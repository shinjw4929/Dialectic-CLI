# Plan Writing Guide (계획 작성 가이드) — Dialectic-CLI

> 작업 plan을 작성할 때 따라야 할 형식. `create-plan` 스킬이 본 가이드를 참조하여 plan을 생성하고, `review-plan`이 본 가이드 기준으로 검토하며, `execute-plan`이 본 형식의 plan을 실행 가능한 형태로 해석.

---

## 1. plan의 위치·이름

- 디렉토리: `plan/<work-id>/<plan-name>.md`
- `<work-id>`: 작업 단위 ID (예: `001-codex-adapter`, `002-orchestrator-loop`)
- 파일이 1개면 그냥 `plan/<work-id>/plan.md`. 복잡한 작업은 여러 단계 plan을 한 폴더에.

---

## 2. plan 형식 — AS-IS / TO-BE

```markdown
# Plan · <작업명>

## 0. 메타

- 작업 ID: <work-id>
- 의도: <한 줄 요약>
- 관련 ADR / Q번호: <docs/dev-docs/architecture.md ADR-N or outline/README.md Q번호>
- 예상 영향 범위: <변경될 파일 목록 또는 범위>

## 1. AS-IS (현재 상태)

현재 코드/문서가 어떤 상태인지. 사실 기준 (의견·계획 X). 인용 근거 (파일·줄 번호) 명시.

예시:
- `src/agents/codex.py` 부재 — Codex 호출 어댑터 미구현.
- `docs/runtime-docs/protocol.md` §8에 어댑터 인터페이스 정의 있지만 실제 구현 없음.

## 2. TO-BE (목표 상태)

작업 완료 후 어떤 상태가 되어야 하는지. 검증 가능한 항목으로.

예시:
- `src/agents/codex.py` 작성 — `AgentRunner` Protocol 준수.
- 단위 테스트 `tests/test_codex.py` — 1턴 호출 OK + cwd 격리 검증.
- `docs/runtime-docs/protocol.md` §10 codex 호출 옵션 추가.

## 3. 단계 (Phase)

작업을 **병렬·직렬 가능한 Phase**로 분할. `execute-plan`이 Phase 단위로 subagent 분기 가능.

```
Phase 1 (직렬):  src/agents/base.py 작성 (다른 어댑터의 기반)
Phase 2 (병렬):  
  · src/agents/codex.py 작성
  · src/agents/claude.py 작성
  (둘은 base.py에만 의존, 서로 독립 → 병렬 가능)
Phase 3 (직렬):  tests/ 작성 + docs/runtime-docs/protocol.md 갱신
```

각 Phase는:
- **목표**: 완료 시 무엇이 되는지
- **입력**: 어떤 파일·정보가 필요한지
- **출력**: 어떤 파일이 변경·생성되는지
- **검증**: 어떻게 완료를 확인하는지 (e.g. `pytest tests/test_codex.py`)

## 4. 엣지케이스 / 위험

플랜 실행 중 부딪칠 가능한 함정. 반드시 1개 이상 명시.

예시:
- subprocess timeout 동작이 OS별로 다를 수 있음 — Linux 기준 검증 후 macOS 별도 확인 필요
- mock 어댑터의 raw stream 파싱이 실 호출과 미세 다를 수 있음 → tests/test_mock_equivalence.py로 사후 검증

## 5. 비기능 요구

- 성능·리소스 제약 (해당 시)
- 외부 의존성 추가 여부 (있으면 ADR 필요)
- 보안 고려사항 (있으면)

## 6. 완료 기준 (Definition of Done)

체크박스로:

- [ ] 코드 작성 + 단위 테스트 pass
- [ ] `sync-docs` 실행 후 누락 0
- [ ] `review-code` 실행 후 P0 결함 0
- [ ] `commit` 분류표 사용자 승인 + 순차 커밋
- [ ] (해당 시) ADR 추가 또는 Documentation-Checklist 매핑 추가
```

---

## 3. AS-IS / TO-BE 형식의 가치

- **검증 가능**: TO-BE는 측정 가능한 상태 — "잘 동작" 같은 모호한 표현 X
- **diff 명확**: AS-IS와 TO-BE의 차이가 곧 작업 분량
- **review-plan이 검사하기 쉬움**: TO-BE 항목 하나하나가 검사 단위
- **execute-plan이 분할하기 쉬움**: Phase가 명시되어 있어 병렬 가능 부분 자동 식별

---

## 4. 안티패턴 (피할 것)

| 안티패턴 | 문제 | 대안 |
|---|---|---|
| AS-IS 없이 바로 TO-BE만 | 변경 분량 가늠 불가, 사용자가 현재 상태 모름 | 양쪽 다 적기 |
| Phase 없이 한 덩어리 | 병렬화 못 하고, 진행 추적도 어려움 | 최소 2-3 Phase로 분할 |
| 완료 기준 모호 ("잘 되면 끝") | review-plan이 무엇을 검사할지 모름 | 측정 가능한 체크박스 |
| 엣지케이스 0 | 발견 안 된 위험이 곧 미래 결함 | 반드시 1개 이상 |

---

## 5. plan 갱신

- plan 실행 중 발견된 변경(예: TO-BE 항목 하나가 실제로는 다른 방식이 더 합리적)은 plan 직접 수정
- 수정 시 commit message: "Update plan/<work-id>: <reason>"
- review-plan이 결함을 P0로 짚었으면 plan을 수정 후 다시 review-plan
- 자동 plan-edit 루프 X — 사용자 수동 fix가 원칙

---

> 본 가이드는 `create-plan` / `review-plan` / `execute-plan` 모두가 참조. 형식 변경 시 세 스킬 모두 영향 — Documentation-Checklist §1.4 따라 동기화.
