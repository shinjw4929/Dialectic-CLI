"""Orchestrator — 한 턴 라이프사이클 (driver → reviewer) + run_session.

protocol.md §3 (`:196-211`, MODE_ROLES) / §4 (`:212-231`, 턴 라이프사이클) /
§5 (`:233-271`, 4섹션 prompt) / §7 (`:285-301`, cwd 격리) 정합.

- ts 형식: `datetime.now(tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')`
  (protocol.md §2 line 92, 정규식 `^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}Z$` 매치).
- DAG 무결성: task 메시지(turn_id=0)만 parent_id=None, 그 외 모두 직전 메시지 msg_id.
- frozen Meta — 어댑터 응답 meta 변경 X. critique convergence_streak 갱신은
  `dataclasses.replace(resp.meta, convergence_streak=...)`로 새 Meta 생성 (정직성).
"""

# imports — 표준 라이브러리만 (code-conventions.md §2 외부 의존성 0)
import argparse
import dataclasses
import itertools
import json
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .agents.base import ERROR_CONTENT_TRUNCATE_CHARS, AgentAuthError, AgentRunner
from .agents.claude import ClaudeRunner
from .agents.codex import CodexRunner
from .bus import Bus
from .patch_apply import apply_patches, extract_patches
from .schema import Message, Meta
from .ui import (
    ROLE_LABEL_KO,
    VENDOR_LABEL,
    Spinner,
    TriggerListener,
    print_message,
    prompt_decision,
    prompt_end_or_iterate,
    stdin_canonical_off,
)

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

# turn 내 최후 위치 명시 (driver=1, reviewer=2, user=3 다음 sentinel) — magic number 회피.
META_SEQ_SENTINEL = 99

# patch_applied 메시지의 seq_in_turn — proposal=1, reviewer=2 사이가 시간 순이지만
# seq=2는 reviewer와 충돌이라 META_SEQ_SENTINEL 직전(=98)에 배치. 직렬화 순서는
# proposal(1) → reviewer(2) → patch_applied(98)로 reviewer 뒤에 노출 (의도된 비대칭,
# 01-plan §5.6). 별도 상수로 의미 단위 명확.
META_PATCH_APPLIED_SEQ = 98

# decision 메시지의 seq_in_turn — proposal=1, critique=2, decision=97,
# patch_applied=98, meta=99 직렬화 순. 시간 순 ≠ 직렬화 순 (ADR-10 의도된 비대칭) —
# 사용자 직권 지시가 patch 내역보다 먼저 driver 다음 턴 prompt에 노출.
META_DECISION_SEQ = 97

# critical·full 모드 i 분기 무한 누적 방지 절대 상한 (모듈 상수, paste).
MAX_TURNS_HARD_CAP = 20

# subprocess 호출 timeout (code-conventions §3 — 명시 필수, 무한대 차단).
DEFAULT_TIMEOUT_S = 300


def SENTINEL_META(
    workdir: Path | str,
    vendor: str = "system",
    agent_cli: str = "system",
    latency_ms: int = 0,
    convergence_streak: int | None = None,
) -> Meta:
    """sentinel Meta 14 필드 일관 채움 — 13 default-없는 + 1 default convergence_streak.

    PEP 8 E731 회피로 lambda → def. 호출자(헬퍼 4종)가 본 함수로 시스템 sentinel 메시지의
    Meta를 생성. token 4종 0 + cost None + is_mock False (정직성).
    """
    return Meta(
        vendor=vendor, agent_cli=agent_cli,
        model=None, session_id=None, thread_id=None,
        input_tokens=0, output_tokens=0, cached_input_tokens=0, reasoning_output_tokens=0,
        cost_usd=None, latency_ms=latency_ms,
        is_mock=False, workdir=str(workdir),
        convergence_streak=convergence_streak,
    )


def _now_ts() -> str:
    """protocol.md §2 line 92 형식 1:1 — `2026-05-07T12:00:00.000Z`."""
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _detect_converged(text: str) -> bool:
    """outline/02 §2.9: reviewer 응답 마지막 비공백 줄이 정확히 '[CONVERGED]' 단독."""
    stripped = text.rstrip()
    last = stripped.splitlines()[-1] if stripped else ""
    return last.strip() == "[CONVERGED]"


