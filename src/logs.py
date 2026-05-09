"""`dialectic logs` 서브커맨드 구현 — `<workdir>/<UTC-ts>/messages.jsonl` 1차 인터페이스.

outline/03-ux.md §3.4 (산출물 구조 SSOT) + §3.5 (Q3 관찰성 narrative) 정합.
plan 011 Bug 2 fix 반영: session 격리 → 같은 workdir 내 N session 자동/명시 선택.

핵심 함수:
- `find_latest_session_dir()` — base_dir 우선순위 따라 자동 탐색 (2-tier mtime).
- `resolve_session_dir(user_workdir)` — 사용자 명시 --workdir 해석 (workdir/session 둘 다 수용).
- `format_summary(msg)` / `format_full(msg)` — 1줄 요약 / 본문 펼침.
- `render_logs(...)` — JSONL 한 줄씩 읽고 stdout 출력 (tail/follow/kind/full).

외부 의존성 0 — 표준 라이브러리만.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# session_ts 형식 = `%Y%m%dT%H%M%SZ` (`src/orchestrator.py:662` SSOT).
_SESSION_TS_PATTERN = re.compile(r"^\d{8}T\d{6}Z$")

# follow 모드 polling 간격 — outline §3.5 SSOT (250ms는 작성 시점 안.
# 실 구현은 0.5s 채택 — `tail -f` 표준 정합 + CPU 부담 최소화).
_FOLLOW_POLL_INTERVAL_S = 0.5


def _resolve_base_dir() -> Path | None:
    """base_dir 우선순위: DIALECTIC_RUNS_DIR > XDG_DATA_HOME/dialectic/runs > ~/.local/share/dialectic/runs.

    phase-c §1 표 SSOT 1:1. **첫 매칭 한 곳만** 검사 — 합집합 X (사용자 혼란 ↑).
    base_dir 미존재 시 None 반환.
    """
    runs_env = os.environ.get("DIALECTIC_RUNS_DIR")
    if runs_env:
        base = Path(runs_env)
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            base = Path(xdg) / "dialectic" / "runs"
        else:
            base = Path.home() / ".local" / "share" / "dialectic" / "runs"
    if not base.is_dir():
        return None
    return base


def _latest_child_dir(parent: Path) -> Path | None:
    """parent 직속 자식 폴더 중 mtime 최대 1건 반환. 자식 0 → None."""
    try:
        children = [p for p in parent.iterdir() if p.is_dir()]
    except OSError:
        return None
    if not children:
        return None
    return max(children, key=lambda p: p.stat().st_mtime)


def _latest_session_child(workdir: Path) -> Path | None:
    """workdir 직속 자식 중 `_SESSION_TS_PATTERN` 매칭 폴더 mtime 최대 1건 반환."""
    try:
        children = [
            p for p in workdir.iterdir()
            if p.is_dir() and _SESSION_TS_PATTERN.match(p.name)
        ]
    except OSError:
        return None
    if not children:
        return None
    return max(children, key=lambda p: p.stat().st_mtime)


def find_latest_session_dir() -> Path | None:
    """2-tier 자동 탐색: base_dir → 최신 workdir → 최신 session.

    base_dir 결정 우선순위 (phase-c §1 표 SSOT):
      DIALECTIC_RUNS_DIR env > XDG_DATA_HOME/dialectic/runs >
      ~/.local/share/dialectic/runs.
    **첫 매칭 base_dir 한 곳**만 검사 (합집합 X).

    탐색 절차:
      1. base_dir 미존재/빈 → None
      2. base_dir 직속 자식 폴더 mtime 최대 → workdir_dir
      3. workdir_dir 직속 자식 중 _SESSION_TS_PATTERN 매칭 폴더 mtime 최대 → session_dir
      4. session_dir/messages.jsonl 존재 시 session_dir 반환, 아니면 None
    반환: <base>/<workdir-id>/<UTC-ts>/ 폴더 (messages.jsonl 포함).
    """
    base = _resolve_base_dir()
    if base is None:
        return None
    workdir = _latest_child_dir(base)
    if workdir is None:
        return None
    session = _latest_session_child(workdir)
    if session is None:
        return None
    if not (session / "messages.jsonl").is_file():
        return None
    return session


def resolve_session_dir(user_workdir: Path) -> Path | None:
    """사용자 명시 --workdir 인자 해석 — workdir level 또는 session_dir 직접 지정 둘 다 수용.

    절차:
      1. user_workdir/messages.jsonl 존재 시 user_workdir 자체가 session_dir → 그대로 반환
      2. 없으면 user_workdir 직속 자식 중 _SESSION_TS_PATTERN 매칭 폴더 mtime 최대 → session_dir
      3. 매칭 폴더 0 → None (사용자에게 stderr 안내)
    """
    if (user_workdir / "messages.jsonl").is_file():
        return user_workdir
    session = _latest_session_child(user_workdir)
    if session is None:
        return None
    if not (session / "messages.jsonl").is_file():
        return None
    return session


def format_summary(msg: dict) -> str:
    """1줄 요약: [turn=N seq=M] kind=... from=... slot=...

    slot=None은 'slot=-' 출력. content는 포함 X.
    """
    turn = msg.get("turn_id")
    seq = msg.get("seq_in_turn")
    kind = msg.get("kind")
    from_ = msg.get("from")
    slot = msg.get("slot")
    slot_label = "-" if slot is None else slot
    return f"[turn={turn} seq={seq}] kind={kind} from={from_} slot={slot_label}"


def format_full(msg: dict) -> str:
    """본문 펼침: format_summary(msg) + '\\n' + msg['content']. 끝에 '---' 구분자 1줄.

    content가 멀티라인이면 그대로 출력 (truncate X).
    """
    content = msg.get("content", "")
    return f"{format_summary(msg)}\n{content}\n---"


def _parse_jsonl_lines(
    lines: list[str], *, source: Path, start_lineno: int = 1,
) -> list[dict]:
    """JSONL line list → dict list. malformed line은 stderr 1줄 경고 + skip.

    `src/bus.py:Bus.read_all()` 정책 정합 (P-JSONL skip + raw 보존).
    """
    out: list[dict] = []
    for offset, raw_line in enumerate(lines):
        lineno = start_lineno + offset
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            sys.stderr.write(
                f"[logs] {source}:{lineno} JSONDecodeError ({exc.msg}) — 라인 skip\n"
            )
            continue
        if not isinstance(payload, dict):
            sys.stderr.write(
                f"[logs] {source}:{lineno} 비-dict JSON — 라인 skip\n"
            )
            continue
        out.append(payload)
    return out


def render_logs(
    *,
    session_dir: Path,
    tail: int | None,
    follow: bool,
    kind_filter: str | None,
    full: bool,
) -> int:
    """session_dir/messages.jsonl(`outline/03-ux.md §3.4 SSOT`)에서 JSONL 한 줄씩 읽어 stdout 출력.

    - kind_filter 지정 시 msg.kind != filter는 skip.
    - tail N 지정 시 마지막 N개만 출력 (line 수 < N도 안전).
    - full=True면 format_full, 아니면 format_summary 사용.
    - follow=True면 EOF 도달 후 _FOLLOW_POLL_INTERVAL_S(0.5s) 폴링하며 새 line append 시 추가 출력.
      KeyboardInterrupt 시 stdout flush 후 return 0.
    - malformed JSONL line은 stderr 1줄 경고 (`bus.py:Bus.read_all` 정책 정합) + skip.
    - session_dir/messages.jsonl 미존재 시 stderr 경고 + return 1.
    반환: exit code (0 = 정상, 1 = 파일 미발견 또는 읽기 실패).
    """
    jsonl_path = session_dir / "messages.jsonl"
    if not jsonl_path.is_file():
        sys.stderr.write(f"[logs] {jsonl_path} 미존재\n")
        return 1

    formatter = format_full if full else format_summary

    def _emit(msg: dict) -> None:
        if kind_filter is not None and msg.get("kind") != kind_filter:
            return
        sys.stdout.write(formatter(msg) + "\n")

    try:
        raw_lines = jsonl_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        sys.stderr.write(f"[logs] {jsonl_path} 읽기 실패: {exc}\n")
        return 1

    initial_msgs = _parse_jsonl_lines(raw_lines, source=jsonl_path)

    # tail은 kind 필터 적용 후 마지막 N개 (사용자 직관 — "최근 critique 3개" 의도).
    if kind_filter is not None:
        filtered = [m for m in initial_msgs if m.get("kind") == kind_filter]
    else:
        filtered = initial_msgs
    if tail is not None and tail >= 0:
        filtered = filtered[-tail:] if tail > 0 else []

    for msg in filtered:
        sys.stdout.write(formatter(msg) + "\n")
    sys.stdout.flush()

    if not follow:
        return 0

    # follow: _FOLLOW_POLL_INTERVAL_S 폴링. tail 처리 후에도 follow 활성 시 EOF 이후 새 line만 emit.
    bytes_consumed = sum(len(line.encode("utf-8")) for line in raw_lines)
    pending = ""
    try:
        while True:
            try:
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    f.seek(bytes_consumed)
                    chunk = f.read()
            except OSError as exc:
                sys.stderr.write(f"[logs] {jsonl_path} follow 중 읽기 실패: {exc}\n")
                return 1
            if chunk:
                bytes_consumed += len(chunk.encode("utf-8"))
                pending += chunk
                # complete line 단위로만 parse (\n으로 끝나야 line 완성).
                if "\n" in pending:
                    complete, _, pending = pending.rpartition("\n")
                    new_lines = (complete + "\n").splitlines(keepends=True)
                    new_msgs = _parse_jsonl_lines(new_lines, source=jsonl_path)
                    for msg in new_msgs:
                        _emit(msg)
                    sys.stdout.flush()
            time.sleep(_FOLLOW_POLL_INTERVAL_S)
    except KeyboardInterrupt:
        sys.stdout.flush()
        return 0
