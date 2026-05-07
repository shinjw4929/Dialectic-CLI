# Phase C · Orchestrator + CLI + env_check — 001-run-mode-core

## 0. 메타

- Phase ID: **C**
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: B1 (`src/agents/codex.py`), B2 (`src/agents/claude.py`)
- 병렬 그룹: —
- 예상 LOC: ~295 (orchestrator 165 — `_serialize_history` 명세 + 빈 응답 분기 driver/reviewer + ts 생성 규약 + **outline/02 §2.9 [CONVERGED] 감지/streak 누적/ADR-9 fallback 추가 +15 LOC** + cli rewrite 60 — `--convergence-streak`/`--interactive` 인자 2종 추가 +5 LOC + env_check 70)

## 1. 목표

한 턴 라이프사이클 + argparse `run`/`doctor` 서브커맨드 + 환경 점검(claude/codex `--version` + auth status). `dialectic run --max-turns 1` 한 턴 E2E exit 0 + JSONL 4 라인 보장.

## 2. 입력

- Phase A·B 산출물: `Bus`, `AgentRunner`, `CodexRunner`, `ClaudeRunner`.
- `docs/runtime-docs/protocol.md` §3 (`:196-211`, MODE_ROLES), §4 (`:212-231`, 턴 라이프사이클), §5 (`:233-271`, 4섹션 prompt), §7 (`:285-301`, cwd 격리).
- `docs/dev-docs/code-conventions.md` §6 (`:122-131`, CLI 인자 처리), §3 (`:31-58`, subprocess 규약 — env_check도 적용).
- `docs/runtime-docs/roles/{implementer,spec-reviewer}.md` (run 모드 driver/reviewer role 본문 — 4섹션 prompt §1 ROLE에 주입).

## 3. 출력

### 3.1 `src/orchestrator.py` (신규, ~165 LOC — phase-c §0 분해와 일관: orchestrator 본문 165 = imports 15 + dict 12 + helpers 30 + run_turn 50 + run_session 58)

```python
# paste
# imports — 표준 라이브러리만 (code-conventions.md §2 외부 의존성 0)
import dataclasses
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .agents.base import AgentAuthError, AgentRunner
from .agents.claude import ClaudeRunner
from .agents.codex import CodexRunner
from .bus import Bus
from .schema import Message, Meta

MODE_ROLES = {
    "run":       {"driver": "implementer", "reviewer": "spec-reviewer"},
    "plan":      {"driver": "planner",     "reviewer": "plan-reviewer"},
    "implement": {"driver": "implementer", "reviewer": "spec-reviewer"},
}

ROLE_FILE = {
    "implementer":   Path(__file__).parent.parent / "docs/runtime-docs/roles/implementer.md",
    "spec-reviewer": Path(__file__).parent.parent / "docs/runtime-docs/roles/spec-reviewer.md",
    "planner":       Path(__file__).parent.parent / "docs/runtime-docs/roles/planner.md",
    "plan-reviewer": Path(__file__).parent.parent / "docs/runtime-docs/roles/plan-reviewer.md",
}
```

