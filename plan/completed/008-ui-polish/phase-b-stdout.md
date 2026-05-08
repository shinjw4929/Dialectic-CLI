# Phase B · 호출 결과 stdout 출력 — 008-ui-polish

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: A (`Spinner` wrapping wiring 완료 — 본 phase는 spinner 종료 직후에 print_message 추가)
- 병렬 그룹: A·B 직렬, C 독립 병렬
- 예상 LOC: ~40 (코드: ui.py ANSI 상수 5 + KIND_COLOR + SEPARATOR + TYPE_CHECKING import + print_message 본문 ~25 / orchestrator.py proposal·critique append 직후 print_message 호출 2개 ~15) + ~25 (테스트 3 케이스)

## 1. 목표

본 Phase 종료 시 `src/orchestrator.py:run_turn`의 proposal append (`:371`) + critique append (`:427`) 직후 `src/ui.py:print_message`로 stdout 출력. outline/03-ux §3.2 line 195-225 narrative SSOT 1:1 형식 (구분선 + 헤더 + 본문 + 구분선) + §3.5 line 362 ANSI 색상 (proposal=cyan, critique=yellow).

## 2. 입력

### 2.1 의존 Phase 산출물

- Phase A 산출: `src/orchestrator.py:run_turn`의 driver/reviewer 호출이 `with Spinner(...)` 컨텍스트로 wrapping. 본 phase는 컨텍스트 종료 직후 `bus.append(proposal)` / `bus.append(critique)` 다음 라인에 `print_message(...)` 호출 추가
- Phase A 산출: `src/ui.py:VENDOR_LABEL` / `ROLE_LABEL_KO` paste dict — 본 phase에서 그대로 활용

### 2.2 참조 .md (줄 번호까지)

- `outline/03-ux.md` §3.2 (`:193-201`) — 종료 1줄 + 본문 + 구분선 형식 SSOT
- `outline/03-ux.md` §3.2 (`:204-225`) — reviewer critique 출력 narrative
- `outline/03-ux.md` §3.5 (`:362`) — ANSI 색상 SSOT (proposal=cyan, critique=yellow, decision=green, error=red)
- `docs/dev-docs/code-conventions.md` §2 (외부 의존성 0)
- `src/schema.py:19-39` — `Meta` 필드 (`latency_ms`, `output_tokens`, `input_tokens`, `cost_usd`)
- `plan/008-ui-polish/01-plan.md §2.2`, §5-1, §5-2

### 2.3 사전 검증된 사실

- `Meta.latency_ms` int (필수) / `output_tokens` int / `input_tokens` int / `cost_usd` float | None — `print_message` 헤더 1줄에 사용
- `Meta` 필드는 frozen — 본 phase는 읽기만 (변경 X). `dataclasses.replace` 패턴 미사용
- 본 phase에서 출력 대상은 driver의 `proposal_meta` (resp1.meta + patches replace) + reviewer의 `critique_meta` (resp2.meta + convergence_streak replace) 둘 다. 이미 orchestrator.py에서 `dataclasses.replace`로 새 Meta 생성 후 메시지에 부여 — print_message는 해당 Meta 그대로 받음

## 3. 출력

### 3.1 `src/ui.py` 보강 (~25 LOC)

```python
# paste
ANSI_CYAN = "\x1b[36m"
ANSI_YELLOW = "\x1b[33m"
ANSI_GREEN = "\x1b[32m"
ANSI_RED = "\x1b[31m"
ANSI_RESET = "\x1b[0m"

KIND_COLOR = {
    "proposal": ANSI_CYAN,
    "critique": ANSI_YELLOW,
    "decision": ANSI_GREEN,
    "error":    ANSI_RED,
}

# outline/03-ux §3.2 line 193·201·205 구분선 — 65 chars `─`
SEPARATOR = "─" * 65
```

```python
# paste
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .schema import Meta
```

