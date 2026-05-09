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


# ─── case 3: no_fence (proposal에 fence 0건) ───────────────────────────────────


def test_run_turn_no_fence_records_no_fence_status(tmp_path):
    """driver 응답에 search-replace 마커 0건 → patch_applied seq=98 + apply_status=no_fence.

    silent skip 차단 (이전 동작은 if patches: 분기 통째로 건너뛰어 메시지 미발행).
    fix 후에는 proposal 직후 항상 patch_applied 발행 — driver R1 prompt 자가 교정 채널 복구.
    """
    workdir, sessions_dir, bus_path = _setup_workdir(tmp_path)
    target = workdir / "target.py"
    target.write_text("untouched\n", encoding="utf-8")

    driver_text = "코드 없이 spec만 정리합니다.\n## 요약\nN/A — 구현 없음.\n"
    reviewer_text = "spec ok\n[CONVERGED]"

    bus = Bus(bus_path)
    run_turn(
        turn_id=1, mode="implement",
        driver_runner=_FakeRunner(name="codex", vendor="openai", text=driver_text),
        reviewer_runner=_FakeRunner(name="claude", vendor="anthropic", text=reviewer_text),
        bus=bus, task="x", workdir=workdir, sessions_dir=sessions_dir,
    )

    msgs = bus.read_all()
    # proposal(1) + patch_applied(98) + critique(2) — 3 라인. fence 0건이라도 patch_applied 자리 보존.
    assert len(msgs) == 3
    proposal = next(m for m in msgs if m.kind == "proposal")
    patch_applied = next(m for m in msgs if m.kind == "patch_applied")
    critique = next(m for m in msgs if m.kind == "critique")

    assert proposal.seq_in_turn == 1
    assert critique.seq_in_turn == 2
    assert patch_applied.seq_in_turn == 98

    # proposal.meta.patches는 None (fence 0건 → extract 결과 [] → None 환원)
    assert proposal.meta.patches is None

    # patch_applied — no_fence
    assert patch_applied.meta.apply_status == "no_fence"
    assert patch_applied.meta.apply_error == "no FILE: marker found in proposal"
    assert patch_applied.meta.files_changed == []
    assert patch_applied.from_ == "system"
    assert patch_applied.slot is None

    # content prefix — driver 오인 차단
    assert patch_applied.content.startswith("apply_status=no_fence")

    # workdir 파일 미변경
    assert target.read_text(encoding="utf-8") == "untouched\n"

    # P1-3 가드 — reviewer가 [CONVERGED] 출력했어도 mode=implement + no_fence면 수렴 차단
    assert critique.meta.convergence_streak is None


# ─── case 4: P1-3 — run 모드 fence 0건은 가드 미적용 (회귀 보호) ───────────────


def test_run_turn_no_fence_in_run_mode_does_not_block_converge(tmp_path):
    """run 모드는 patch fence 0건이어도 [CONVERGED] 정상 통과 — 가드는 implement 모드 한정.

    회귀 보호: run 모드 driver는 코드 외 자유 응답(분석·요약 등)도 정상 산출이라
    code-blind CONVERGED 가드를 적용하면 안 됨.
    """
    workdir, sessions_dir, bus_path = _setup_workdir(tmp_path)

    driver_text = "# 분석 결과\n간단한 코드 없음 응답.\n"
    reviewer_text = "looks good\n[CONVERGED]"

    bus = Bus(bus_path)
    run_turn(
        turn_id=1, mode="run",
        driver_runner=_FakeRunner(name="codex", vendor="openai", text=driver_text),
        reviewer_runner=_FakeRunner(name="claude", vendor="anthropic", text=reviewer_text),
        bus=bus, task="x", workdir=workdir, sessions_dir=sessions_dir,
    )

    msgs = bus.read_all()
    critique = next(m for m in msgs if m.kind == "critique")
    patch_applied = next(m for m in msgs if m.kind == "patch_applied")

    # run 모드에서도 patch_applied(no_fence) 메시지는 발행됨 — 신호 일관성
    assert patch_applied.meta.apply_status == "no_fence"
    # 그러나 수렴 카운터는 정상 — run 모드는 가드 미적용
    assert critique.meta.convergence_streak == 1
