# Phase A · CLI mode — 009-user-synthesis-wiring

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A·B·C (의존성 0, execute-plan 병렬 분기 후보)
- 예상 LOC: ~10 LOC + 테스트 ~15 LOC

## 1. 목표

`src/cli.py`의 `--interactive` argparse choices를 `["end-only","critical","full"]` 3종으로 확장하고, 메뉴 진입(`_interactive_menu_body`)의 default를 `"critical"`로 변경한다.

## 2. 입력

- `src/cli.py:74-77` — AS-IS `choices=["end-only"]` 단일값
- `src/cli.py:257-262` — AS-IS `Namespace(..., interactive="end-only")` 메뉴 고정 wiring
- 참조: `outline/03-ux.md` §3.1 (`:19-69`) — `--interactive` 강도 dial Q18 (Phase E §3.3에서 narrative 갱신)

## 3. 출력

- `src/cli.py:74-77` 변경 (~3 LOC):
  - `choices=["end-only","critical","full"]`
  - `default="end-only"` 유지 (CLI 직접 호출 시 자동 dialectic)
  - `help` narrative 갱신 — 3 mode 의미 1줄씩
- `src/cli.py:257-262` 변경 (~1 LOC):
  - `interactive="critical"` (메뉴 default 변경)
- `tests/test_cli_interactive_modes.py` 신규 (~15 LOC):
  - 3 mode argparse parsing 단언
  - default 값 단언 (`end-only`)
  - 메뉴 default critical 단언 (Namespace 빌더 격리)

## 4. 작업 단위

- [ ] `src/cli.py:74-77` `choices` 리스트 3 mode + help narrative 갱신
- [ ] `src/cli.py:257-262` Namespace `interactive` 값 `"critical"`
- [ ] `tests/test_cli_interactive_modes.py` 신규 (≥3 케이스)
- [ ] `pytest tests/test_cli_interactive_modes.py -q` pass

## 5. 검증

- `pytest tests/test_cli_interactive_modes.py -q` 신규 ≥3 케이스 pass — argparse parsing은 `parser.parse_args(["run","--task","x","--interactive","critical"])` 격리 호출로 단언 (실 codex/claude 호출 0)
- `python -c "from src.cli import main"` import 성공만 확인 (실행 X)
- 메뉴 default critical 단언: `_interactive_menu_body` 본문에서 `argparse.Namespace(...)` 빌더 부분만 추출해서 `.interactive == "critical"` 단언
- 기존 회귀 0 — `pytest -q` 전체

본 Phase는 실 codex/claude 호출 명령 사용 X (P0-2 fix). `from src.cli import main; main()`은 args.func 통해 실 호출 발생 — 격리 의도와 정반대.

## 6. 엣지케이스 / 위험 (Phase 한정)

- 잘못된 choices (`--interactive partial` 등): argparse 자동 차단 — 단언 단위 테스트 1개로 회귀 보호
- 메뉴 default 변경이 plan 008(미진행) 산출 `_interactive_menu_body` 본문과 충돌 시: plan 008이 추가 wiring(spinner·결과 출력)을 하더라도 Namespace 필드 변경은 독립 — 합쳐도 안전. 단 execute-plan 시 plan 008 head merge 후 진입 권고
- argparse `default` 값과 메뉴 wiring 값 불일치: CLI default=`end-only`, 메뉴 default=`critical` — 의도된 분기 (진입로별). 단 사용자가 `dialectic run` 인자 없이 호출 시 메뉴 진입 X (run subparser는 task 필수) → CLI default `end-only` 적용. 메뉴는 `dialectic`(서브커맨드 0) 진입 — 별도 경로
