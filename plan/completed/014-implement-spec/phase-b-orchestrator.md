# Phase B · run_session implement 분기 — 014-implement-spec

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: A (Phase A의 `args.spec` 인자 + `dialectic implement` alias subparser 사용)
- 병렬 그룹: —
- 예상 LOC: ~25 (코드) + ~40 (테스트)

## 1. 목표

`src/orchestrator.py:run_session`에 `mode==implement` 분기 추가 — `args.spec` 검증 (None/missing/directory/empty 4종 SystemExit) + 정상 시 `args.task = spec_body` substitution. spec body는 `_task_msg` → JSONL turn_id=0 메시지 + `build_prompt §2 TASK` 자리에 자동 진입 (별도 build_prompt 분기 X).

## 2. 입력

- Phase A 산출 — `args.spec` 인자 + `dialectic implement` alias subparser
- [`src/orchestrator.py:764`](../../src/orchestrator.py) — `bus.append(_task_msg(args.task, args.mode, workdir))` task 메시지 진입점 AS-IS
- [`src/orchestrator.py:771-772`](../../src/orchestrator.py) — `if args.mode == "plan":` spec_path 분기 (plan 013 산출). 본 plan은 그 전후 또는 별도 위치에 implement 분기 추가
- [`src/orchestrator.py:197-226`](../../src/orchestrator.py) — `build_prompt(role, task, ...)` mode 무관, task 1:1 §2 주입 (변경 X)
- [`src/orchestrator.py:48-50`](../../src/orchestrator.py) — `MODE_ROLES["implement"] = {driver: "implementer", reviewer: "spec-reviewer"}` (Day 1 보존, 변경 X)
- 사전 검증 사실: `args.task`는 `_task_msg`/`run_turn` 호출자가 그대로 사용 — substitution은 run_session 진입 직후 1회면 충분
- 사전 검증 사실: `Path(args.spec).resolve()`는 symlink·상대경로 정규화 + 절대 경로 반환 (cli.py에서 이미 절대경로면 idempotent)
- 사전 검증 사실: post-010 default workdir이 `~/.local/share/dialectic/runs/<ts-id>/`라 spec 경로(보통 `<ts-id>/specs/<slug>.md`)는 ADR-6 차단 무관

## 3. 출력

### 3.1 `run_session` implement 분기 추가

```python
# spec — bus.append(_task_msg(...)) 호출(:764) 직전, plan 013 spec_path 분기 (:771) 직전 또는 직후
# 위치: session_dir mkdir 후, _task_msg 직전이 자연스러움 (task 메시지에 spec body가 들어가야 하므로)

if args.mode == "implement":
    spec_arg = getattr(args, "spec", None)
    if not spec_arg:
        raise SystemExit(
            "implement 모드는 --spec <path> 필수 — outline :50 dialectic implement narrative."
        )
    spec_path_in = Path(spec_arg).resolve()
    if not spec_path_in.is_file():
        raise SystemExit(f"spec 파일 없음 또는 디렉토리: {spec_path_in}")
    try:
        spec_body = spec_path_in.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise SystemExit(f"spec UTF-8 디코딩 실패: {spec_path_in} ({e})") from e
    if not spec_body.strip():
        raise SystemExit(f"spec 파일 비어있음: {spec_path_in}")
    # task 자리에 spec body 주입 — protocol.md §5 :282-284 정합
    # _task_msg + build_prompt §2 TASK가 일관되게 spec body로 채워짐
    args.task = spec_body
```

### 3.2 위치 결정

`run_session` 본문 흐름 (post-010/013):
```
:660  workdir = _resolve_workdir(args)
:695  ADR-6 차단
:709  K fallback
:720  max_turns clamp
:739  try:
:744    session_ts/session_dir/sessions_dir mkdir
:764    bus.append(_task_msg(args.task, args.mode, workdir))  ← task 메시지 시점
:771    if args.mode == "plan": spec_path = _resolve_spec_path(...) (plan 013)
```

implement 분기 위치: `try:` 진입 직후, `:744` session_dir mkdir **이전** 또는 `:764` `_task_msg` **직전**.

**결정**: `_task_msg` 직전 (`:759` 인근). 이유:
- spec 검증 실패 → `_task_msg` 호출 안 함 → JSONL 빈 상태로 SystemExit (clean)
- session_dir은 이미 mkdir됨 (사용자가 stderr session 경로 안내 후 이해)
- ADR-6 차단(`:695`) 이후라 workdir이 절대 안전 보장됨

### 3.3 mode!=implement에서 `--spec` 무시 narrative

`run_session` docstring에 1줄 추가:

```python
# spec
def run_session(args: argparse.Namespace) -> int:
    """... 기존 docstring +

    args.spec: implement 모드 입력 (필수). 다른 mode에선 argparse가 받아도 무시 (Phase B §6).
    """
```

stderr 경고는 **본 plan 1차 외** — mode==run/plan에서 args.spec 명시 시 단순 무시.

### 3.4 신규 단위 테스트 — `tests/test_implement_spec.py` 누적 (Phase A 위)