```python
# spec
def print_message(
    *,
    role_label: str,
    vendor_label: str,
    kind: str,
    text: str,
    meta: "Meta",
) -> None:
    """outline/03-ux §3.2 line 193-201 형식 1:1로 stdout 출력.

    형식:
        ─────────────────────────────────────────────────────────────────
        [{role_label}: {vendor_label}] ✓ {latency}s · {output_tokens} out / {input_tokens} in[· ${cost:.3f}]
        ─────────────────────────────────────────────────────────────────
        {text}
        ─────────────────────────────────────────────────────────────────

    - `latency` = meta.latency_ms / 1000.0, 소수점 1자리 (`{:.1f}`)
    - `cost` 표시는 `meta.cost_usd is not None` 시에만 ` · ${cost:.3f}` 부분 추가 (codex가 항상 None일 가능)
    - ANSI 색상: KIND_COLOR.get(kind, "") — 헤더 라인만 색상 (구분선·본문은 평문)
    - `sys.stdout.isatty()` False 시 ANSI 색상 모두 빈 문자열 치환 (capsys/CI 회귀 차단)
    - 출력 자체는 isatty 무관 항상 진행 (CI/pytest에서도 결과 인지 가능)
    """
```

### 3.2 `src/orchestrator.py:run_turn` 수정 (~15 LOC)

```python
# spec
# proposal append (`:371`) 직후
bus.append(proposal)
print_message(
    role_label=ROLE_LABEL_KO.get(driver_role, driver_role),
    vendor_label=VENDOR_LABEL.get(driver_runner.name, driver_runner.name),
    kind="proposal",
    text=resp1.text,
    meta=proposal_meta,
)

# critique append (`:427`) 직후
bus.append(critique)
print_message(
    role_label=ROLE_LABEL_KO.get(reviewer_role, reviewer_role),
    vendor_label=VENDOR_LABEL.get(reviewer_runner.name, reviewer_runner.name),
    kind="critique",
    text=resp2.text,
    meta=critique_meta,
)
```

import 추가: `from .ui import Spinner, VENDOR_LABEL, ROLE_LABEL_KO, print_message` (Phase A에 print_message만 추가 형태).

빈 응답·에러 분기는 본 phase 출력 X — 사용자에게는 stderr 1줄 (현재 `_error_msg`가 JSONL에 기록만, stderr 노출 0)만 후속 plan에서 보강. 본 phase는 정상 응답 분기에 한해 stdout 출력.

### 3.3 단위 테스트 (~25 LOC)

`tests/test_ui_print_message.py` (신규) ≥3 케이스.

