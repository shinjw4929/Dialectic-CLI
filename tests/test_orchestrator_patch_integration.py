"""orchestrator R2.6/R2.7 통합 — extract → apply → patch_applied append.

phase-c §3.2 (P1-X2 fix) 정합. 가짜 AgentRunner 주입으로 codex/claude CLI 부재 환경에서
run_turn driver/reviewer 분기 + patch_apply 통합 동작 검증.

회귀 가드 (01-plan §5.6):
- (1) `critique.seq_in_turn == 2` + `patch_applied.seq_in_turn == 98` — seq 변경 즉시 fail
- (2) `patch_applied.content.startswith("apply_status=")` — driver 오인 차단 prefix 검증
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# repo root sys.path — `from src.orchestrator import ...` 직접 사용
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.agents.base import AgentResponse  # noqa: E402
from src.bus import Bus  # noqa: E402
from src.orchestrator import SENTINEL_META, run_turn  # noqa: E402


# ─── 가짜 AgentRunner ──────────────────────────────────────────────────────────


@dataclass
class _FakeRunner:
    """AgentRunner Protocol 준수 — codex/claude 어댑터 우회용 stub."""
    name: str
    vendor: str
    text: str

    def run(
        self,
        prompt: str,
        *,
        raw_log_path: Path,
        timeout_s: int,
        workdir: Path,
    ) -> AgentResponse:
        # raw_log_path는 실제 파일을 만들지 않아도 무방 (orchestrator는 read 0)
        return AgentResponse(
            text=self.text,
            raw_path=raw_log_path,
            meta=SENTINEL_META(workdir, vendor=self.vendor, agent_cli=self.name),
            stderr_excerpt=None,
        )


def _setup_workdir(tmp_path: Path) -> tuple[Path, Path, Path]:
    """workdir + sessions_dir + messages.jsonl 경로 준비."""
    workdir = tmp_path / "wd"
    workdir.mkdir()
    sessions_dir = workdir / "logs" / "sessions"
    sessions_dir.mkdir(parents=True)
    bus_path = workdir / "logs" / "messages.jsonl"
    return workdir, sessions_dir, bus_path


# ─── case 1: happy path ────────────────────────────────────────────────────────


def test_run_turn_applies_patch_and_appends_patch_applied(tmp_path):
    """driver 응답에 patch 1 블록 → workdir 파일 변경 + patch_applied seq=98 + critique seq=2."""
    workdir, sessions_dir, bus_path = _setup_workdir(tmp_path)
    target = workdir / "target.py"
    target.write_text("hello world\n", encoding="utf-8")

    driver_text = (
        "여기 patch입니다.\n"
        "FILE: target.py\n"
        "<<<<<<< SEARCH\n"
        "hello world\n"
        "=======\n"
        "hello dialectic\n"
        ">>>>>>> REPLACE\n"
        "끝.\n"
    )
    reviewer_text = "looks good\n[CONVERGED]"

    bus = Bus(bus_path)
    run_turn(
        turn_id=1, mode="run",
        driver_runner=_FakeRunner(name="codex", vendor="openai", text=driver_text),
        reviewer_runner=_FakeRunner(name="claude", vendor="anthropic", text=reviewer_text),
        bus=bus, task="x", workdir=workdir, sessions_dir=sessions_dir,
    )

    msgs = bus.read_all()
    # proposal(seq=1) + patch_applied(seq=98) + critique(seq=2) — 3 라인
    assert len(msgs) == 3
    proposal = next(m for m in msgs if m.kind == "proposal")
    patch_applied = next(m for m in msgs if m.kind == "patch_applied")
    critique = next(m for m in msgs if m.kind == "critique")

    # §5.6 (1) seq 회귀 가드
    assert proposal.seq_in_turn == 1
    assert critique.seq_in_turn == 2
    assert patch_applied.seq_in_turn == 98

    # §5.6 (2) prefix 가드
    assert patch_applied.content.startswith("apply_status=")

    # workdir 파일이 REPLACE로 치환됨 (utf-8 명시)
    assert target.read_text(encoding="utf-8") == "hello dialectic\n"

    # proposal.meta.patches — 1 dict
    assert proposal.meta.patches is not None
    assert len(proposal.meta.patches) == 1
    assert proposal.meta.patches[0]["file"] == "target.py"
    assert proposal.meta.patches[0]["search"] == "hello world"
    assert proposal.meta.patches[0]["replace"] == "hello dialectic"

    # patch_applied.meta.apply_status / files_changed
    assert patch_applied.meta.apply_status == "ok"
    assert patch_applied.meta.apply_error is None
    assert patch_applied.meta.files_changed == ["target.py"]
    assert patch_applied.from_ == "system"
    assert patch_applied.slot is None


# ─── case 2: traversal failure ─────────────────────────────────────────────────


def test_run_turn_patch_traversal_failure_records_error(tmp_path):
    """driver 응답이 workdir 외부 경로 → apply_status=failed + workdir 파일 미변경."""
    workdir, sessions_dir, bus_path = _setup_workdir(tmp_path)
    target = workdir / "target.py"
    target.write_text("untouched\n", encoding="utf-8")

    driver_text = (
        "FILE: ../etc/passwd\n"
        "<<<<<<< SEARCH\n"
        "root\n"
        "=======\n"
        "pwned\n"
        ">>>>>>> REPLACE\n"
    )
    reviewer_text = "noted\n[CONVERGED]"

    bus = Bus(bus_path)
    run_turn(
        turn_id=1, mode="run",
        driver_runner=_FakeRunner(name="codex", vendor="openai", text=driver_text),
        reviewer_runner=_FakeRunner(name="claude", vendor="anthropic", text=reviewer_text),
        bus=bus, task="x", workdir=workdir, sessions_dir=sessions_dir,
    )

    msgs = bus.read_all()
    patch_applied = next(m for m in msgs if m.kind == "patch_applied")

    assert patch_applied.meta.apply_status == "failed"
    assert patch_applied.meta.apply_error is not None
    assert "path outside workdir" in patch_applied.meta.apply_error
    assert patch_applied.meta.files_changed == []

    # content prefix 가드 (failed branch)
    assert patch_applied.content.startswith("apply_status=failed")

    # workdir 파일 미변경
    assert target.read_text(encoding="utf-8") == "untouched\n"