def _serialize_history(
    history: list[Message],
    *,
    exclude_reviewer: bool = False,
) -> str:
    """protocol.md §5 (`:246-260`) 형식. turn_id>=1만 포함 (turn_id=0 task는 §2 TASK 별도).

    exclude_reviewer=True 시 m.kind == "critique" 메시지 제외 — full a 분기 시 driver
    응답 채택 후 다음 턴 prompt에서 reviewer critique를 history에서 제외하는 용도.
    default False라 기존 호출자 회귀 0.
    """
    body = [m for m in history if m.turn_id >= 1]
    if exclude_reviewer:
        body = [m for m in body if m.kind != "critique"]
    if not body:
        return "(이전 턴 없음)"
    body = sorted(body, key=lambda m: (m.turn_id, m.seq_in_turn))
    out: list[str] = []
    for turn_id, group in itertools.groupby(body, key=lambda m: m.turn_id):
        out.append(f"## Turn {turn_id}")
        for m in group:
            if m.kind == "decision":
                directive = m.directive or ""
                out.append(f'- USER (decision: {m.content}, directive: "{directive}")')
            elif m.from_ == "system":
                out.append(f"- SYSTEM ({m.kind}): {m.content}")
            else:
                out.append(f"- {m.from_.upper()} ({m.kind}): {m.content}")
        out.append("")
    return "\n".join(out).rstrip()


def build_prompt(
    role: str,
    task: str,
    history: list[Message],
    directive: str | None,
    *,
    exclude_reviewer: bool = False,
) -> str:
    """4섹션 prompt — protocol.md §5 (`:233-271`).

    role-specific instructions는 ROLE.md 본문에 이미 있으므로 prompt §4는 단순 재호출 +
    directive 강조 (protocol.md §5 line 257 — '당신의 역할({role})로 다음을 수행:').

    exclude_reviewer=True 시 _serialize_history에 전달 → 다음 턴 driver prompt에서
    reviewer critique 제외 (full a 분기 대응). default False 회귀 0.
    """
    role_md = ROLE_FILE[role].read_text(encoding="utf-8")
    # _serialize_history가 빈 body → "(이전 턴 없음)" 반환 — 외부 가드 중복 제거.
    history_md = _serialize_history(history, exclude_reviewer=exclude_reviewer)
    your_turn = (
        f"당신의 역할({role})로 위 ROLE 섹션의 책임을 수행하십시오. "
        f"§ '응답 전 셀프체크'의 모든 항목을 통과해야 응답이 유효합니다.\n\n"
        f"(directive: {directive or 'none'})"
    )
    return (
        f"# 1. ROLE\n{role_md}\n\n"
        f"# 2. TASK\n{task}\n\n"
        f"# 3. HISTORY\n{history_md}\n\n"
        f"# 4. YOUR TURN\n{your_turn}"
    )


def _msg(
    turn_id: int,
    seq_in_turn: int,
    role: str,
    slot: str,
    mode: str,
    kind: str,
    content: str,
    *,
    parent_id: str | None,
    meta: Meta,
) -> Message:
    """driver/reviewer 응답 메시지. 호출자가 변수 보존 → 다음 호출 parent_id."""
    return Message(
        ts=_now_ts(),
        msg_id=str(uuid4()),
        parent_id=parent_id,
        turn_id=turn_id,
        seq_in_turn=seq_in_turn,
        from_=role,
        to="broadcast",
        slot=slot,
        mode=mode,
        kind=kind,
        content=content,
        directive=None,
        meta=meta,
    )


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
    vendor: str = "system",
    agent_cli: str = "system",
    latency_ms: int = 0,
    response_meta: Meta | None = None,
) -> Message:
    """호출 실패 또는 빈 응답 메시지.

    response_meta 전달 시 token 4종 + cost + model + session_id/thread_id 보존
    (code-conventions.md §4 정직성). exception case는 SENTINEL_META fallback.
    """
    meta = response_meta if response_meta is not None else SENTINEL_META(
        workdir, vendor=vendor, agent_cli=agent_cli, latency_ms=latency_ms,
    )
    content = f"{type(exc).__name__}: {str(exc)[:ERROR_CONTENT_TRUNCATE_CHARS]}"
    return Message(
        ts=_now_ts(),
        msg_id=str(uuid4()),
        parent_id=parent_id,
        turn_id=turn_id,
        seq_in_turn=seq_in_turn,
        from_=role,
        to="broadcast",
        slot=slot,
        mode=mode,
        kind="error",
        content=content,
        directive=None,
        meta=meta,
    )


def _task_msg(task: str, mode: str, workdir: Path) -> Message:
    """첫 메시지 — turn_id=0, parent_id=None, kind=task."""
    return Message(
        ts=_now_ts(),
        msg_id=str(uuid4()),
        parent_id=None,
        turn_id=0,
        seq_in_turn=1,
        from_="system",
        to="broadcast",
        slot=None,
        mode=mode,
        kind="task",
        content=task,
        directive=None,
        meta=SENTINEL_META(workdir),
    )