```python
# spec
def build_prompt(role: str, task: str, history: list[Message], directive: str | None) -> str:
    """4섹션 prompt — protocol.md §5 (`:233-271`).

    # 4. YOUR TURN 본문은 role.md의 §"응답 전 셀프체크" 직전을 호출하는 짧은 lead-in:
    role-specific instructions는 ROLE.md 본문에 이미 있으므로 prompt §4는 단순 재호출 +
    directive 강조 (protocol.md §5 line 257 — '당신의 역할({role})로 다음을 수행:').
    """
    role_md = ROLE_FILE[role].read_text()
    history_md = _serialize_history(history) if history else "(이전 턴 없음)"
    your_turn = (
        f"당신의 역할({role})로 위 ROLE 섹션의 책임을 수행하십시오. "
        f"§ '응답 전 셀프체크'의 모든 항목을 통과해야 응답이 유효합니다.\n\n"
        f"(directive: {directive or 'none'})"
    )
    return f"# 1. ROLE\n{role_md}\n\n# 2. TASK\n{task}\n\n# 3. HISTORY\n{history_md}\n\n# 4. YOUR TURN\n{your_turn}"

def _detect_converged(text: str) -> bool:
    """outline/02 §2.9: reviewer 응답 마지막 비공백 줄이 정확히 '[CONVERGED]' 단독."""
    last = text.rstrip().splitlines()[-1] if text.rstrip() else ""
    return last.strip() == "[CONVERGED]"


def run_turn(
    turn_id: int,
    mode: str,
    *,
    driver_runner: AgentRunner,
    reviewer_runner: AgentRunner,
    bus: Bus,
    task: str,
    workdir: Path,
    sessions_dir: Path,
) -> None:
    history = bus.read_all()
    last_msg_id = history[-1].msg_id if history else None
    roles = MODE_ROLES[mode]

    # driver
    driver_role = roles["driver"]
    p1 = build_prompt(driver_role, task, history, directive=None)
    raw1 = sessions_dir / f"{turn_id}-driver-{uuid4().hex[:8]}.jsonl"
    try:
        resp1 = driver_runner.run(p1, raw_log_path=raw1, timeout_s=300, workdir=workdir)
        if not resp1.text:                 # 빈 응답 — Day 2는 retry 생략, 즉시 error 기록 후 턴 종료
            # response_meta 전달로 token 비용 silent loss 차단 (P-JSONL 정직성).
            bus.append(_error_msg(turn_id, 1, driver_role, "driver", mode,
                                  ValueError("empty_response"), workdir,
                                  parent_id=last_msg_id,
                                  vendor=driver_runner.vendor, agent_cli=driver_runner.name,
                                  latency_ms=resp1.meta.latency_ms,
                                  response_meta=resp1.meta))
            return
        proposal = _msg(turn_id, 1, driver_role, "driver", mode, "proposal",
                        resp1.text, parent_id=last_msg_id, meta=resp1.meta)
        bus.append(proposal)               # proposal.msg_id를 변수 보존 → reviewer 호출 시 parent_id 인자로 사용
    except (subprocess.TimeoutExpired, json.JSONDecodeError, AgentAuthError) as e:
        bus.append(_error_msg(turn_id, 1, driver_role, "driver", mode, e, workdir,
                              parent_id=last_msg_id,
                              vendor=driver_runner.vendor, agent_cli=driver_runner.name,
                              latency_ms=300_000 if isinstance(e, subprocess.TimeoutExpired) else 0))
        return

    # reviewer (history 다시 읽음 — proposal 반영)
    reviewer_role = roles["reviewer"]
    p2 = build_prompt(reviewer_role, task, bus.read_all(), directive=None)
    raw2 = sessions_dir / f"{turn_id}-reviewer-{uuid4().hex[:8]}.jsonl"
    try:
        resp2 = reviewer_runner.run(p2, raw_log_path=raw2, timeout_s=300, workdir=workdir)
        if not resp2.text:                 # 빈 응답 — Day 2는 retry 생략, 즉시 error 기록
            bus.append(_error_msg(turn_id, 2, reviewer_role, "reviewer", mode,
                                  ValueError("empty_response"), workdir,
                                  parent_id=proposal.msg_id,
                                  vendor=reviewer_runner.vendor, agent_cli=reviewer_runner.name,
                                  latency_ms=resp2.meta.latency_ms,
                                  response_meta=resp2.meta))
            return
        # outline/02 §2.9: 마커 감지 → critique meta.convergence_streak에 1 또는 None 기록.
        # frozen dataclass라 dataclasses.replace로 새 Meta 생성 (어댑터 meta 변경 X — 정직성).
        # 단순화 결정 — 누적 streak 값이 아닌 본 turn 마커 binary 박음. outline §2.9는 "디버깅·재현용
        # 필수 X — 없으면 0 가정"이라 자유 해석 영역. 누적 streak는 run_session 내부 변수 + 종료점
        # _meta_msg(convergence_streak=K)에 박힘. Day 3+에서 누적값 요구 시 run_turn에 streak 인자 추가.
        # 단순화 손실: JSONL 외부 독자가 critique meta만 보면 누적 streak 모름 (binary만). 누적 회수는
        # auto_end_converged 메시지의 K값 또는 인접 critique의 binary 카운트로만 가능. Day 2 한 턴
        # E2E 범위에서는 손실 미미 — 사용자가 streak 추적 필요 시 stderr 또는 logs/messages.jsonl 시계열 분석.
        is_converged = _detect_converged(resp2.text)
        critique_meta = dataclasses.replace(resp2.meta, convergence_streak=1 if is_converged else None)
        critique = _msg(turn_id, 2, reviewer_role, "reviewer", mode, "critique",
                        resp2.text, parent_id=proposal.msg_id, meta=critique_meta)
        bus.append(critique)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, AgentAuthError) as e:
        bus.append(_error_msg(turn_id, 2, reviewer_role, "reviewer", mode, e, workdir,
                              parent_id=proposal.msg_id,
                              vendor=reviewer_runner.vendor, agent_cli=reviewer_runner.name,
                              latency_ms=300_000 if isinstance(e, subprocess.TimeoutExpired) else 0))

def run_session(args) -> int:
    # Path.resolve()로 정규화 — symlink·상대경로 해소, Meta.workdir이 항상 절대 정규 경로 (재현성)
    workdir = (Path(args.workdir).resolve() if args.workdir
               else Path(tempfile.mkdtemp(prefix="dialectic-")).resolve())

    # ADR-6 사용자 입력 우회 차단: --workdir이 Dialectic-CLI repo 루트와 일치하면
    # 개발용 .md(CLAUDE.md/AGENTS.md)가 런타임 prompt에 누수된다. 친절한 안내 후 종료.
    DIALECTIC_REPO_ROOT = Path(__file__).resolve().parent.parent
    if workdir == DIALECTIC_REPO_ROOT:
        raise SystemExit(
            f"--workdir이 Dialectic-CLI repo 루트({workdir})와 일치합니다 (ADR-6). "
            f"개발용 .md가 런타임 prompt에 누수됩니다. 별도 경로를 지정하거나 "
            f"--workdir 미지정으로 임시 dir 자동 생성을 사용하십시오."
        )

    cleanup = (args.workdir is None)

    # ADR-9 (outline/02 §2.9): --max-turns < K+1 시 K=1 자동 fallback + stderr 경고.
    # 본 plan default --max-turns 1이라 default --convergence-streak 2면 매 호출 fallback 경로.
    K = args.convergence_streak
    if args.max_turns < K + 1 and K > 1:
        # K > 1 가드: K=1·max_turns=1 degenerate case에서는 "reduced to 1" 메시지가 misleading.
        # K=1 명시 입력은 fallback 경로 자체가 무의미 — 메시지 skip.
        sys.stderr.write(
            f"--max-turns ({args.max_turns}) < --convergence-streak + 1 ({K + 1}) — "
            f"K reduced to 1 (ADR-9, outline/02 §2.9)\n"
        )
        K = 1

    try:
        logs_dir = workdir / "logs"
        sessions_dir = logs_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        bus = Bus(logs_dir / "messages.jsonl")
        # task 메시지 (turn_id=0)
        bus.append(_task_msg(args.task, args.mode, workdir))

        driver_runner = _resolve_runner(args.driver)
        reviewer_runner = _resolve_runner(args.reviewer)

        # outline/02 §2.9: reviewer [CONVERGED] streak K 도달 시 auto_end_converged.
        # critique 부재(error 등)는 streak reset.
        streak = 0
        for turn in range(1, args.max_turns + 1):
            run_turn(
                turn, args.mode,
                driver_runner=driver_runner, reviewer_runner=reviewer_runner,
                bus=bus, task=args.task, workdir=workdir, sessions_dir=sessions_dir,
            )
            last_critique = next(
                (m for m in reversed(bus.read_all()) if m.kind == "critique" and m.turn_id == turn),
                None,
            )
            if last_critique is None:
                streak = 0
                continue
            if last_critique.meta.convergence_streak == 1:
                streak += 1
                if streak >= K:
                    bus.append(_meta_msg(
                        turn, "auto_end_converged", workdir, args.mode,
                        parent_id=last_critique.msg_id, convergence_streak=K,
                    ))
                    return 0
            else:
                streak = 0

        # fallthrough: max-turns 도달 (Day 3에서 인터랙티브 6지선다로 교체 가능)
        # DAG 무결성: _meta_msg는 직전 메시지를 parent로 (DoD 00-plan.md §6 — task 외 모든 메시지 parent_id non-None)
        last = bus.read_all()[-1]
        bus.append(_meta_msg(args.max_turns, "auto-end (max-turns reached)", workdir, args.mode, parent_id=last.msg_id))
        return 0
    finally:
        if cleanup:
            shutil.rmtree(workdir, ignore_errors=True)
```