```python
# spec
def test_print_message_proposal_cyan_with_isatty(monkeypatch, capsys):
    """isatty=True (monkeypatch sys.stdout.isatty=lambda:True) 환경에서
    kind=proposal 출력. capsys.readouterr().out에:
    - SEPARATOR 3회 (구분선 3줄)
    - role_label / vendor_label substring
    - ANSI_CYAN escape (`\x1b[36m`) substring
    - text 본문 substring
    """

def test_print_message_critique_yellow(monkeypatch, capsys):
    """kind=critique → ANSI_YELLOW (`\x1b[33m`) substring."""

def test_print_message_isatty_false_no_ansi(monkeypatch, capsys):
    """isatty=False 환경에서 ANSI escape 미포함 (`\x1b` substring 부재).
    출력 자체는 진행 — role_label / text 본문 모두 capsys에 포함."""
```

`Meta` 인스턴스는 `tests/test_schema.py` 기존 패턴 참조 (`SENTINEL_META` 또는 직접 `Meta(...)` 14 필드 채움).

## 4. 작업 단위

- [ ] `src/ui.py`에 ANSI 상수 5개 + `KIND_COLOR` dict + `SEPARATOR` 상수 paste
- [ ] `src/ui.py`에 `print_message(*, role_label, vendor_label, kind, text, meta) -> None` 신설 — keyword-only, isatty 가드, outline §3.2 형식 1:1
- [ ] `src/orchestrator.py` import에 `print_message` 추가 (Phase A의 import 라인에 합류)
- [ ] `run_turn` proposal append (`:371`) 직후 `print_message(...)` 호출 1줄 추가
- [ ] `run_turn` critique append (`:427`) 직후 `print_message(...)` 호출 1줄 추가
- [ ] `tests/test_ui_print_message.py` 신규 — ≥3 케이스 (proposal cyan / critique yellow / isatty=False no-ansi)
- [ ] `pytest tests/test_ui_print_message.py -q` ≥3 passed
- [ ] `pytest -q` 전체 회귀 0

## 5. 검증

- `pytest tests/test_ui_print_message.py -q` ≥3 passed
- `grep -n "print_message" src/orchestrator.py` 2건 단언 (proposal + critique)
- `grep -n "ANSI_CYAN\|ANSI_YELLOW\|KIND_COLOR\|SEPARATOR" src/ui.py` 정의 단언
- `python -c "from src.ui import print_message, KIND_COLOR; assert KIND_COLOR['proposal'].endswith('36m'); assert KIND_COLOR['critique'].endswith('33m')"` exit 0
- (수동) `dialectic run --task "test" --max-turns 1` 실행 — driver/reviewer 응답 정상 시 stdout에 구분선 + 헤더 + 본문 출력 (인증 부재 시 error 분기로 출력 0, 인증 성공 환경에서 수동 검증)

## 6. 엣지케이스 / 위험 (Phase 한정)

- **`meta.cost_usd is None`**: codex 어댑터(`src/agents/codex.py`)는 cost 이벤트 부재로 항상 None, claude 어댑터는 cost 보고. `meta.cost_usd is not None`일 때만 ` · ${cost:.3f}` 헤더에 추가 — 두 vendor 모두 형식 정합
- **ADR-10 patch 필드 출력 (`meta.patches`/`apply_status`/`apply_error`/`files_changed`)**: 본 phase 헤더는 `latency` + `output_tokens` + `input_tokens` + `cost_usd`만 표시 (outline §3.2:193 SSOT 1:1). `meta.patches` 등 ADR-10 4 필드는 `proposal.text` 본문에 search-replace 마커로 자연 포함 (`src/orchestrator.py:374-386`의 `_patch_applied_msg`는 별도 system 메시지로 bus에 append되지만 stdout 출력은 본 plan 범위 외 — 후속 plan에서 `kind=patch_applied` 출력 검토). 본 phase는 `kind in ("proposal", "critique")`만 처리
- **`output_tokens=0` 빈 응답**: 빈 응답은 orchestrator에서 error 분기 진입(`:350-362`, `:406-416`) — print_message 미호출. 정상 응답은 `text.strip() != ""` 보장 후 print_message 진입
- **`text` multi-line**: `text` 그대로 stdout write (개행 보존). outline §3.2:195-200 형식 1:1 — 구분선 사이에 본문이 multi-line으로 자연 출력
- **isatty=False 환경 (capsys/CI)**: ANSI 색상 빈 문자열 치환. 단위 테스트 `monkeypatch.setattr(sys.stdout, 'isatty', lambda: False)` 케이스 1개로 회귀 차단
- **`meta` 타입 import 순환**: `src/ui.py`가 `src/schema.py:Meta`를 직접 import하면 schema ↔ ui 양방향 의존 우려 (현 시점 schema → ui 부재로 무해하나, 향후 schema가 ui helper 호출 시 순환). 본 phase는 `from typing import TYPE_CHECKING; if TYPE_CHECKING: from .schema import Meta` + `meta: "Meta"` 문자열 어노테이션 채택 (PEP 484 forward reference). 런타임 import 0 + 정적 분석 시 타입 보존 — duck typing 단독보다 IDE/typecheck 명료성 ↑
- **R-001 P-ENCODING**: 본 phase는 stdout write만 사용 — `read_text`/`write_text`/`open()` 부재. vacuously OK. 신규 테스트 파일에 file I/O 추가 시 `encoding="utf-8"` 강제 (test 케이스 모두 capsys로 stdout 캡처라 file I/O 0)
- **frozen Meta 회귀**: 본 phase는 Meta 읽기만 (`meta.latency_ms` 등). `dataclasses.replace` 미사용. 회귀 0
- **JSONL append-only**: 본 phase는 stdout 출력만 추가. `bus.append` 호출 위치·횟수 변경 0 (proposal/critique append 라인은 그대로, 직후에 print_message 1줄 추가)
