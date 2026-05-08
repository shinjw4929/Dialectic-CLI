# Phase A · 호출 진행 spinner — 008-ui-polish

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A·B 직렬 (B가 본 산출 후 같은 함수 추가 wiring), C 독립 병렬
- 예상 LOC: ~40 (코드: ui.py paste dict 2개 ~10 + orchestrator import 1줄 + run_turn driver/reviewer with 블록 wrapping 각 ~13 = ~30) + ~20 (테스트 2 케이스)

## 1. 목표

본 Phase 종료 시 `src/orchestrator.py:run_turn`의 driver 호출(`:337`) + reviewer 호출(`:393`)이 `with Spinner(message)` 컨텍스트 매니저로 wrapping되어, isatty=True 환경에서 호출 동안 stderr에 회전 spinner + 동적 라벨 표시. isatty=False 환경 회귀 0.

## 2. 입력

### 2.1 의존 Phase 산출물

- (없음)

### 2.2 참조 .md (줄 번호까지)

- `outline/03-ux.md` §3.2 (`:190-194`) — spinner 메시지 형식 SSOT (`[구현자: Codex CLI] running... ⠋`)
- `outline/03-ux.md` §3.2 (`:240`) — 역할 라벨 모드별 변환 narrative
- `docs/dev-docs/code-conventions.md` §2 (외부 의존성 0), §3 (subprocess timeout 명시)
- `plan/008-ui-polish/01-plan.md §2.1`, §5-1, §5-3
- `plan/completed/006-ui/phase-a-ui.md §3.1` — Spinner 컨텍스트 매니저 명세 (정의 SSOT, 변경 X)

### 2.3 사전 검증된 사실

- `src/ui.py:Spinner` (`:82-124`) 존재 — `__enter__`/`__exit__` + isatty 가드 + thread.join 정리 보유 (plan 006 산출). 변경 X
- `src/orchestrator.py:33` `MODE_ROLES` dict 존재 — `roles["driver"]`/`roles["reviewer"]`로 영문 role 키 접근 가능
- `AgentRunner.vendor` 속성 (`src/agents/base.py`) — `"openai"`/`"anthropic"`/`"mock"`. UI 라벨용 vendor_label은 ui.py paste dict로 별도 매핑 (`{"codex": "Codex CLI", "claude": "Claude Code"}`)
- `AgentRunner.name` 속성 — `"codex"`/`"claude"`/`"mock"`. VENDOR_LABEL key로 적합

## 3. 출력

### 3.1 `src/ui.py` 보강 (Phase A 한정 — VENDOR_LABEL + ROLE_LABEL_KO만, ANSI/print_message는 Phase B)

```python
# paste
VENDOR_LABEL = {
    "codex": "Codex CLI",
    "claude": "Claude Code",
    "mock": "Mock",
}

ROLE_LABEL_KO = {
    "implementer":   "구현자",
    "spec-reviewer": "기획 검토자",
    "planner":       "계획자",
    "plan-reviewer": "계획 검토자",
}
```

### 3.2 `src/orchestrator.py:run_turn` 수정 (~30 LOC)

driver 호출(`:335-348`) + reviewer 호출(`:391-404`) 양쪽을 `with Spinner(...)` 컨텍스트로 wrapping. `from .ui import Spinner, VENDOR_LABEL, ROLE_LABEL_KO` import 추가.

```python
# spec
# driver 분기 — with Spinner 블록 boundary는 build_prompt + runner.run 한정 (호출 단위)
driver_label = ROLE_LABEL_KO.get(driver_role, driver_role)
driver_vendor = VENDOR_LABEL.get(driver_runner.name, driver_runner.name)
spinner_msg = f"[{driver_label}: {driver_vendor}] running..."
try:
    with Spinner(spinner_msg):
        p1 = build_prompt(driver_role, task, history, directive=None)
        resp1 = driver_runner.run(p1, raw_log_path=raw1, timeout_s=DEFAULT_TIMEOUT_S, workdir=workdir)
    # with 블록 종료 후 (Spinner __exit__로 stderr 라인 clear 완료 시점)에 빈 응답·meta 처리
except (
    subprocess.TimeoutExpired, json.JSONDecodeError, AgentAuthError,
    FileNotFoundError, OSError, UnicodeDecodeError, ValueError,
) as e:
    # except 진입 시에도 with __exit__ 호출 보장 (Python 언어 명세) — Spinner 자동 정리
    bus.append(_error_msg(...))  # 기존 except 본문 그대로
    return

# 빈 응답 가드 (`:350-362`) + proposal 메시지 build + bus.append + patches apply는
# with 블록 외부에 그대로 유지 (spinner 노이즈 차단 — 호출 자체만 30~50초 영역).
```

reviewer 분기도 동일 패턴 (`reviewer_role`, `reviewer_runner` 사용, `proposal.msg_id` parent_id).

**Boundary 결정 (작성자 판단 X, 본 plan 정본)**: `with Spinner(...):` 블록 boundary는 **`build_prompt + runner.run` 단위**로 한정. except 분기는 `try`에 두되 `with`은 **`try` 내부**에 위치 — except 진입 시 with __exit__가 먼저 호출되어 spinner stderr 정리 → bus.append(_error_msg) 실행 순서 보장 (spinner 잔여 frame ↔ 후속 출력 race 차단).