def _meta_msg(
    turn_id: int,
    content: str,
    workdir: Path,
    mode: str,
    *,
    parent_id: str | None,
    convergence_streak: int | None = None,
) -> Message:
    """auto-end / auto_end_converged / budget_exceeded — kind=meta, seq=99."""
    return Message(
        ts=_now_ts(),
        msg_id=str(uuid4()),
        parent_id=parent_id,
        turn_id=turn_id,
        seq_in_turn=META_SEQ_SENTINEL,
        from_="system",
        to="broadcast",
        slot=None,
        mode=mode,
        kind="meta",
        content=content,
        directive=None,
        meta=SENTINEL_META(workdir, convergence_streak=convergence_streak),
    )


def _patch_applied_msg(
    turn_id: int,
    workdir: Path,
    mode: str,
    content: str,
    *,
    parent_id: str,
    apply_status: str,
    apply_error: str | None,
    files_changed: list[str],
) -> Message:
    """R2.7 patch_applied — from=system, slot=None, seq=98 (proposal=1, reviewer=2, meta=99 사이).

    content는 호출자(run_turn)가 만든 요약 문자열 — `_serialize_history`의 system 분기(:99-100)
    `SYSTEM (patch_applied): {content}` 형태로 driver 다음 턴 R1 prompt에 자연 피드백.
    호출자가 prefix를 `apply_status=...`로 명시하여 driver의 reviewer critique 오인 risk 차단
    (01-plan §5.6 (2) mitigation).

    meta는 SENTINEL_META(workdir) + dataclasses.replace로 apply_status/apply_error/files_changed
    3 필드 채움. patches는 proposal 측 책임 → None 유지.
    """
    base_meta = SENTINEL_META(workdir)
    meta = dataclasses.replace(
        base_meta,
        apply_status=apply_status,
        apply_error=apply_error,
        files_changed=files_changed,
    )
    return Message(
        ts=_now_ts(),
        msg_id=str(uuid4()),
        parent_id=parent_id,
        turn_id=turn_id,
        seq_in_turn=META_PATCH_APPLIED_SEQ,
        from_="system",
        to="broadcast",
        slot=None,
        mode=mode,
        kind="patch_applied",
        content=content,
        directive=None,
        meta=meta,
    )


def _decision_msg(
    turn_id: int,
    key: str,
    directive: str | None,
    workdir: Path,
    mode: str,
    *,
    parent_id: str | None,
) -> Message:
    """decision kind 메시지 helper (protocol.md:238 SSOT 재사용).

    필드:
      msg_id     = uuid4()
      from_      = "user", to = "implementer", slot = None
      seq_in_turn= META_DECISION_SEQ (=97). 직렬화 순: proposal=1 → critique=2 →
                   decision=97 → patch_applied=98 → meta=99. 시간 순 ≠ 직렬화 순,
                   ADR-10 의도된 비대칭 — `_serialize_history` sort 정합. 사용자 직권
                   지시가 patch 내역보다 먼저 driver 다음 턴 prompt에 노출.
      kind       = "decision" (재사용 — `user_synthesis` 신설 폐기, schema kind 표 유지)
      content    = key (outline §3.3 a/r/m/i/e/s)
      directive  = directive 본문 또는 None
      meta       = vendor="user", agent_cli="user", model=None, tokens 4종 0,
                   cost_usd=None, latency_ms=0, is_mock=False
    """
    return Message(
        ts=_now_ts(),
        msg_id=str(uuid4()),
        parent_id=parent_id,
        turn_id=turn_id,
        seq_in_turn=META_DECISION_SEQ,
        from_="user",
        to="implementer",
        slot=None,
        mode=mode,
        kind="decision",
        content=key,
        directive=directive,
        meta=Meta(
            vendor="user",
            agent_cli="user",
            model=None,
            session_id=None,
            thread_id=None,
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=0,
            reasoning_output_tokens=0,
            cost_usd=None,
            latency_ms=0,
            is_mock=False,
            workdir=str(workdir),
        ),
    )


def _last_critique_msg_id(history: list[Message]) -> str | None:
    """history 역방향 탐색 — 마지막 critique kind msg_id (없으면 None)."""
    for m in reversed(history):
        if m.kind == "critique":
            return m.msg_id
    return None


def _last_proposal_msg_id(history: list[Message]) -> str | None:
    """history 역방향 탐색 — 마지막 proposal kind msg_id (full s 분기 fallback).

    skip_reviewer 직후 critique 부재 → parent_id를 proposal로 fallback.
    """
    for m in reversed(history):
        if m.kind == "proposal":
            return m.msg_id
    return None


def _setup_sigint_handler(listener: TriggerListener) -> Callable | int | None:
    """SIGINT 핸들러 등록 (phase-b R3 hand-off).

    abort 시 listener __exit__로 raw mode 복원 + sys.exit(130) (POSIX SIGINT 표준 종료
    코드). 반환값 = `signal.signal` 시그니처상 Callable | int (SIG_DFL/SIG_IGN sentinel)
    | None (핸들러 부재). caller가 with 블록 종료 시 `signal.signal(SIGINT, prev)` 복원.
    """

    def _handler(signum: int, frame: object) -> None:
        try:
            listener.__exit__(None, None, None)
        finally:
            sys.exit(130)

    prev = signal.signal(signal.SIGINT, _handler)
    return prev