### 3.2 orchestrator 내부 헬퍼 (4종 — execute-plan 자유 해석 차단을 위해 시그니처·반환 명세 고정)

`run_turn`/`run_session`이 호출하는 `Message` 생성 헬퍼 4종. 모두 `Message`/`Meta` 인스턴스 반환 (시그니처 frozen, dataclass의 `__init__` 그대로 채움).

**`ts` 생성 규약** (4 헬퍼 모두 동일): 함수 본문 첫 줄에서 `ts = datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')` 생성 — **protocol.md §2 line 92 명세 1:1**. 결과 형식: `2026-05-07T12:00:00.000Z` (정규식 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$` 매치). `datetime.utcnow()` (TZ-naive, Python 3.12+ deprecated) + 단순 `isoformat()` (Z 접미사 없음, +00:00 잔존) 모두 금지 — protocol.md 계약 위반. 호출자 인자로 받지 않음 (시그니처 단순화). 같은 turn 내 여러 헬퍼 호출 시 ts가 미세하게 다르지만 의도된 동작 (latency 추적용).

**sentinel `Meta` 14 필드 일관 규약** (13 default-없는 + 1 default `convergence_streak`. `_task_msg`/`_meta_msg`/`_error_msg` 공통 sentinel 채움 패턴):

```python
# paste
SENTINEL_META = lambda workdir, vendor="system", agent_cli="system", latency_ms=0, convergence_streak=None: Meta(
    vendor=vendor, agent_cli=agent_cli,
    model=None, session_id=None, thread_id=None,
    input_tokens=0, output_tokens=0, cached_input_tokens=0, reasoning_output_tokens=0,
    cost_usd=None, latency_ms=latency_ms,
    is_mock=False, workdir=str(workdir),
    convergence_streak=convergence_streak,
)
```

13 default-없는 필드 모두 채움 — schema.Meta는 frozen dataclass 14 필드, `convergence_streak: int | None = None` 1개만 default 보유 (phase-a §3.1). 따라서 SENTINEL_META lambda는 default-없는 13 필드를 전부 인자로 채우고 14번째 default 필드는 keyword `convergence_streak=None` 옵션. 어댑터(phase-b1/b2)도 동일 — `Meta(...)` 호출에 `convergence_streak` 미전달 → default None 적용 (정합).

**상수 (magic number 회피)**:

```python
# paste
META_SEQ_SENTINEL = 99   # _meta_msg의 seq_in_turn — turn 내 최후 위치 명시 (driver=1, reviewer=2, user=3 다음 sentinel)
```

**`_serialize_history(history: list[Message]) -> str`** (build_prompt 내부에서 호출):

```python
def _serialize_history(history: list[Message]) -> str:
    """protocol.md §5 (`:246-260`) 형식으로 직렬화. 라벨 = role 대문자.

    예시 출력:
    ## Turn 1
    - IMPLEMENTER (proposal): ...본문...
    - SPEC-REVIEWER (critique): ...본문...
    - USER (decision: iterate, directive: "..."): ...

    ## Turn 2
    ...
    """
    # 의사코드 (execute-plan 자유 해석 차단):
    #   1. turn_id=0 (task 메시지)는 "## TASK" 또는 별도 처리 — Day 2는 build_prompt §2 TASK가
    #      task 본문을 별도 주입하므로 history 직렬화에서 제외 권장 (중복 주입 차단).
    #   2. history 중 turn_id >= 1만 sorted(key=(turn_id, seq_in_turn)) 후 itertools.groupby로
    #      turn_id별 묶음.
    #   3. 각 turn 묶음 헤더 "## Turn {N}" + 멤버를 "- {ROLE.upper()} ({kind}): {content}" 줄로.
    #   4. kind=meta/error는 from_=system이므로 라벨 "SYSTEM"으로 별도 줄 ("- SYSTEM ({kind}): ...").
    #   5. kind=decision은 라벨 "USER" + directive 표기 ("- USER (decision: {content}, directive: \"{directive}\"): ...").
    #   6. 빈 history (turn_id >=1 메시지 0건)면 "(이전 턴 없음)" 한 줄 반환.
    # 5~10 LOC 수준. 본 함수는 본 plan에서 명세만 — execute-plan이 의사코드대로 구현.
```

```python
def _msg(
    turn_id: int,
    seq_in_turn: int,
    role: str,                    # "implementer" | "spec-reviewer" | ...
    slot: str,                    # "driver" | "reviewer"
    mode: str,                    # "run" | "plan" | "implement"
    kind: str,                    # "proposal" | "critique"
    content: str,
    *,
    parent_id: str | None,
    meta: Meta,
) -> Message:
    """driver/reviewer 응답 메시지 — ts = datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') 본문 생성.
    bus.append 전 호출자가 변수에 보존하여 다음 턴 parent_id로 사용."""

def _error_msg(
    turn_id: int,
    seq_in_turn: int,
    role: str,
    slot: str,
    mode: str,
    exc: Exception,
    workdir: Path,
    *,
    parent_id: str | None,
    vendor: str = "system",       # 호출자가 driver_runner.vendor / reviewer_runner.vendor 전달 권고
    agent_cli: str = "system",    # 호출자가 driver_runner.name / reviewer_runner.name 전달 권고
    latency_ms: int = 0,          # timeout이면 호출자가 timeout_s * 1000 전달 권고
    response_meta: Meta | None = None,  # 빈 응답 case (정상 종료 + text="")의 token 비용 보존용
) -> Message:
    """호출 실패 메시지. ts = datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') 본문 생성.
    빈 응답(`if not resp.text:` 분기)은 정상 호출 종료 + 빈 텍스트라 어댑터 응답에 token 비용·model 등 정상 데이터 존재.
    `response_meta` 인자 전달 시 token 4종 + model + session_id/thread_id + cost_usd + cached_input_tokens 모두 보존
    (code-conventions.md §4 정직성 — silent loss 차단). exception case (timeout/auth/parse fail)는 response_meta=None
    → SENTINEL_META(workdir, vendor=vendor, agent_cli=agent_cli, latency_ms=latency_ms)로 fallback (sentinel 0 채움).
    - SENTINEL_META 패턴은 14 필드 모두 채움 (default convergence_streak=None 자동).
    - latency_ms — timeout이면 caller가 timeout_s*1000 전달, 그 외 0 또는 response_meta.latency_ms.
    - turn_id/seq_in_turn은 호출자 인자, slot은 호출자 인자 ("driver"|"reviewer").
    content = f"{type(exc).__name__}: {str(exc)[:500]}", directive=None."""

def _task_msg(task: str, mode: str, workdir: Path) -> Message:
    """첫 메시지 — ts = datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') 본문 생성.
    turn_id=0, seq_in_turn=1, from_="system", to="broadcast", slot=None,
    kind="task", content=task, directive=None, parent_id=None.
    meta = SENTINEL_META(workdir) (vendor=agent_cli="system", 14 필드 모두 채움 (default convergence_streak=None 자동))."""

def _meta_msg(turn_id: int, content: str, workdir: Path, mode: str, *, parent_id: str | None, convergence_streak: int | None = None) -> Message:
    """auto-end / auto_end_converged / budget_exceeded 등 시스템 이벤트 — ts = datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') 본문 생성.
    turn_id=호출 시점, seq_in_turn=META_SEQ_SENTINEL (=99, turn 내 최후 위치),
    from_="system", to="broadcast", slot=None, kind="meta", directive=None.
    parent_id는 호출자(run_session)가 bus.read_all()[-1].msg_id 또는 last_critique.msg_id 추출 후 keyword-only — DAG 무결성.
    convergence_streak — auto_end_converged 시 호출자가 K 값 전달 (outline/02 §2.9). 그 외 None.
    meta = SENTINEL_META(workdir, convergence_streak=convergence_streak)."""
```

설계 의도: 호출자가 헬퍼 반환 `Message`를 변수에 보존해야 다음 호출의 `parent_id`로 사용 가능. `bus.append`가 인스턴스를 변경하지 않으므로(`Message` frozen) 안전. 자급자족성 — 본 plan 외부 review 라벨에 의존하지 않는 자체 설계 명세.

### 3.3 `src/env_check.py` (신규, ~70 LOC)

```python
# paste
import os
import subprocess
from pathlib import Path

# code-conventions.md §3 화이트리스트 — auth + 시스템 변수만 통과
# 본 plan 결정: PATH+HOME(§3 line 43-48 예시) + USER/LANG 추가. USER는 일부 CLI(claude/codex)가
# 사용자 식별·로깅에 참조 가능, LANG은 stderr/help 메시지 인코딩. code-conventions.md §3 추후 sync 권고
# (본 plan 같은 commit에서 §3 갱신은 phase-d §3.5b code-conventions.md 갱신과 별개라 deferred — Day 3 또는 후속 plan).
_SYS_VARS = ("PATH", "HOME", "USER", "LANG")
_AUTH_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CODEX_HOME", "CLAUDE_CODE_OAUTH_TOKEN")

def _safe_env() -> dict:
    """외부 환경변수 누수 차단 화이트리스트 — code-conventions.md §3 규약.

    NOTE (re P2 단일 진실 소스): 본 함수의 _SYS_VARS는 phase-b1/b2 어댑터의 _build_env()와
    동일 시스템 변수 집합. execute-plan 시 (a) 본 두 정의를 비교 + (b) 일치하면 src/_env.py
    한 모듈로 분리 권고 — 향후 mock 어댑터 추가 시 화이트리스트 비대칭 자동 차단. 본 plan
    범위에서는 narrative 권고만 — execute 단계의 자연스러운 리팩터링 영역."""
    return {k: os.environ[k] for k in (*_SYS_VARS, *_AUTH_VARS) if k in os.environ}
```

```python
# spec
def check_env() -> dict:
    """비용 0 환경 점검 — claude/codex --version + auth/login status + claude doctor."""
    env_pass = _safe_env()
    return {
        "claude": {
            "version": _run_capture(["claude", "--version"], env=env_pass, timeout=5),
            "auth":    _run_capture(["claude", "auth", "status"], env=env_pass, timeout=10),    # 인증 상태 (--help의 'auth' 서브커맨드)
            "doctor":  _run_capture(["claude", "doctor"], env=env_pass, timeout=30),            # auto-updater 점검 (사용자 환경 진단). timeout 30s — auto-updater 네트워크 호출 가능성 고려 (10s는 짧음). **비용 0 단서 — 사용자 home에 .mcp.json 부재 시 비용 0**. .mcp.json 존재 시 stdio MCP 서버 health check spawn(부수효과). cwd=Path.home() 결정은 OAuth 캐시 위치 안정성 우선이라 .mcp.json 부재 환경 가정 — Day 3+에서 ephemeral cwd 옵션 검토 가능.
        },
        "codex": {
            "version": _run_capture(["codex", "--version"], env=env_pass, timeout=5),
            "login":   _run_capture(["codex", "login", "status"], env=env_pass, timeout=10),    # 인증 상태 ('login' 서브커맨드의 status 자식)
        },
    }

def _run_capture(cmd, env, timeout, cwd=None) -> dict:
    """{ok: bool, stdout: str, stderr: str}.

    cwd 미지정 시 Path.home() — code-conventions.md §3 'cwd 명시 필수' P0 규약 준수.
    Path.home()은 OAuth 캐시(`~/.claude/`, `~/.codex/`) 위치이므로 인증 상태 호출에 안정적이고
    Dialectic-CLI repo 루트가 아니라 ADR-6 두 층 누수와도 무관."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env, check=False,
            cwd=cwd or Path.home(),
        )
        return {"ok": r.returncode == 0, "stdout": r.stdout.strip()[:200], "stderr": r.stderr.strip()[:200]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout"}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "command not found"}
```

### 3.4 `src/cli.py` (rewrite, ~60 LOC total — argparse 35 (base 30 + `--convergence-streak`/`--interactive` 5) + main/dispatch 15 + _print_env_check 10. 직전 review-plan 보강에 따라 base 55 → total 60 (+5))

```python
# paste
import argparse

from . import orchestrator
from .env_check import check_env
```

```python
# spec
def main() -> int:
    parser = argparse.ArgumentParser(prog="dialectic")
    subs = parser.add_subparsers(dest="cmd", required=False)

    # run
    p_run = subs.add_parser("run", help="dialectic 한 턴 실행")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--workdir", default=None,
                       help="작업 디렉토리. 미지정 시 tempfile.mkdtemp(prefix='dialectic-')로 자동 생성. Dialectic-CLI repo 루트는 ADR-6에 의해 사용 불가 (개발용 .md가 런타임 prompt에 누수되므로 SystemExit).")
    p_run.add_argument("--driver", choices=["codex", "claude"], default="codex")
    p_run.add_argument("--reviewer", choices=["codex", "claude"], default="claude")
    p_run.add_argument("--max-turns", type=int, default=1)
    # paste — choices/default/help는 plan 결정 핵심 narrative라 변형 금지 (P-MODE)
    p_run.add_argument("--mode", choices=["run"], default="run",
                       help="Day 2는 'run' 모드만 노출. plan/implement/compare는 Day 3+에서 인터랙티브 UI + spec 입력 메커니즘(--spec @<path>) + build_prompt implement 분기 추가 후 노출 — 현재 protocol.md §5:243 implement 계약(spec.md 본문 주입) 미구현이라 choices에 포함 시 잘못 동작·비용 발생·JSONL mode 라벨 오염. MODE_ROLES dict는 Day 3+ 호환성 위해 plan/implement 키 보존.")
    p_run.add_argument("--convergence-streak", type=int, default=2,
                       help="reviewer [CONVERGED] 마커 단독 마지막 줄 누적 K턴 도달 시 auto_end_converged (outline/02 §2.9). default K=2. ADR-9: --max-turns < K+1 시 K=1 자동 fallback + stderr 경고 — 본 plan default --max-turns 1이면 매 호출 fallback.")
    p_run.add_argument("--interactive", choices=["end-only"], default="end-only",
                       help="Day 2 한정 'end-only' 단일 노출 (인터랙티브 미구현 — max-turns 또는 [CONVERGED] streak까지 자동 진행, 사용자 prompt 0). 사용자가 `--interactive full` 등 전달 시 argparse가 'invalid choice' raw error 발생 — 의도된 차단 (outline/03 §3.1 약속 미구현 시점이라). Day 3+에서 choices=['full','critical','end-only'] + default='critical' + 6지선다(a/r/m/i/s/e) + Enter=iterate 빈 directive 정책 동시 추가 (outline/03 §3.3).")
    p_run.set_defaults(func=lambda args: orchestrator.run_session(args))

    # doctor
    p_doc = subs.add_parser("doctor", help="환경 점검 (claude/codex --version + auth status, 비용 0)")
    p_doc.set_defaults(func=lambda args: _print_env_check())

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 0
    return args.func(args)

def _print_env_check() -> int:
    res = check_env()
    # 보기 좋게 표 형식 출력 (rich 없이 ANSI)
    ok = all(r["ok"] for tool in res.values() for r in tool.values())
    return 0 if ok else 1
```

## 4. 작업 단위

- [ ] `src/orchestrator.py` 생성 — `MODE_ROLES`, `ROLE_FILE`, `build_prompt()`, `run_turn()`, `run_session()`.
- [ ] `build_prompt()` — protocol.md §5 4섹션 형식 정확히 따름. role.md 본문을 `# 1. ROLE` 섹션에 주입.
- [ ] **헬퍼 4종** (§3.2) — `_msg`, `_error_msg`, `_task_msg`, `_meta_msg`. 시그니처 §3.2 명세 그대로 + `SENTINEL_META` 14 필드 일관 규약 (13 default-없는 + 1 default `convergence_streak=None`) + 본문 첫 줄 `ts = datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')` 필수 (protocol.md §2 line 92). 모두 `Message` 반환, 호출자가 변수에 보존 후 다음 호출 `parent_id`로 사용.
- [ ] `run_turn()` — driver → reviewer 순차. driver `_msg` 결과(`proposal`)를 변수 보존 → reviewer 호출 시 `parent_id=proposal.msg_id`.
- [ ] **빈 응답 분기** — `if not resp.text: bus.append(_error_msg(..., ValueError("empty_response"), ...))` 후 return. driver·reviewer 양쪽 모두 적용. Day 2는 retry 생략 (즉시 error 기록).
- [ ] `run_turn()` 실패 catch — `_error_msg`에도 `parent_id` 명시 (직전 메시지 ID), `vendor`·`agent_cli`·`latency_ms` 어댑터에서 추출 전달.
- [ ] `run_session()` 본문에 `logs_dir.mkdir(parents=True, exist_ok=True)` + `sessions_dir = logs_dir / "sessions"` + `sessions_dir.mkdir(parents=True, exist_ok=True)` 명시 (run_turn에 전달).
- [ ] `run_session()` — `--workdir` 미지정 시 `tempfile.mkdtemp(prefix="dialectic-")` + `try/finally` cleanup. **`Path.resolve()`로 정규화** (symlink·상대경로 해소, `Meta.workdir`이 항상 절대 정규 경로 — 재현성). **`workdir == Path(__file__).resolve().parent.parent` 검증 → SystemExit (ADR-6 사용자 입력 우회 차단, 친절한 안내 메시지)**. `_task_msg`(turn_id=0) → N 턴 → `_meta_msg`(auto-end, **호출자가 `bus.read_all()[-1].msg_id` 추출 후 `parent_id=` keyword-only 인자로 전달 — DAG 무결성**).
- [ ] `_resolve_runner(name: str) -> AgentRunner` — 단순 dict 패턴: `return {"codex": CodexRunner(), "claude": ClaudeRunner()}[name]`. 반환 타입 힌트 `AgentRunner`로 인터페이스 강제 (Protocol 준수 self-document). unknown name이면 KeyError 자연 raise → cli argparse `choices`가 1차 차단. mock은 Day 3.
- [ ] **`src/_env.py` 단일 모듈 분리 검토** (P2, deferred) — `_SYS_VARS`/`_AUTH_VARS` 화이트리스트가 env_check + codex 어댑터 + claude 어댑터 3 모듈에 중복. Day 2 narrative 권고만, 본 plan 본문에서 명시 리팩터링 X. 사용자 판단으로 본 plan 범위 또는 Day 3 plan 추가. Day 3+ mock 어댑터 도입 시 비대칭 위험 예방을 위해 우선순위 ↑.
- [ ] `src/env_check.py` 생성 — `check_env()` + `_run_capture(cmd, env, timeout, cwd=None)` + `_safe_env()` (3 함수 모두 본 phase에서 정의). `_safe_env()`는 `_SYS_VARS` + `_AUTH_VARS` 화이트리스트 (code-conventions.md §3). `_run_capture`는 `cwd=cwd or Path.home()`로 P0 cwd 명시 규약 준수. 4종 호출(`claude --version`, `claude auth status`, `codex --version`, `codex login status`) + `claude doctor` 모두 비용 0.
- [ ] `src/cli.py` rewrite — argparse subparsers `run` + `doctor`, 인자 부재 시 `print_help()` (Day 3 메뉴 fallback placeholder).
- [ ] entry-point는 기존 `pyproject.toml:23` `dialectic = "src.cli:main"` 유지.

## 5. 검증

- `python -c "from src.orchestrator import MODE_ROLES, build_prompt, run_session; from src.env_check import check_env; from src.cli import main"` exit 0.
- `dialectic doctor` exit 0, claude/codex `--version` + `auth/login status` 출력. 비용 0 확인 (token 사용 없음).
- `dialectic run --task "Reply with single digit: 1+1=?" --workdir /tmp/test-run-c --driver codex --reviewer claude --max-turns 1` exit 0.
- `/tmp/test-run-c/logs/messages.jsonl` 4 라인 이상:
  - 라인 1: `kind=task, from=system, turn_id=0`
  - 라인 2: `kind=proposal, from=implementer, slot=driver, turn_id=1, meta.is_mock=false, meta.workdir="/tmp/test-run-c"`
  - 라인 3: `kind=critique, from=spec-reviewer, slot=reviewer, turn_id=1, meta.is_mock=false`
  - 라인 4: `kind=meta, from=system, content~="auto-end"`
- 매 메시지 `msg_id` uuid4 형식, `parent_id` 직전 메시지 가리킴.
- `dialectic run` 인자 부재 시 usage 출력 (exit 0 또는 2).

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **`claude auth status` / `codex login status` 서브커맨드 정확한 표기** (P-VENDOR) — 직전 review-plan에서 실 호출(`claude auth status` 직접 invoke)로 확인. 단 `claude auth --help` 출력에는 `status` 자식 표기 부재 → `--help` parsing 의존 검증은 false negative 위험. **검증 방식**: phase-c §6 진입 전에는 실 호출(`claude auth status` exit code 확인)이 진실. `--help` 텍스트 grep으로만 확인 시 P-VENDOR 잠재 트리거. — `claude --help`에 `auth` 서브커맨드 존재. `codex --help`에 `login` 서브커맨드 존재. 자식 인자(`status`)는 둘 다 `--help`로 추가 검증 필요. **Phase C 시작 시 직접 1회 검증** (비용 0). 어긋나면 `_run_capture` 명령만 수정, 다른 코드는 영향 없음.
2. **인증 미설정 시 `dialectic doctor` 출력** — `auth/login status` 명령이 non-zero exit 또는 "not logged in" 메시지 — 이를 사용자에게 친절히 표시 (붉은 색 ANSI + README §환경설정 링크).
3. **`tempfile.mkdtemp` cleanup 시점** — `try/finally`에서 `shutil.rmtree(ignore_errors=True)`. 단 `--workdir` 명시 사용자는 cleanup X (사용자 코드베이스 보존).
4. **role.md 경로 못 찾음** — `Path(__file__).parent.parent / "docs/runtime-docs/roles/<role>.md"`. 패키지 install 후 wheel 안에 들어있는지 확인 필요. **결정**: editable install (`pip install -e .`)이 본 plan 가정 (`setup.sh`도 editable). wheel 배포 시 `package_data` 설정 또는 `importlib.resources` 적용은 deferred — **Day 4 plan에 cross-link 항목 추가 예정** (`outline/05-timeline.md` Day 4 자기 검증 단계에서 wheel 실 검증 + 필요 시 ADR-9 신규).
5. **history 직렬화 형식** — protocol.md §5 형식 (`## Turn N\n- IMPLEMENTER (proposal): ...`). 첫 턴은 history 비어 있음 — `# 3. HISTORY\n(이전 턴 없음)` 처리.
6. **`max_turns=1`은 사실상 loop X** — for문 1회만 실행. Day 3 인터랙티브 추가 시 `for` 안에 user decision 분기 + `break` 추가. **outline/03 §3.3 6지선다 (a/r/m/i/s/e) + Enter=`iterate` 빈 directive default 정책** 적용 — `--interactive {full,critical,end-only}` 플래그가 분기 강도 제어 (full=매 턴, critical=P0/P1 발견 시만, end-only=자동 종료까지 전혀 prompt X). Day 2는 `end-only` hardcoded.
7. **`directive=None` (첫 턴)** — protocol.md §5는 `(directive: ...)` 마지막 줄 필수. None이면 `"none"` 문자열로 직렬화.
8. **`--workdir <repo 루트>` 사용자 입력 우회** (P-CWD/P-LEAK, ADR-6) — `Path.resolve()`만으로는 사용자가 Dialectic-CLI 루트를 명시 입력하면 막을 수 없음. `run_session()` 본문에서 `workdir == Path(__file__).resolve().parent.parent` 검증 후 `SystemExit` (친절한 안내 — "별도 경로 또는 미지정 사용"). 단위 테스트는 phase-d §3.3 monkeypatch 케이스에 추가 (`test_run_session_rejects_repo_root_workdir`).
9. **`--mode` choices 축소 결정** (P-MODE) — Day 2 plan/implement/compare 미구현(spec 입력 부재 + build_prompt implement 분기 부재)이라 choices에서 노출하면 protocol.md §5:243 계약 위반. CLI choices는 `["run"]`로 좁히되 `MODE_ROLES`/`ROLE_FILE` dict는 plan/implement 키 보존 (Day 3+ 추가 시 dict 변경 X — choices 한 줄 갱신만으로 활성).
10. **`dialectic logs` 서브커맨드 deferred** (outline/03 §3.5, Q3) — `--follow`/`--kind`/`--turn`/`--since`/`--summary`/`--run` 옵션은 Day 3+ 추가. Day 2 본 plan은 `run`/`doctor` 두 서브커맨드만. cli `argparse subparsers` 확장 위치는 `p_doc` 다음에 `p_logs = subs.add_parser("logs", ...)` — Day 3 plan 진입 시 대화 명확.
11. **mock fallback deferred** (outline/03 §3.1, §4.4 Q5·C) — 인증 부재 시 자동 mock 어댑터 fallback 메커니즘은 Day 2 mock 어댑터 미구현이라 활성 X. `dialectic doctor`가 인증 누락 시 사용자에게 안내만 (`auth/login status` non-zero 출력). Day 3+ mock 어댑터 + `--mock <recording_dir>` + 자동 fallback 한 묶음으로 추가.
12. **`bus.read_all()` 매 턴 다중 호출 — N²/턴 read** — `run_turn`이 driver/reviewer 사이 `history = bus.read_all()` + reviewer 직전 다시 + run_session이 critique 추출 위해 또. Day 2 한 턴 E2E 범위는 영향 0 (라인 4~5 짧음), max-turns 확장 시 N² 누적. Day 3+에서 `Bus`에 in-memory cache 추가 또는 `run_turn`이 caller에게 history 누적 list 전달 패턴 검토.
13. **`_build_env`/`_safe_env` 화이트리스트 3 모듈 중복 — `src/_env.py` 분리 권고** — env_check + codex 어댑터 + claude 어댑터 모두 `_SYS_VARS`/`_AUTH_VARS` 동일 화이트리스트. 향후 mock 어댑터 추가 시 비대칭 위험. Day 2 본 plan은 narrative 권고만(§3.3 `_safe_env` docstring) — 작업 단위에 명시 X. 사용자 판단으로 본 plan 범위 또는 Day 3 plan 진입 시 단일 모듈로 분리.
14. **`AgentRunner` Protocol import 활용** — `from .agents.base import AgentAuthError, AgentRunner` 중 `AgentRunner`는 `_resolve_runner` 반환 타입 힌트 + `run_turn` keyword-only 인자 타입(`driver_runner: AgentRunner`)에 활용. 인터페이스 명세 강제 — code-conventions §5 Protocol 준수가 시그니처 차원에서 self-document.
