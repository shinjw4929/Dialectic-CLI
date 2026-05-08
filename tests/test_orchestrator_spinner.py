"""run_turn driver/reviewer 호출이 `with Spinner(...)` 컨텍스트로 wrapping 되는지 검증.

phase-a §3.3 spec 2 케이스 — isatty=True 시 stderr 회전 frame 출력 / isatty=False no-op.

회귀 가드:
- (1) Spinner __enter__ 시 thread.start, __exit__ 시 stop set + 라인 clear
- (2) isatty=False 환경 (CI/pytest)에서는 stderr write 0, mock runner 응답은 정상 bus.append
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

# repo root sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.agents.base import AgentResponse  # noqa: E402
from src.bus import Bus  # noqa: E402
from src.orchestrator import SENTINEL_META, run_turn  # noqa: E402


@dataclass
class _MockRunner:
    """AgentRunner Protocol 준수 — codex/claude 어댑터 우회용 stub."""
    name: str
    vendor: str
    text: str
    delay_s: float = 0.0

    def run(
        self,
        prompt: str,
        *,
        raw_log_path: Path,
        timeout_s: int,
        workdir: Path,
    ) -> AgentResponse:
        if self.delay_s > 0:
            time.sleep(self.delay_s)
        return AgentResponse(
            text=self.text,
            raw_path=raw_log_path,
            meta=SENTINEL_META(workdir, vendor=self.vendor, agent_cli=self.name),
            stderr_excerpt=None,
        )


def _setup_workdir(tmp_path: Path) -> tuple[Path, Path, Path]:
    workdir = tmp_path / "wd"
    workdir.mkdir()
    sessions_dir = workdir / "logs" / "sessions"
    sessions_dir.mkdir(parents=True)
    bus_path = workdir / "logs" / "messages.jsonl"
    return workdir, sessions_dir, bus_path


def test_run_turn_wraps_driver_call_with_spinner(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """isatty=True monkeypatch + delay 부여 시 stderr에 spinner frame 1자 이상 출력.

    run_turn이 driver runner.run을 `with Spinner(...)` 컨텍스트로 wrap한다는 행동 단언.
    """
    workdir, sessions_dir, bus_path = _setup_workdir(tmp_path)

    # stderr.isatty가 True를 반환하도록 monkeypatch — Spinner._enabled 활성화
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True, raising=False)

    driver_text = "proposal text\n"
    reviewer_text = "critique text\n[CONVERGED]"

    bus = Bus(bus_path)
    run_turn(
        turn_id=1, mode="run",
        # delay_s를 잠깐 둬서 spinner 스레드가 최소 1프레임 write할 시간 확보
        driver_runner=_MockRunner(name="codex", vendor="openai", text=driver_text, delay_s=0.15),
        reviewer_runner=_MockRunner(name="claude", vendor="anthropic", text=reviewer_text, delay_s=0.15),
        bus=bus, task="x", workdir=workdir, sessions_dir=sessions_dir,
    )

    captured = capsys.readouterr()
    # stderr에 spinner frame 또는 라벨 substring 등장 단언 — Spinner가 active
    # 라벨에는 ROLE_LABEL_KO['implementer']='구현자' + VENDOR_LABEL['codex']='Codex CLI' 포함
    assert "구현자" in captured.err or "Codex CLI" in captured.err, (
        f"driver Spinner stderr 출력 부재: err={captured.err!r}"
    )
    # reviewer 라벨도 단언 (with Spinner 2건 검증)
    assert "기획 검토자" in captured.err or "Claude Code" in captured.err, (
        f"reviewer Spinner stderr 출력 부재: err={captured.err!r}"
    )

    # bus 회귀 — proposal + critique 정상 append
    msgs = bus.read_all()
    kinds = [m.kind for m in msgs]
    assert "proposal" in kinds
    assert "critique" in kinds


def test_run_turn_spinner_isatty_false_no_op(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """isatty=False (CI/pytest) 환경 — stderr에 spinner frame 0. bus.append 정상 진행."""
    workdir, sessions_dir, bus_path = _setup_workdir(tmp_path)

    # stderr.isatty가 False — Spinner._enabled = False, thread 미시작
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False, raising=False)

    driver_text = "proposal text\n"
    reviewer_text = "critique text\n[CONVERGED]"

    bus = Bus(bus_path)
    run_turn(
        turn_id=1, mode="run",
        driver_runner=_MockRunner(name="codex", vendor="openai", text=driver_text),
        reviewer_runner=_MockRunner(name="claude", vendor="anthropic", text=reviewer_text),
        bus=bus, task="x", workdir=workdir, sessions_dir=sessions_dir,
    )

    captured = capsys.readouterr()
    # spinner frame 문자(SPINNER_FRAMES)도, 라벨 substring도 stderr 미등장
    assert "구현자" not in captured.err
    assert "Codex CLI" not in captured.err
    assert "기획 검토자" not in captured.err
    assert "Claude Code" not in captured.err

    # 그러나 bus.append는 정상 — proposal + critique 두 개
    msgs = bus.read_all()
    kinds = [m.kind for m in msgs]
    assert "proposal" in kinds
    assert "critique" in kinds