```python
# spec — Phase B 케이스 (≥5)
def test_implement_mode_spec_none_systemexit(tmp_path, monkeypatch):
    """args.spec=None + mode==implement → SystemExit '필수'."""

def test_implement_mode_spec_missing_systemexit(tmp_path, monkeypatch):
    """args.spec=<missing path> → SystemExit '없음'."""

def test_implement_mode_spec_directory_systemexit(tmp_path, monkeypatch):
    """args.spec=<directory> → SystemExit '없음 또는 디렉토리'."""

def test_implement_mode_spec_empty_systemexit(tmp_path, monkeypatch):
    """args.spec=<empty file> → SystemExit '비어있음'."""

def test_implement_mode_spec_substitution(tmp_path, monkeypatch):
    """정상 spec → args.task가 spec body로 substitution됨 검증.

    mock driver/reviewer + spec.md 본문 'Spec body content'
    검증: bus.read_all()의 turn_id=0 task 메시지 content == 'Spec body content'
    """
```

mock 패턴: `tests/test_spec_autosave.py`의 `_mock_runner` + `_patch_runners` 재사용 (또는 import).

## 4. 작업 단위

- [ ] (Pre-execute) `grep -n "def run_session\|bus\.append.*_task_msg\|args\.mode == \"plan\"" src/orchestrator.py`로 본 phase 인용 줄 재확인 (Phase A 진행으로 line drift 가능)
- [ ] `src/orchestrator.py` `run_session`에 `if args.mode == "implement":` 분기 추가 (위 §3.1 spec — `_task_msg` 호출 직전 위치)
- [ ] spec 검증 4종 (`spec is None` / `not is_file()` / `UnicodeDecodeError` / `not spec_body.strip()`) 모두 SystemExit + 사용자 친화적 메시지
- [ ] 정상 spec body → `args.task = spec_body` substitution
- [ ] `run_session` docstring에 `args.spec` 1줄 narrative 추가
- [ ] `tests/test_implement_spec.py`에 Phase B 케이스 5건 추가 (Phase A 위 누적)
- [ ] mock 패턴 — `tests/test_spec_autosave.py`의 `_mock_runner` import 또는 재정의
- [ ] `pytest -q` 전체 회귀 0 확인 (특히 plan 011/013 회귀)

## 5. 검증

- `python3 -c "from src.orchestrator import run_session; import inspect; print('spec' in inspect.signature(run_session).parameters or 'args.spec via Namespace')"` — args.spec 진입 통로 확인
- `pytest -q tests/test_implement_spec.py` Phase A·B 누적 ≥8 케이스 pass
- `pytest -q` 전체 회귀 0 (plan 010/011/013 산출 모두 영향 0)
- 단위 호출: `dialectic implement --spec /nonexistent` → SystemExit "spec 파일 없음 또는 디렉토리: ..." (실 호출 형태 검증)
- 단위 호출: 빈 spec.md 생성 후 `dialectic implement --spec <empty>` → SystemExit "spec 파일 비어있음"

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **spec read OSError (permission denied 등)**
   - `Path.read_text`는 PermissionError를 raise — 본 분기는 UnicodeDecodeError만 catch
   - PermissionError는 그대로 propagate → run_session finally에서 stderr session 안내 후 traceback
   - **mitigation**: 1차 plan 외. Phase B §6 narrative 박힘. 사용자 권한 이슈는 명확한 traceback이 더 도움

2. **spec 본문 token 한도 초과**
   - 모델별 다름 (claude-sonnet ~200K, codex 다양)
   - 본 plan은 stderr 경고만 — 한도 자체는 별도 plan
   - 본문 길이 ≥ 8000 char(rough) 시 stderr `f"WARNING: spec 본문 길이 {len(spec_body)} char — token 한도 초과 가능"` 1줄 (선택, 1차 구현 외)

3. **spec body가 코드 fence 포함 — extract_patches 영향?**
   - spec body는 task 자리에 들어감 (build_prompt §2 TASK). `extract_patches`는 driver 응답(resp1.text)에만 호출
   - task 자리 fence는 patches 추출 0 ✓
   - 그러나 driver(implementer)가 spec body를 그대로 베껴 응답하면 patches 추출됨 — 정상 동작 (implementer가 spec → 코드 patch 변환)

4. **args.spec이 ~`(home) 시작 path**
   - `Path("~/x.md").resolve()`는 expanduser X — 그대로 `~`를 디렉토리 이름으로 인식
   - `Path(args.spec).expanduser().resolve()` 권고? — 1차 단순화 위해 expanduser 0 (사용자가 절대 경로 입력 권장)
   - Phase A `_input_spec_path`도 동일 — 메뉴 입력 시 사용자가 절대 경로 직접 입력

5. **plan 013 산출 spec.md 충돌 fallback path와 동일 task 재실행**
   - plan 013은 `<workdir>/specs/<slug>-<session_ts>.md` fallback 생성
   - 사용자가 어느 spec 경로를 implement에 입력할지는 사용자 결정 (메뉴 또는 CLI)
   - logs subcommand(plan 010) 산출과 cross-link narrative — 별도 plan

6. **mock 어댑터 부재 — 통합 테스트는 monkeypatch로**
   - plan 007 mock 어댑터 deferred 상태. Phase B 테스트는 `_resolve_runner` monkeypatch + `MagicMock` runner로 운영
   - `tests/test_spec_autosave.py` 패턴 재사용