def _resolve_runner(name: str) -> AgentRunner:
    """codex/claude 어댑터 인스턴스 반환. mock은 Day 3+. invalid name은 친절 ValueError."""
    runners: dict[str, AgentRunner] = {"codex": CodexRunner(), "claude": ClaudeRunner()}
    if name not in runners:
        raise ValueError(
            f"unknown driver/reviewer: {name!r} — choices: {sorted(runners)}. "
            f"mock 어댑터는 Day 3+ 추가 예정."
        )
    return runners[name]


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
    skip_reviewer: bool = False,
    exclude_reviewer_history: bool = False,
) -> None:
    """기존 driver→reviewer 1턴 라이프사이클.

    skip_reviewer=True (full s 분기) → reviewer 호출 skip. critique 메시지 미생성.
    exclude_reviewer_history=True (full a 분기) → driver build_prompt 호출 시
    history에서 critique 제외. default False 회귀 0.
    """
    # 본 turn 시작 시 history snapshot — turn_id < N 메시지만. driver는 본 history,
    # reviewer는 history + 본 turn proposal (driver 응답 후 bus 재read).
    # protocol.md §5 line 250 "turn_id < N" 명세는 driver 한정 — reviewer는 turn N의
    # proposal까지 봐야 critique 가능 (의미적 정합).
    # 성능 주의: 매 턴 bus.read_all() 다회 호출 (history + reviewer history + last_critique
    # + fallthrough last). 단일 프로세스 한 턴 E2E에선 무해, max_turns↑ 시 in-memory cache 검토.
    history = bus.read_all()
    last_msg_id = history[-1].msg_id if history else None
    roles = MODE_ROLES[mode]

    # ---- driver ----
    driver_role = roles["driver"]
    raw1 = sessions_dir / f"{turn_id}-driver-{uuid4().hex[:8]}.jsonl"
    # build_prompt를 try 안으로 — role.md 부재(FileNotFoundError) / 디코딩 실패(UnicodeDecodeError) /
    # 권한(PermissionError → OSError) 누수 차단 (C-007 패턴). catch 튜플 확장 (C-005).
    driver_label = ROLE_LABEL_KO.get(driver_role, driver_role)
    driver_vendor = VENDOR_LABEL.get(driver_runner.name, driver_runner.name)
    driver_spinner_msg = f"[{driver_label}: {driver_vendor}] running..."
    try:
        # stdin_canonical_off + Spinner: 호출 동안 사용자 키 누름이 다음 prompt에 누수되는
        # 결함 차단 (line discipline off + drain thread + INTR 보존). 자세히는 src/ui.py.
        with stdin_canonical_off(), Spinner(driver_spinner_msg):
            p1 = build_prompt(
                driver_role, task, history, directive=None,
                exclude_reviewer=exclude_reviewer_history,
            )
            resp1 = driver_runner.run(p1, raw_log_path=raw1, timeout_s=DEFAULT_TIMEOUT_S, workdir=workdir)
    except (
        subprocess.TimeoutExpired, json.JSONDecodeError, AgentAuthError,
        FileNotFoundError, OSError, UnicodeDecodeError, ValueError,
    ) as e:
        bus.append(_error_msg(
            turn_id, 1, driver_role, "driver", mode, e, workdir,
            parent_id=last_msg_id,
            vendor=driver_runner.vendor, agent_cli=driver_runner.name,
            latency_ms=DEFAULT_TIMEOUT_S * 1000 if isinstance(e, subprocess.TimeoutExpired) else 0,
        ))
        return

    if not resp1.text.strip():  # whitespace-only도 빈 응답으로 환원
        # 빈 응답 — Day 2 retry 생략, response_meta 전달로 token·latency·cost 모두 보존.
        # stderr_excerpt(어댑터 비정상 종료 시 채움)를 ValueError 메시지에 합성 — protocol.md §9
        # "content=<stderr 발췌>" 정합 (P-STDERR_LOSS).
        exc = ValueError(
            f"empty_response | stderr: {resp1.stderr_excerpt}" if resp1.stderr_excerpt
            else "empty_response"
        )
        bus.append(_error_msg(
            turn_id, 1, driver_role, "driver", mode, exc, workdir,
            parent_id=last_msg_id, response_meta=resp1.meta,
        ))
        return

    # R2.6/R2.7 — protocol.md §4 line 232-235. patch 0개면 분기 skip (노이즈 차단).
    patches = extract_patches(resp1.text)
    proposal_meta = dataclasses.replace(resp1.meta, patches=patches or None)
    proposal = _msg(
        turn_id, 1, driver_role, "driver", mode, "proposal",
        resp1.text, parent_id=last_msg_id, meta=proposal_meta,
    )
    bus.append(proposal)
    print_message(
        role_label=ROLE_LABEL_KO.get(driver_role, driver_role),
        vendor_label=VENDOR_LABEL.get(driver_runner.name, driver_runner.name),
        kind="proposal",
        text=resp1.text,
        meta=proposal_meta,
    )

    if patches:
        status, error, files_changed = apply_patches(patches, workdir=workdir)
        summary = (
            f"apply_status=ok, files_changed={files_changed}"
            if status == "ok"
            else f"apply_status=failed, apply_error={error}"
        )
        bus.append(_patch_applied_msg(
            turn_id, workdir, mode, summary,
            parent_id=proposal.msg_id,
            apply_status=status,
            apply_error=error,
            files_changed=files_changed,
        ))

    # ---- reviewer ----
    # full s 분기 시 skip_reviewer=True → reviewer 호출 skip + critique 미생성.
    # 다음 턴 parent_id는 _last_proposal_msg_id fallback (run_session에서 분기).
    if skip_reviewer:
        return

    reviewer_role = roles["reviewer"]
    raw2 = sessions_dir / f"{turn_id}-reviewer-{uuid4().hex[:8]}.jsonl"
    reviewer_label = ROLE_LABEL_KO.get(reviewer_role, reviewer_role)
    reviewer_vendor = VENDOR_LABEL.get(reviewer_runner.name, reviewer_runner.name)
    reviewer_spinner_msg = f"[{reviewer_label}: {reviewer_vendor}] running..."
    try:
        # stdin_canonical_off + Spinner: driver와 동일 — 호출 동안 stdin 누수 차단.
        with stdin_canonical_off(), Spinner(reviewer_spinner_msg):
            p2 = build_prompt(reviewer_role, task, bus.read_all(), directive=None)
            resp2 = reviewer_runner.run(p2, raw_log_path=raw2, timeout_s=DEFAULT_TIMEOUT_S, workdir=workdir)
    except (
        subprocess.TimeoutExpired, json.JSONDecodeError, AgentAuthError,
        FileNotFoundError, OSError, UnicodeDecodeError, ValueError,
    ) as e:
        bus.append(_error_msg(
            turn_id, 2, reviewer_role, "reviewer", mode, e, workdir,
            parent_id=proposal.msg_id,
            vendor=reviewer_runner.vendor, agent_cli=reviewer_runner.name,
            latency_ms=DEFAULT_TIMEOUT_S * 1000 if isinstance(e, subprocess.TimeoutExpired) else 0,
        ))
        return

    if not resp2.text.strip():  # whitespace-only도 빈 응답으로 환원
        # stderr_excerpt 합성 — protocol.md §9 정합 (P-STDERR_LOSS).
        exc = ValueError(
            f"empty_response | stderr: {resp2.stderr_excerpt}" if resp2.stderr_excerpt
            else "empty_response"
        )
        bus.append(_error_msg(
            turn_id, 2, reviewer_role, "reviewer", mode, exc, workdir,
            parent_id=proposal.msg_id, response_meta=resp2.meta,
        ))
        return

    # outline/02 §2.9: 마커 감지 → critique meta.convergence_streak에 1 또는 None.
    is_converged = _detect_converged(resp2.text)
    critique_meta = dataclasses.replace(
        resp2.meta, convergence_streak=1 if is_converged else None,
    )
    critique = _msg(
        turn_id, 2, reviewer_role, "reviewer", mode, "critique",
        resp2.text, parent_id=proposal.msg_id, meta=critique_meta,
    )
    bus.append(critique)
    print_message(
        role_label=ROLE_LABEL_KO.get(reviewer_role, reviewer_role),
        vendor_label=VENDOR_LABEL.get(reviewer_runner.name, reviewer_runner.name),
        kind="critique",
        text=resp2.text,
        meta=critique_meta,
    )


