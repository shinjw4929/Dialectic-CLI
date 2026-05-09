"""plan 013 Phase A — _task_to_slug + _resolve_spec_path 단위 테스트.

Phase A 산출 helper 2개 검증:
- `_task_to_slug` 6 케이스 (영문/한글/특수문자/장문/빈/all-special)
- `_resolve_spec_path` 4 케이스 (정상/충돌-session_ts/specs/ mkdir/절대경로)

Phase B (run_turn / run_session wiring 통합 테스트) 케이스는 본 파일 누적.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.orchestrator import _resolve_spec_path, _task_to_slug


# ---------------------------------------------------------------------------- #
# _task_to_slug — 6 케이스
# ---------------------------------------------------------------------------- #


def test_slug_english_simple():
    """영문 + 콤마/공백 → hyphen 정리."""
    assert _task_to_slug("Add a, b function") == "add-a-b-function"


def test_slug_korean():
    """한글 + 공백 → 한글 유지 + hyphen 단일화."""
    assert _task_to_slug("덧셈 함수 작성") == "덧셈-함수-작성"


def test_slug_special_chars():
    """em-dash + 괄호 + 콤마 → hyphen 단일화."""
    assert _task_to_slug("Find max(a, b) — return larger") == "find-max-a-b-return-larger"


def test_slug_long_truncate():
    """50 char 초과 → 50 char로 truncate + 양끝 hyphen 정리."""
    long_task = "a" * 60
    result = _task_to_slug(long_task)
    assert len(result) == 50
    assert result == "a" * 50


def test_slug_empty():
    """빈 문자열 → 'task' fallback."""
    assert _task_to_slug("") == "task"


def test_slug_all_special():
    """모두 특수문자 → 'task' fallback."""
    assert _task_to_slug("!!! ??? ###") == "task"


# ---------------------------------------------------------------------------- #
# _resolve_spec_path — 4 케이스
# ---------------------------------------------------------------------------- #


def test_resolve_spec_path_basic(tmp_path):
    """기본: <workdir>/specs/<slug>.md + specs/ 자동 생성."""
    result = _resolve_spec_path(tmp_path, "Add a, b function", session_ts="20260509T120000Z")
    assert result == tmp_path / "specs" / "add-a-b-function.md"
    assert (tmp_path / "specs").is_dir()


def test_resolve_spec_path_collision_session_ts(tmp_path):
    """기존 specs/<slug>.md 존재 시 <slug>-<session_ts>.md 접미사."""
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "task-x.md").write_text("existing", encoding="utf-8")

    result = _resolve_spec_path(tmp_path, "task X", session_ts="20260509T123456Z")
    assert result == specs_dir / "task-x-20260509T123456Z.md"


def test_resolve_spec_path_specs_mkdir(tmp_path):
    """specs/ 미존재 시 자동 생성. spec.md는 top-level — <session_ts>/specs/ 아님."""
    assert not (tmp_path / "specs").exists()
    result = _resolve_spec_path(tmp_path, "test", session_ts="20260509T120000Z")
    assert (tmp_path / "specs").is_dir()
    # top-level 검증: 결과 경로 parent는 <workdir>/specs/, NOT <workdir>/<session_ts>/specs/
    assert result.parent == tmp_path / "specs"
    assert "20260509T120000Z" not in result.parent.parts


def test_resolve_spec_path_absolute(tmp_path):
    """반환 경로가 절대 경로 (workdir resolve 정합)."""
    result = _resolve_spec_path(tmp_path, "task", session_ts="20260509T120000Z")
    assert result.is_absolute()


# ---------------------------------------------------------------------------- #
# Phase B — run_turn / run_session 통합 wiring (mock driver/reviewer)
# ---------------------------------------------------------------------------- #


from types import SimpleNamespace
from unittest.mock import MagicMock

from src import orchestrator
from src.bus import Bus
from src.schema import Meta


def _mock_runner(text: str, name: str = "codex"):
    """driver/reviewer stub — text 응답 + frozen Meta (schema.py Meta 필드 정합)."""
    runner = MagicMock()
    runner.name = name
    runner.vendor = "openai" if name == "codex" else "anthropic"
    resp = SimpleNamespace(
        text=text,
        stderr_excerpt="",
        meta=Meta(
            vendor=runner.vendor, agent_cli=name, model=None,
            session_id=None, thread_id=None,
            input_tokens=0, output_tokens=0,
            cached_input_tokens=0, reasoning_output_tokens=0,
            cost_usd=None, latency_ms=10,
            is_mock=True, workdir="/tmp/mock",
        ),
    )
    runner.run = MagicMock(return_value=resp)
    return runner


def _setup_bus(tmp_path):
    """sessions/ + messages.jsonl 격리된 Bus 생성."""
    session_dir = tmp_path / "20260509T120000Z"
    sessions_dir = session_dir / "sessions"
    sessions_dir.mkdir(parents=True)
    bus = Bus(session_dir / "messages.jsonl")
    return bus, sessions_dir


def test_spec_autosave_run_turn_writes(tmp_path):
    """run_turn(spec_path=...) → driver 응답을 spec.md로 write."""
    bus, sessions_dir = _setup_bus(tmp_path)
    spec_path = tmp_path / "specs" / "test.md"
    spec_path.parent.mkdir()

    orchestrator.run_turn(
        1, "plan",
        driver_runner=_mock_runner("Mock spec body"),
        reviewer_runner=_mock_runner("Mock critique [CONVERGED]"),
        bus=bus, task="test task", workdir=tmp_path, sessions_dir=sessions_dir,
        spec_path=spec_path,
    )

    assert spec_path.exists()
    assert spec_path.read_text(encoding="utf-8") == "Mock spec body"


def test_spec_autosave_run_turn_no_spec_path(tmp_path):
    """spec_path=None → 파일 write 0 (회귀 보호)."""
    bus, sessions_dir = _setup_bus(tmp_path)

    orchestrator.run_turn(
        1, "run",
        driver_runner=_mock_runner("body"),
        reviewer_runner=_mock_runner("critique [CONVERGED]"),
        bus=bus, task="test", workdir=tmp_path, sessions_dir=sessions_dir,
        spec_path=None,
    )

    assert not (tmp_path / "specs").exists()


def test_spec_autosave_overwrite_per_turn(tmp_path):
    """동일 spec_path로 run_turn 2회 → 마지막 응답이 정본 (overwrite)."""
    bus, sessions_dir = _setup_bus(tmp_path)
    spec_path = tmp_path / "specs" / "x.md"
    spec_path.parent.mkdir()

    orchestrator.run_turn(
        1, "plan",
        driver_runner=_mock_runner("first turn body"),
        reviewer_runner=_mock_runner("[CONVERGED]"),
        bus=bus, task="x", workdir=tmp_path, sessions_dir=sessions_dir,
        spec_path=spec_path,
    )
    orchestrator.run_turn(
        2, "plan",
        driver_runner=_mock_runner("second turn body"),
        reviewer_runner=_mock_runner("[CONVERGED]"),
        bus=bus, task="x", workdir=tmp_path, sessions_dir=sessions_dir,
        spec_path=spec_path,
    )

    assert spec_path.read_text(encoding="utf-8") == "second turn body"


class _NoopTriggerListener:
    """TriggerListener stub — terminal raw mode 진입 회피."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def is_set(self):
        return False


