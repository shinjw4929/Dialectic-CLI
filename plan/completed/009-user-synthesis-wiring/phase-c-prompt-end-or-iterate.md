# Phase C · prompt_end_or_iterate — 009-user-synthesis-wiring

## 0. 메타

- Phase ID: C
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A·B·C (의존성 0)
- 예상 LOC: ~25 LOC + 테스트 ~15 LOC

## 1. 목표

`src/ui.py`에 `prompt_end_or_iterate(turn_id: int, reason: str)` 함수 신설. critical 모드 매 턴 끝 잠재 prompt 시점 호출 — Y/n/directive 3 분기 + EOF/Ctrl+C 안전망. `prompt_decision`(full 모드용)과 분리 — Enter default 의미가 정반대. 라벨은 outline §3.2:216 SSOT `[User Synthesis · Turn {turn_id}]` 정합.

## 2. 입력

- `src/ui.py:59-108 prompt_decision` — 동일 모듈 ref. 단 default 의미 정반대 (`prompt_decision` Enter=`("i", None)` ↔ 본 함수 Enter=`("e", None)`)
- 호출자 (Phase D 산출): `src/orchestrator.py:run_session` critical 모드 매 턴 끝 (`with TriggerListener` 블록 종료 직후, canonical mode 회복 상태)
- 참조: `outline/03-ux.md` §3.2 line 216 — `[User Synthesis · Turn {turn_id}]` 라벨 SSOT

## 3. 출력

`src/ui.py` 추가 (`prompt_decision` 아래):

```python
# spec
def prompt_end_or_iterate(turn_id: int, reason: str) -> tuple[str, str | None]:
    """critical 모드 매 턴 끝 prompt — Y/n/text 3 분기.

    함수 이름 의미 정합 narrative:
      이름 `end_or_iterate`는 두 결과 (e=end / i=iterate) 강조.
      호출 시점은 critical 모드 매 턴 끝의 "잠재 prompt 시점" — Phase D
      orchestrator wiring에서 `should_prompt = trigger.is_set() OR converged_now
      OR last_turn_now` 셋 OR 분기. 따라서 "종료 직전"이 아니라 "사용자 결정
      잠재 시점"이 정확. 함수 이름은 결과 의미(end/iterate) 강조라 그대로.

    라벨: outline §3.2 line 216 SSOT 형식 — `[User Synthesis · Turn {turn_id}]`.
    이어서 reason 별도 라인 (`reason: <reason>`).

    reason 예:
        "Ctrl+F 트리거"
        "[CONVERGED] streak 2 도달"
        "max-turns 5 도달"

    분기:
        Enter / Y / y                → ("e", None)  사용자 만족 신호
        n / N                        → ("i", None)  directive 없이 1턴 추가
        그 외 텍스트                  → ("i", text) directive 주입
        EOFError / KeyboardInterrupt → ("e", None) CI·파이프 안전망

    `prompt_decision`과 분리 — Enter default 의미 정반대 (full 모드 = iterate vs
    critical 모드 잠재 prompt = end). 한 함수에 mode 분기 넣으면 default 의미 모호.

    호출 시점: orchestrator.run_session critical 모드, with TriggerListener 블록
    종료 (cleanup) 직후. canonical mode 회복 상태이므로 input() 정상 동작.

    호출자: orchestrator.run_session critical 모드 (Phase D wiring).
    """
    ...
```

`tests/test_prompt_end_or_iterate.py` 신규 (~15 LOC):
- Enter (`""`) → `("e", None)`
- `"Y"` / `"y"` → `("e", None)`
- `"n"` / `"N"` → `("i", None)`
- `"추가로 X 구현해줘"` → `("i", "추가로 X 구현해줘")`
- EOFError → `("e", None)`
- KeyboardInterrupt → `("e", None)`
- `[User Synthesis · Turn {turn_id}]` 라벨 stderr 출력 단언 (turn_id=3 케이스)
- reason 라벨 stderr 출력 단언

## 4. 작업 단위

- [ ] `src/ui.py`에 `prompt_end_or_iterate(turn_id, reason)` 함수 추가
- [ ] 라벨 stderr 출력 — `[User Synthesis · Turn {turn_id}]` 1줄 (outline §3.2:216 SSOT) + `reason: {reason}` 1줄 + `Enter/Y=종료, n=directive 없이 추가, 텍스트=directive 주입` 안내 1줄
- [ ] try/except `(EOFError, KeyboardInterrupt)` → `("e", None)`
- [ ] `raw.strip()` 후 분기 — 빈 문자열/`"y"`/`"Y"` → end (lower 비교), `"n"`/`"N"` → iterate, else → directive (원본 strip 결과 보존)
- [ ] `tests/test_prompt_end_or_iterate.py` 신규 ≥4 케이스 (Y/n/text/EOF + 라벨 stderr 단언)
- [ ] `pytest tests/test_prompt_end_or_iterate.py -q` pass

## 5. 검증

- `pytest tests/test_prompt_end_or_iterate.py -q` ≥4 케이스 pass
- monkeypatch input으로 Y/n/text/EOF 분기 단언
- `[User Synthesis · Turn 3]` 라벨이 stderr에 정확히 출력됐는지 capsys 단언 (outline SSOT 정합 회귀 보호)
- reason 문자열이 stderr에 정확히 포함됐는지 capsys 단언
- 기존 회귀 0 — `prompt_decision` 동작 변경 X

## 6. 엣지케이스 / 위험 (Phase 한정)

- 빈 입력 vs whitespace-only 입력: `raw.strip()` 후 빈 문자열이면 Enter 분기와 동일 처리
- 다국어 입력 (한글 directive): `input()` UTF-8 buffer 자연 처리. `cli.py:_readline_input` 패턴 ref 가능
- 대문자 'N' / 소문자 'y' 혼용: `raw.strip().lower()` 비교는 Y/n 두 분기에만 적용. 텍스트 분기는 원본 보존
- 사용자가 Y/n 외 단일 글자 입력 (예: `"e"`, `"x"`): "그 외 텍스트" 분기로 directive 주입 — 의도된 동작
- listener와 fd 충돌 가능성: 본 함수는 critical 모드 호출자(Phase D)가 `with TriggerListener` 블록 종료 직후 호출. listener thread 이미 join + tcsetattr 복원 완료라 canonical mode 회복 상태 — input() 정상 동작 (P-RAW 정합, R5)
- turn_id 인자 사유: outline §3.2:216 SSOT 라벨 형식 정합
- 함수 이름 의미 (P1-ζ): end/iterate 결과 강조 — "종료 직전 prompt"가 아닌 "잠재 prompt 시점" docstring narrative 강화