def run_session(args: argparse.Namespace) -> int:
    # Path.resolve() — symlink·상대경로 해소, Meta.workdir이 항상 절대 정규 경로.
    workdir = (Path(args.workdir).resolve() if args.workdir
               else Path(tempfile.mkdtemp(prefix="dialectic-")).resolve())
    # cleanup 정책: --workdir 미지정 시에도 결과 보존 (사용자가 messages.jsonl 확인 가능).
    # mkdtemp 누적은 사용자 책임 (`/tmp/dialectic-*` 주기 정리). Day 3+ `--cleanup-workdir` 토글 검토.
    cleanup = False

    # ADR-6 우회 차단: --workdir이 Dialectic-CLI repo 루트 OR 그 하위 경로일 때 종료.
    # claude/codex가 cwd부터 부모 dir까지 CLAUDE.md/AGENTS.md auto-discovery하므로
    # repo_root/src, repo_root/plan, repo_root/docs 등 하위 cwd도 부모 검색 시 개발용 .md 누수.
    # mkdtemp가 TMPDIR=repo 하위 edge에서 생성한 임시 dir도 leak 차단 (cleanup 후 SystemExit).
    DIALECTIC_REPO_ROOT = Path(__file__).resolve().parent.parent
    if workdir == DIALECTIC_REPO_ROOT or DIALECTIC_REPO_ROOT in workdir.parents:
        if cleanup:
            shutil.rmtree(workdir, ignore_errors=True)  # mkdtemp leak 차단 (C-008)
        raise SystemExit(
            f"--workdir이 Dialectic-CLI repo 루트 또는 그 하위 경로({workdir})입니다 (ADR-6). "
            f"claude/codex가 부모 dir auto-discovery로 개발용 CLAUDE.md/AGENTS.md를 "
            f"런타임 prompt에 누수합니다. 별도 경로를 지정하거나 --workdir 미지정으로 "
            f"임시 dir 자동 생성을 사용하십시오."
        )

    # ADR-9 (outline/02 §2.9): --max-turns < K+1 시 K=1 자동 fallback.
    K = args.convergence_streak
    if args.max_turns < K + 1 and K > 1:
        sys.stderr.write(
            f"--max-turns ({args.max_turns}) < --convergence-streak + 1 ({K + 1}) — "
            f"K reduced to 1 (ADR-9, outline/02 §2.9)\n"
        )
        K = 1

    # 초기값 가드 (P1-ε): args.max_turns가 hard cap 초과 시 clamp + stderr 경고.
    # critical/full i 분기 동적 +1 누적 안전망과 별개로 사용자 입력 시점 차단.
    max_turns_runtime = min(args.max_turns, MAX_TURNS_HARD_CAP)
    if args.max_turns > MAX_TURNS_HARD_CAP:
        sys.stderr.write(
            f"--max-turns ({args.max_turns}) > MAX_TURNS_HARD_CAP "
            f"({MAX_TURNS_HARD_CAP}) — clamped\n"
        )

    # mock 모드 fallback (P-MOCK 괄호 명시): mock 어댑터는 raw 키 stdin 처리 X →
    # critical/full 잠재 prompt와 비호환. 현재 _resolve_runner에 mock 미등록 (plan 007
    # deferred)이라 vacuous narrative — `args.driver=="mock"` 자체가 ValueError raise
    # 시점. plan 007 진입 후 활성.
    mock_in_use = (args.driver == "mock") or (args.reviewer == "mock")
    interactive_in = args.interactive in ("critical", "full")
    if mock_in_use and interactive_in:
        sys.stderr.write(
            "mock 모드는 critical/full 비호환 — end-only 강제 (P-MOCK)\n"
        )
        args.interactive = "end-only"

    try:
        logs_dir = workdir / "logs"
        sessions_dir = logs_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        bus = Bus(logs_dir / "messages.jsonl")
        bus.append(_task_msg(args.task, args.mode, workdir))

        driver_runner = _resolve_runner(args.driver)
        reviewer_runner = _resolve_runner(args.reviewer)

        # outline/02 §2.9: reviewer [CONVERGED] streak K 도달 시 auto_end_converged.
        streak = 0

        if args.interactive == "end-only":
            return _run_session_end_only(
                args, K, max_turns_runtime, bus,
                driver_runner, reviewer_runner, workdir, sessions_dir,
            )

        if args.interactive == "critical":
            return _run_session_critical(
                args, K, max_turns_runtime, bus,
                driver_runner, reviewer_runner, workdir, sessions_dir,
            )

        if args.interactive == "full":
            return _run_session_full(
                args, K, max_turns_runtime, bus,
                driver_runner, reviewer_runner, workdir, sessions_dir,
            )

        # 알 수 없는 interactive 값 — argparse choices가 차단하지만 방어.
        raise ValueError(
            f"unknown --interactive: {args.interactive!r} — "
            f"expected one of ('end-only', 'critical', 'full')"
        )
    finally:
        if cleanup:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            # 사용자에게 workdir + messages.jsonl 경로 안내 — 결과 확인 통로.
            sys.stderr.write(
                f"\n[run_session] workdir 보존: {workdir}\n"
                f"  messages.jsonl: {workdir}/logs/messages.jsonl\n"
                f"  raw streams:    {workdir}/logs/sessions/\n"
            )