def _patch_runners(monkeypatch, driver_text="Spec body", reviewer_text="critique [CONVERGED]"):
    """_resolve_runner + interactive prompt monkeypatch — 외부 API/stdin 호출 0."""
    def fake_resolver(name):
        return _mock_runner(driver_text if name == "codex" else reviewer_text, name=name)
    monkeypatch.setattr(orchestrator, "_resolve_runner", fake_resolver)
    monkeypatch.setattr(orchestrator, "TriggerListener", _NoopTriggerListener)
    monkeypatch.setattr(
        orchestrator, "prompt_end_or_iterate",
        lambda **kw: ("e", None),
    )
    monkeypatch.setattr(
        orchestrator, "prompt_decision",
        lambda **kw: ("e", None),
    )


def _build_args(tmp_path, mode="plan", interactive="end-only", task="Add a, b function"):
    return SimpleNamespace(
        task=task,
        mode=mode,
        driver="codex",
        reviewer="claude",
        max_turns=1,
        convergence_streak=2,
        interactive=interactive,
        workdir=str(tmp_path),
    )


def test_spec_autosave_run_session_plan_mode_end_only(tmp_path, monkeypatch):
    """run_session(mode='plan', interactive='end-only') → spec.md 생성."""
    _patch_runners(monkeypatch, driver_text="end-only spec body")

    args = _build_args(tmp_path, interactive="end-only")
    orchestrator.run_session(args)

    spec_path = tmp_path / "specs" / "add-a-b-function.md"
    assert spec_path.exists()
    assert spec_path.read_text(encoding="utf-8") == "end-only spec body"


def test_spec_autosave_run_session_plan_mode_critical(tmp_path, monkeypatch):
    """critical 분기 — _run_session_critical 시그니처 누락 시 fail (§6.2)."""
    _patch_runners(monkeypatch, driver_text="critical spec body")

    args = _build_args(tmp_path, interactive="critical")
    orchestrator.run_session(args)

    spec_path = tmp_path / "specs" / "add-a-b-function.md"
    assert spec_path.exists()
    assert spec_path.read_text(encoding="utf-8") == "critical spec body"


def test_spec_autosave_run_session_plan_mode_full(tmp_path, monkeypatch):
    """full 분기 — _run_session_full 시그니처 누락 시 fail (§6.2)."""
    _patch_runners(monkeypatch, driver_text="full spec body")
    # full 분기는 prompt_decision 호출 — 1턴 후 max_turns 도달로 자연 종료
    args = _build_args(tmp_path, interactive="full")
    orchestrator.run_session(args)

    spec_path = tmp_path / "specs" / "add-a-b-function.md"
    assert spec_path.exists()
    assert spec_path.read_text(encoding="utf-8") == "full spec body"


def test_spec_autosave_run_session_run_mode_no_spec(tmp_path, monkeypatch):
    """run_session(mode='run') → spec_path=None → specs/ 미생성."""
    _patch_runners(monkeypatch, driver_text="run mode body")

    args = _build_args(tmp_path, mode="run", interactive="end-only")
    orchestrator.run_session(args)

    assert not (tmp_path / "specs").exists()


def test_spec_autosave_stderr_announce_plan_mode(tmp_path, monkeypatch, capsys):
    """mode=plan 종료 시 stderr에 spec.md 경로 안내 (사용자 산출물 확인 통로)."""
    _patch_runners(monkeypatch, driver_text="plan body")

    args = _build_args(tmp_path, mode="plan", interactive="end-only")
    orchestrator.run_session(args)

    err = capsys.readouterr().err
    assert "spec.md:" in err
    assert "specs/add-a-b-function.md" in err


def test_spec_autosave_stderr_announce_run_mode_no_spec(tmp_path, monkeypatch, capsys):
    """mode=run 종료 시 stderr에 spec.md 라인 부재 (회귀 보호)."""
    _patch_runners(monkeypatch, driver_text="run body")

    args = _build_args(tmp_path, mode="run", interactive="end-only")
    orchestrator.run_session(args)

    err = capsys.readouterr().err
    assert "spec.md:" not in err
    assert "messages.jsonl:" in err  # 기존 안내는 유지
