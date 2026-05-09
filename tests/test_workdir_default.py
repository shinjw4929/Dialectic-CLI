"""plan 010 Phase C — workdir default 우선순위 단위 테스트.

`_resolve_workdir` 헬퍼 5건 단언:
  1. default(env 미설정) → `~/.local/share/dialectic/runs/<...>/`
  2. `DIALECTIC_RUNS_DIR=<dir>` → `<dir>/<...>/`
  3. `XDG_DATA_HOME=<dir>` (DIALECTIC_RUNS_DIR 미설정) → `<dir>/dialectic/runs/<...>/`
  4. `--workdir <abs>` 명시 → 위 우선순위 모두 무시 (절대 경로 그대로)
  5. `DIALECTIC_RUNS_DIR=<repo>/runs` → ADR-6 SystemExit (회귀 차단 — `run_session` 호출자 책임)

ADR-6 차단(`run_session` 내부)은 `_resolve_workdir` 단독으론 발생 X — 본 5번 케이스는
실 `run_session` 진입으로 차단 검증 (호출자 책임 분리 명시).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.orchestrator import _resolve_workdir, run_session


def _ns(workdir=None):
    return SimpleNamespace(workdir=workdir)


# ---------------------------------------------------------------------------- #
# 우선순위 4건
# ---------------------------------------------------------------------------- #

def test_resolve_workdir_default_xdg_home(monkeypatch, tmp_path):
    """env 미설정 → ~/.local/share/dialectic/runs/<...>/ 하위."""
    monkeypatch.delenv("DIALECTIC_RUNS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    result = _resolve_workdir(_ns())
    expected_base = (tmp_path / ".local" / "share" / "dialectic" / "runs").resolve()
    assert result.parent == expected_base
    assert result.is_dir()


def test_resolve_workdir_dialectic_runs_dir_override(monkeypatch, tmp_path):
    """`DIALECTIC_RUNS_DIR` 우선 — XDG·home fallback 무시."""
    runs = tmp_path / "custom_runs"
    monkeypatch.setenv("DIALECTIC_RUNS_DIR", str(runs))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_unused"))

    result = _resolve_workdir(_ns())
    assert result.parent == runs.resolve()
    assert result.is_dir()


def test_resolve_workdir_xdg_data_home(monkeypatch, tmp_path):
    """`XDG_DATA_HOME` 적용 — `<XDG_DATA_HOME>/dialectic/runs/` 하위."""
    monkeypatch.delenv("DIALECTIC_RUNS_DIR", raising=False)
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))

    result = _resolve_workdir(_ns())
    expected_base = (xdg / "dialectic" / "runs").resolve()
    assert result.parent == expected_base
    assert result.is_dir()


def test_resolve_workdir_cli_arg_wins(monkeypatch, tmp_path):
    """`--workdir <abs>` 명시 시 모든 env 무시 + 그 경로 그대로 (mkdir·timestamp suffix 없음)."""
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    monkeypatch.setenv("DIALECTIC_RUNS_DIR", str(tmp_path / "ignored_runs"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "ignored_xdg"))

    result = _resolve_workdir(_ns(workdir=str(explicit)))
    assert result == explicit.resolve()


# ---------------------------------------------------------------------------- #
# ADR-6 — DIALECTIC_RUNS_DIR이 repo 하위인 경우 차단 (호출자 책임)
# ---------------------------------------------------------------------------- #

def test_run_session_rejects_dialectic_runs_dir_under_repo(monkeypatch):
    """`DIALECTIC_RUNS_DIR=<repo>/runs` → run_session 진입 시 ADR-6 SystemExit.

    `_resolve_workdir`이 mkdtemp로 임시 dir 생성 직후 `run_session`이 ADR-6 차단함을 검증.
    `cleanup=False` default에서 차단 후 base_dir 잔존 — C-008 surface 잠재 누수, 본 테스트는
    repo 작업트리 오염 방지 위해 `finally`로 정리. 정식 fix는 plan 010 외 후속 plan.
    """
    import shutil

    repo_root = Path(__file__).resolve().parent.parent
    base_dir = repo_root / "runs"
    monkeypatch.setenv("DIALECTIC_RUNS_DIR", str(base_dir))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    args = SimpleNamespace(
        workdir=None, task="x",
        driver="codex", reviewer="claude",
        max_turns=1, mode="run",
        convergence_streak=2, interactive="end-only",
    )
    try:
        with pytest.raises(SystemExit, match="ADR-6"):
            run_session(args)
    finally:
        if base_dir.exists():
            shutil.rmtree(base_dir, ignore_errors=True)
