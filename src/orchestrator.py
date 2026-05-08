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
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .agents.base import ERROR_CONTENT_TRUNCATE_CHARS, AgentAuthError, AgentRunner
from .agents.claude import ClaudeRunner
from .agents.codex import CodexRunner
from .bus import Bus
from .patch_apply import apply_patches, extract_patches
from .schema import Message, Meta
from .ui import ROLE_LABEL_KO, VENDOR_LABEL, Spinner, print_message, stdin_canonical_off

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


def _serialize_history(history: list[Message]) -> str:
    """protocol.md §5 (`:246-260`) 형식. turn_id>=1만 포함 (turn_id=0 task는 §2 TASK 별도)."""
    body = [m for m in history if m.turn_id >= 1]
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


def build_prompt(role: str, task: str, history: list[Message], directive: str | None) -> str:
    """4섹션 prompt — protocol.md §5 (`:233-271`).

    role-specific instructions는 ROLE.md 본문에 이미 있으므로 prompt §4는 단순 재호출 +
    directive 강조 (protocol.md §5 line 257 — '당신의 역할({role})로 다음을 수행:').
    """
    role_md = ROLE_FILE[role].read_text(encoding="utf-8")
    # _serialize_history가 빈 body → "(이전 턴 없음)" 반환 — 외부 가드 중복 제거.
    history_md = _serialize_history(history)
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
) -> None:
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
            p1 = build_prompt(driver_role, task, history, directive=None)
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
        for turn in range(1, args.max_turns + 1):
            run_turn(
                turn, args.mode,
                driver_runner=driver_runner, reviewer_runner=reviewer_runner,
                bus=bus, task=args.task, workdir=workdir, sessions_dir=sessions_dir,
            )
            history_after = bus.read_all()
            # protocol.md §9 정합: 인증 실패 / 빈 응답 / parse 실패 등 error 발견 시 즉시 종료.
            # retry 1회 명세는 Day 3+ deferred (사용자 directive 기반 retry 정책 결정 후).
            # max_turns↑ 시 fatal error가 max-turns까지 반복되며 token 소모 차단.
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
            args.max_turns, "auto-end (max-turns reached)", workdir, args.mode,
            parent_id=last.msg_id,
        ))
        return 0
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