def _run_session_end_only(
    args: argparse.Namespace,
    K: int,
    max_turns_runtime: int,
    bus: Bus,
    driver_runner: AgentRunner,
    reviewer_runner: AgentRunner,
    workdir: Path,
    sessions_dir: Path,
) -> int:
    """end-only mode — 자동 dialectic, 사용자 prompt 0. AS-IS for-range 패턴 유지."""
    streak = 0
    for turn in range(1, max_turns_runtime + 1):
        run_turn(
            turn, args.mode,
            driver_runner=driver_runner, reviewer_runner=reviewer_runner,
            bus=bus, task=args.task, workdir=workdir, sessions_dir=sessions_dir,
        )
        history_after = bus.read_all()
        last_msg = history_after[-1]
        if last_msg.kind == "error" and last_msg.turn_id == turn:
            bus.append(_meta_msg(
                turn, f"auto-end (error: {last_msg.content[:80]})", workdir, args.mode,
                parent_id=last_msg.msg_id,
            ))
            return 0
        last_critique = next(
            (m for m in reversed(history_after)
             if m.kind == "critique" and m.turn_id == turn),
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

    # max-turns 도달 fallthrough.
    last = bus.read_all()[-1]
    bus.append(_meta_msg(
        max_turns_runtime, "auto-end (max-turns reached)", workdir, args.mode,
        parent_id=last.msg_id,
    ))
    return 0


def _run_session_critical(
    args: argparse.Namespace,
    K: int,
    max_turns_runtime: int,
    bus: Bus,
    driver_runner: AgentRunner,
    reviewer_runner: AgentRunner,
    workdir: Path,
    sessions_dir: Path,
) -> int:
    """critical mode — 매 turn cleanup-restart pattern.

    매 turn 새 TriggerListener 인스턴스 (with 컨텍스트). __exit__ 시 thread 종료 +
    raw mode 복원 → prompt 진행 (canonical mode이라 사용자 byte 절도 race 0).
    idle window (prompt 끝 ~ 다음 turn listener 시작)는 "Ctrl+F 2회 연타" narrative cover.

    α 정책: trigger/converged/last_turn 모든 i = +1 단순 누적.
    c 분기: 실수 trigger 취소 (trigger 단독만 c 노출).
    옵션 분기:
      trigger 단독 → Y/c/텍스트 (n 미노출)
      CONVERGED/last_turn → Y/n/텍스트 (c 미노출)
    """
    streak = 0
    turn = 1
    while turn <= max_turns_runtime:
        with TriggerListener() as trigger:
            prev_handler = _setup_sigint_handler(trigger)
            try:
                run_turn(
                    turn, args.mode,
                    driver_runner=driver_runner, reviewer_runner=reviewer_runner,
                    bus=bus, task=args.task, workdir=workdir, sessions_dir=sessions_dir,
                )
            finally:
                signal.signal(signal.SIGINT, prev_handler)
        # listener __exit__ — raw mode 복원 + thread 종료. 이후 canonical mode이라
        # 사용자 byte 절도 race 0. trigger.is_set()은 이미 발동된 상태로 보존됨.
        history_after = bus.read_all()
        last_msg = history_after[-1]
        if last_msg.kind == "error" and last_msg.turn_id == turn:
            bus.append(_meta_msg(
                turn, f"auto-end (error: {last_msg.content[:80]})", workdir, args.mode,
                parent_id=last_msg.msg_id,
            ))
            return 0
        last_critique = next(
            (m for m in reversed(history_after)
             if m.kind == "critique" and m.turn_id == turn),
            None,
        )
        converged_now = False
        if last_critique is not None:
            if last_critique.meta.convergence_streak == 1:
                streak += 1
                if streak >= K:
                    converged_now = True
            else:
                streak = 0
        else:
            streak = 0

        last_turn_now = (turn == max_turns_runtime)
        triggered = trigger.is_set()
        should_prompt = triggered or converged_now or last_turn_now
        if should_prompt:
            if converged_now:
                reason = f"[CONVERGED] streak {K} 도달"
            elif last_turn_now:
                reason = f"max-turns {max_turns_runtime} 도달"
            else:
                reason = "Ctrl+F 트리거"
            allow_continue = triggered and not (converged_now or last_turn_now)
            allow_iterate_no_directive = converged_now or last_turn_now
            key, directive = prompt_end_or_iterate(
                turn_id=turn, reason=reason,
                allow_continue=allow_continue,
                allow_iterate_no_directive=allow_iterate_no_directive,
            )
            parent_id = _last_critique_msg_id(history_after) or history_after[-1].msg_id
            if key == "e":
                bus.append(_meta_msg(
                    turn, "auto_end_user", workdir, args.mode,
                    parent_id=parent_id,
                ))
                return 0
            if key == "c":
                # 실수 trigger 취소 — max_turns 변경 X, decision append X.
                # converged 무한 루프 차단 위해 streak = 0.
                streak = 0
            if key == "i":
                bus.append(_decision_msg(
                    turn, "i", directive, workdir, args.mode,
                    parent_id=parent_id,
                ))
                max_turns_runtime += 1   # α 정책
                streak = 0
                if max_turns_runtime > MAX_TURNS_HARD_CAP:
                    bus.append(_meta_msg(
                        turn,
                        f"auto_end_hard_cap (max_turns_runtime > {MAX_TURNS_HARD_CAP})",
                        workdir, args.mode, parent_id=parent_id,
                    ))
                    return 0
        turn += 1

    # while 탈출 — last_turn_now에서 e 선택했으면 위 return. c + last_turn_now 시
    # turn += 1로 while False → fallthrough → max-turns reached.
    last = bus.read_all()[-1]
    bus.append(_meta_msg(
        max_turns_runtime, "auto-end (max-turns reached)", workdir, args.mode,
        parent_id=last.msg_id,
    ))
    return 0


def _run_session_full(
    args: argparse.Namespace,
    K: int,
    max_turns_runtime: int,
    bus: Bus,
    driver_runner: AgentRunner,
    reviewer_runner: AgentRunner,
    workdir: Path,
    sessions_dir: Path,
) -> int:
    """full mode — 매 턴 끝 prompt_decision (6지선다 a/r/m/i/e/s).

    listener 가동 X — 매 턴 prompt 자동. 분기:
      a → 다음 턴 driver build_prompt에 exclude_reviewer=True (reviewer critique 제외)
      r → directive 자동 주입 (사용자 입력 우선, 없으면 last_critique.content[:200])
      m → 현재 동작 (둘 다 history)
      i → max_turns_runtime += 1 (α 정책) + streak 리셋 + hard_cap 가드
      e → auto_end_user
      s → 다음 턴 reviewer 호출 skip
    """
    streak = 0
    turn = 1
    skip_reviewer_next = False
    exclude_reviewer_history_next = False
    while turn <= max_turns_runtime:
        run_turn(
            turn, args.mode,
            driver_runner=driver_runner, reviewer_runner=reviewer_runner,
            bus=bus, task=args.task, workdir=workdir, sessions_dir=sessions_dir,
            skip_reviewer=skip_reviewer_next,
            exclude_reviewer_history=exclude_reviewer_history_next,
        )
        history_after = bus.read_all()
        last_msg = history_after[-1]
        if last_msg.kind == "error" and last_msg.turn_id == turn:
            bus.append(_meta_msg(
                turn, f"auto-end (error: {last_msg.content[:80]})", workdir, args.mode,
                parent_id=last_msg.msg_id,
            ))
            return 0

        # parent_id 결정 — reset 이전 (P1-새-2 dead code fix).
        if skip_reviewer_next:
            parent_id = _last_proposal_msg_id(history_after) or history_after[-1].msg_id
        else:
            parent_id = _last_critique_msg_id(history_after) or history_after[-1].msg_id
        skip_reviewer_next = False
        exclude_reviewer_history_next = False

        key, raw_directive = prompt_decision(turn_id=turn, interactive_mode="full")

        # full r 분기 directive 자동 주입 (β inline — `_summarize_critique` helper 폐기).
        # raw_directive 빈 입력 시만 last_critique.content[:200] 자동 주입. 사용자 우선.
        if key == "r" and not raw_directive:
            last_critique = next(
                (m for m in reversed(history_after) if m.kind == "critique"),
                None,
            )
            if last_critique is not None:
                raw_directive = (
                    f"이전 턴 reviewer 비판 강조 채택: "
                    f"{last_critique.content[:200]}"
                )

        bus.append(_decision_msg(
            turn, key, raw_directive, workdir, args.mode,
            parent_id=parent_id,
        ))

        if key == "a":
            exclude_reviewer_history_next = True
        elif key == "r":
            pass  # decision_msg는 위에서 append 완료 (directive 보존)
        elif key == "m":
            pass  # 현재 동작 (둘 다 history)
        elif key == "i":
            max_turns_runtime += 1
            streak = 0
            if max_turns_runtime > MAX_TURNS_HARD_CAP:
                bus.append(_meta_msg(
                    turn,
                    f"auto_end_hard_cap (max_turns_runtime > {MAX_TURNS_HARD_CAP})",
                    workdir, args.mode, parent_id=parent_id,
                ))
                return 0
        elif key == "e":
            bus.append(_meta_msg(
                turn, "auto_end_user", workdir, args.mode,
                parent_id=parent_id,
            ))
            return 0
        elif key == "s":
            skip_reviewer_next = True
        turn += 1

    # max-turns 도달 fallthrough.
    last = bus.read_all()[-1]
    bus.append(_meta_msg(
        max_turns_runtime, "auto-end (max-turns reached)", workdir, args.mode,
        parent_id=last.msg_id,
    ))
    return 0