### 3.3 단위 테스트 (~20 LOC)

`tests/test_orchestrator_spinner.py` (신규) 또는 기존 `tests/test_orchestrator_*.py` 확장. 권장 — **신규 파일**로 격리.

```python
# spec
def test_run_turn_wraps_driver_call_with_spinner(monkeypatch, capsys, tmp_path):
    """run_turn이 driver runner.run을 Spinner 컨텍스트로 wrap.
    isatty=True monkeypatch 시 stderr에 spinner frame 1자 이상 출력 (회전 1프레임 캡처)."""

def test_run_turn_spinner_isatty_false_no_op(monkeypatch, capsys, tmp_path):
    """isatty=False 환경에서 stderr에 spinner frame 출력 0 (CI/pytest 회귀 차단).
    driver/reviewer 호출은 정상 진행 (mock runner 응답 메시지가 bus에 append되는지 단언)."""
```

mock runner는 `tests/test_orchestrator_*` 기존 패턴(직접 `class _MockRunner` 정의, `AgentRunner` Protocol 시그니처 따름) 활용.

## 4. 작업 단위

- [ ] `src/ui.py`에 `VENDOR_LABEL` dict + `ROLE_LABEL_KO` dict paste (Phase B에서 추가될 ANSI 상수·print_message는 본 phase 범위 외)
- [ ] `src/orchestrator.py` 상단 import에 `from .ui import Spinner, VENDOR_LABEL, ROLE_LABEL_KO` 추가 (기존 import 블록 끝에)
- [ ] `run_turn` driver 호출 (`:335-348`) `with Spinner(...)` wrapping — message 형식: `[{ROLE_LABEL_KO[driver_role]}: {VENDOR_LABEL[driver_runner.name]}] running...`
- [ ] `run_turn` reviewer 호출 (`:391-404`) 동일 wrapping (reviewer_role / reviewer_runner.name 사용)
- [ ] `Spinner` 컨텍스트 매니저는 except 분기에서도 정상 `__exit__` 보장 — 별도 finally 불필요 (Python 언어 명세)
- [ ] `tests/test_orchestrator_spinner.py` 신규 — ≥2 케이스 (isatty=True wrap / isatty=False no-op)
- [ ] `pytest tests/test_orchestrator_spinner.py -q` ≥2 passed
- [ ] `pytest -q` 전체 회귀 0 (43 → ≥45 본 phase 한정)

## 5. 검증

- `pytest tests/test_orchestrator_spinner.py -q` ≥2 passed
- `grep -n "with Spinner" src/orchestrator.py` 2건 (driver + reviewer) 단언
- `grep -n "VENDOR_LABEL\|ROLE_LABEL_KO" src/ui.py src/orchestrator.py` 정의 1회씩 + import 1회씩 단언
- `python -c "from src.ui import VENDOR_LABEL, ROLE_LABEL_KO; assert VENDOR_LABEL['codex'] == 'Codex CLI'; assert ROLE_LABEL_KO['implementer'] == '구현자'"` exit 0
- (수동) `dialectic run --task "test" --max-turns 1` 실행 — driver/reviewer 호출 동안 spinner 화면 표시 (인증 부재 시 호출 즉시 error 분기 진입이라 spinner 시각 검증은 짧을 수 있음, with 컨텍스트 진입·종료 자체는 검증)

## 6. 엣지케이스 / 위험 (Phase 한정)

- **isatty=False (CI/파이프)**: Spinner는 plan 006에서 `_enabled = bool(...isatty(...))` 가드 보유 — `__enter__`에서 thread 미시작, `__exit__` no-op. 회귀 0
- **except 분기 spinner 정리**: `with` 컨텍스트 매니저는 except 진입 시에도 `__exit__` 호출 보장 (Python 언어 명세 §The with statement). thread.join은 plan 006 `__exit__` 구현 내 `Event.set() + thread.join(timeout=1)` 보유
- **mock runner 부재 (Day 2)**: mock 어댑터는 plan 007 후속이라 본 phase test에서는 직접 `class _MockRunner` 정의 — `AgentRunner` Protocol 시그니처 1:1 (run 메서드 + name/vendor 속성). 기존 `tests/test_orchestrator_converge.py` 패턴 참조
- **vendor 라벨 fallback**: `VENDOR_LABEL.get(runner.name, runner.name)` — 미등록 vendor (예: 향후 추가 어댑터)에서도 raw name 표시. paste dict 직접 인덱싱은 KeyError 위험이라 회피
- **role 라벨 fallback**: `ROLE_LABEL_KO.get(role, role)` — `MODE_ROLES`에 신규 role 추가 시 raw 영문 표시 (회귀 0)
- **spinner 메시지 길이**: outline §3.2:190-194 narrative는 `[구현자: Codex CLI] running... ⠋` 형식. Spinner 내부에서 `\r{frame} {self._message}` 출력 (`src/ui.py:100`)이라 message에 frame 포함 X (Spinner가 자동 prepend) — message 형식은 `[role: vendor] running...`만
- **테스트 capsys stderr**: Spinner는 stderr write라 `capsys.readouterr().err`로 캡처. `capsys.readouterr().out`은 빈 문자열 (Phase A 한정, B에서 stdout 사용)
