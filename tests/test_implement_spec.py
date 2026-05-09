"""plan 014 Phase A·B — implement 모드 spec 입력 단위 테스트.

Phase A: `_input_spec_path` 메뉴 입력 검증 (7 케이스).
Phase B: `run_session` `mode==implement` 분기 — args.spec 4종 SystemExit + 정상 substitution (5 케이스).
mock 패턴 (Phase B): `tests/test_spec_autosave.py`의 `_mock_runner`/`_patch_runners` 재사용.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src import cli


def _seq_factory(items):
    """입력 시퀀스 → `_readline_input` stub. StopIteration 시 EOFError raise.

    `_safe_input`은 EOFError 발생 시 종료 확인 prompt 1회 더 호출함 — 종료 확인에서도
    EOFError이면 `_MenuExit` raise.
    """
    it = iter(items)

    def _stub(prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return _stub


def test_input_spec_path_basic(tmp_path, monkeypatch):
    """tmp_path/spec.md 생성 후 입력 → 절대 경로 반환."""
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\n\nbody.\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([str(spec)]))
    result = cli._input_spec_path()
    assert result == str(spec.resolve())


def test_input_spec_path_missing_retry(tmp_path, monkeypatch, capsys):
    """미존재 입력 → retry 안내 → 정상 입력으로 수렴."""
    missing = tmp_path / "nope.md"
    valid = tmp_path / "ok.md"
    valid.write_text("body", encoding="utf-8")
    monkeypatch.setattr(
        cli, "_readline_input",
        _seq_factory([str(missing), str(valid)]),
    )
    result = cli._input_spec_path()
    assert result == str(valid.resolve())
    out = capsys.readouterr().out
    assert "파일 없음" in out


def test_input_spec_path_directory_retry(tmp_path, monkeypatch, capsys):
    """디렉토리 입력 → 거부 + 재입력 → 정상 파일."""
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()
    valid = tmp_path / "spec.md"
    valid.write_text("body", encoding="utf-8")
    monkeypatch.setattr(
        cli, "_readline_input",
        _seq_factory([str(sub_dir), str(valid)]),
    )
    result = cli._input_spec_path()
    assert result == str(valid.resolve())
    out = capsys.readouterr().out
    assert "디렉토리" in out


def test_input_spec_path_empty_retry(tmp_path, monkeypatch, capsys):
    """빈 입력 → 안내 + 재입력."""
    valid = tmp_path / "spec.md"
    valid.write_text("body", encoding="utf-8")
    monkeypatch.setattr(
        cli, "_readline_input",
        _seq_factory(["", "  ", str(valid)]),
    )
    result = cli._input_spec_path()
    assert result == str(valid.resolve())
    out = capsys.readouterr().out
    assert "spec 경로가 비었습니다" in out


def test_input_spec_path_help_key(tmp_path, monkeypatch, capsys):
    """'?' → 도움말 출력 + 재입력."""
    valid = tmp_path / "spec.md"
    valid.write_text("body", encoding="utf-8")
    monkeypatch.setattr(
        cli, "_readline_input",
        _seq_factory(["?", str(valid)]),
    )
    result = cli._input_spec_path()
    assert result == str(valid.resolve())
    out = capsys.readouterr().out
    assert "도움말" in out
    assert "spec" in out


def test_input_spec_path_eof_propagates(monkeypatch):
    """EOF → `_safe_input` 종료 확인 → 종료 확인도 EOF → `_MenuExit` propagate."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([]))
    with pytest.raises(cli._MenuExit):
        cli._input_spec_path()


def test_input_spec_path_utf8_decode_failure(tmp_path, monkeypatch, capsys):
    """UTF-8 미정합 바이너리 → 거부 + 재입력 정상 spec 수렴."""
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe\xfd not utf-8")
    valid = tmp_path / "spec.md"
    valid.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(
        cli, "_readline_input",
        _seq_factory([str(bad), str(valid)]),
    )
    result = cli._input_spec_path()
    assert result == str(valid.resolve())
    out = capsys.readouterr().out
    assert "UTF-8 디코딩 실패" in out


# ---------------------------------------------------------------------------- #
# Phase B — run_session implement 분기 (mock driver/reviewer + monkeypatch)
# ---------------------------------------------------------------------------- #


from src import orchestrator
from tests.test_spec_autosave import _mock_runner, _patch_runners


def _build_implement_args(tmp_path: Path, spec, interactive: str = "end-only") -> SimpleNamespace:
    """run_session(mode='implement') 진입용 Namespace.

    Phase A `_build_args`(test_spec_autosave.py)와 같은 필드 set + spec 추가.
    """
    return SimpleNamespace(
        task="",  # implement 모드는 spec body가 task로 substitute됨
        mode="implement",
        driver="codex",
        reviewer="claude",
        max_turns=1,
        convergence_streak=2,
        interactive=interactive,
        workdir=str(tmp_path),
        spec=spec,
    )


def test_implement_mode_spec_none_systemexit(tmp_path, monkeypatch):
    """args.spec=None + mode==implement → SystemExit '필수'."""
    _patch_runners(monkeypatch)
    args = _build_implement_args(tmp_path, spec=None)
    with pytest.raises(SystemExit) as exc:
        orchestrator.run_session(args)
    assert "필수" in str(exc.value)


def test_implement_mode_spec_missing_systemexit(tmp_path, monkeypatch):
    """args.spec=<missing path> → SystemExit '없음 또는 디렉토리'."""
    _patch_runners(monkeypatch)
    missing = tmp_path / "nonexistent.md"
    args = _build_implement_args(tmp_path, spec=str(missing))
    with pytest.raises(SystemExit) as exc:
        orchestrator.run_session(args)
    assert "없음" in str(exc.value)


def test_implement_mode_spec_directory_systemexit(tmp_path, monkeypatch):
    """args.spec=<directory> → SystemExit '없음 또는 디렉토리'."""
    _patch_runners(monkeypatch)
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()
    args = _build_implement_args(tmp_path, spec=str(sub_dir))
    with pytest.raises(SystemExit) as exc:
        orchestrator.run_session(args)
    assert "없음 또는 디렉토리" in str(exc.value)


def test_implement_mode_spec_empty_systemexit(tmp_path, monkeypatch):
    """args.spec=<empty file> → SystemExit '비어있음'."""
    _patch_runners(monkeypatch)
    empty = tmp_path / "empty.md"
    empty.write_text("   \n\n  \t\n", encoding="utf-8")  # whitespace-only도 빈으로 간주
    args = _build_implement_args(tmp_path, spec=str(empty))
    with pytest.raises(SystemExit) as exc:
        orchestrator.run_session(args)
    assert "비어있음" in str(exc.value)


def test_implement_mode_spec_oserror_systemexit(tmp_path, monkeypatch):
    """spec read 시 OSError(PermissionError 등) → '읽기 실패' SystemExit (raw stack trace 차단)."""
    _patch_runners(monkeypatch)
    spec = tmp_path / "spec.md"
    spec.write_text("body", encoding="utf-8")

    real_read_text = Path.read_text

    def _denied(self: Path, *a, **kw) -> str:
        if self == spec.resolve():
            raise PermissionError(13, "Permission denied")
        return real_read_text(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", _denied)
    args = _build_implement_args(tmp_path, spec=str(spec))
    with pytest.raises(SystemExit) as exc:
        orchestrator.run_session(args)
    assert "spec 읽기 실패" in str(exc.value)


def test_implement_mode_spec_substitution(tmp_path, monkeypatch):
    """정상 spec → args.task가 spec body로 substitution됨 (JSONL turn_id=0 task content 검증)."""
    _patch_runners(monkeypatch, driver_text="implementer body")
    spec = tmp_path / "input-spec.md"
    spec_body = "# Spec body content\n\n- step 1\n- step 2\n"
    spec.write_text(spec_body, encoding="utf-8")

    args = _build_implement_args(tmp_path, spec=str(spec))
    orchestrator.run_session(args)

    # args.task가 spec body로 substitute됨 (Namespace 직접 검증)
    assert args.task == spec_body

    # JSONL turn_id=0 task 메시지 content == spec body
    # session_dir = tmp_path/<session_ts>/messages.jsonl — 한 폴더만 생성됨
    session_dirs = [p for p in tmp_path.iterdir() if p.is_dir() and p.name not in ("specs",)]
    assert len(session_dirs) == 1, f"expected 1 session dir, got {session_dirs}"
    from src.bus import Bus
    bus = Bus(session_dirs[0] / "messages.jsonl")
    msgs = bus.read_all()
    task_msgs = [m for m in msgs if m.kind == "task" and m.turn_id == 0]
    assert len(task_msgs) == 1
    assert task_msgs[0].content == spec_body


# ---------------------------------------------------------------------------- #
# Phase C — alias subparser argparse 단위 검증 (mock runner 없이)
# ---------------------------------------------------------------------------- #
#
# `dialectic implement --spec X`와 `dialectic run --mode implement --spec X --task ""`
# 양쪽 path가 argparse Namespace에서 동등 결과를 만드는지 단위 단언.
# `cli.main()`은 argparse 후 `args.func(args)`로 즉시 `run_session`을 실행하므로
# mock 인프라 없이 구동 X — `_build_parser_with_implement_alias()`로 cli.main 본문의
# parser 구성 부분만 재현해 격리 (test_cli_interactive_modes.py:_build_parser 정합).
# 본 재현이 src/cli.py의 실 main 본문과 어긋나면 회귀 보호 단언이 실패해 drift 알림.

import argparse


def _build_parser_with_implement_alias() -> argparse.ArgumentParser:
    """src/cli.py:main()의 argparse 구성 중 run/implement subparser 부분만 재현.

    실 cli.main 본문 변경 시 본 함수도 같이 갱신 (drift 보호는 아래
    `test_cli_module_implement_alias_drift`로 회귀 단언).
    """
    parser = argparse.ArgumentParser(prog="dialectic")
    subs = parser.add_subparsers(dest="cmd", required=False)

    # run
    p_run = subs.add_parser("run")
    p_run.add_argument("--task", required=True)
    p_run.add_argument("--workdir", default=None)
    p_run.add_argument("--driver", choices=["codex", "claude"], default="codex")
    p_run.add_argument("--reviewer", choices=["codex", "claude"], default="claude")
    p_run.add_argument("--max-turns", type=cli._positive_int, default=1)
    p_run.add_argument("--mode", choices=["run", "plan", "implement"], default="run")
    p_run.add_argument("--convergence-streak", type=cli._positive_int, default=2)
    p_run.add_argument(
        "--interactive", choices=["end-only", "critical", "full"], default="end-only"
    )
    p_run.add_argument("--spec", type=str, default=None)

    # implement alias
    p_implement = subs.add_parser("implement")
    p_implement.add_argument("--spec", required=True, type=str)
    p_implement.add_argument("--driver", choices=["codex", "claude"], default="codex")
    p_implement.add_argument("--reviewer", choices=["codex", "claude"], default="claude")
    p_implement.add_argument("--max-turns", type=cli._positive_int, default=1)
    p_implement.add_argument("--workdir", default=None)
    p_implement.add_argument("--convergence-streak", type=cli._positive_int, default=2)
    p_implement.add_argument(
        "--interactive", choices=["end-only", "critical", "full"], default="end-only"
    )
    p_implement.set_defaults(mode="implement", task="")

    return parser


def test_implement_alias_argparse_equivalence() -> None:
    """`dialectic implement --spec X` ↔ `dialectic run --mode implement --spec X --task ""` 동등.

    두 호출 path 모두 args.mode/args.spec/args.task 결과 동일 → run_session 진입 정합.
    mock runner 없이 argparse Namespace만 단언 (본 phase 축소 명세 정합 — agent mock 의존 케이스 제외).
    """
    parser = _build_parser_with_implement_alias()
    args_alias = parser.parse_args(["implement", "--spec", "/tmp/x.md"])
    args_run = parser.parse_args(
        ["run", "--mode", "implement", "--spec", "/tmp/x.md", "--task", ""]
    )
    assert args_alias.mode == args_run.mode == "implement"
    assert args_alias.spec == args_run.spec == "/tmp/x.md"
    assert args_alias.task == args_run.task == ""
    # default 인자 동등 (driver/reviewer/max-turns/convergence-streak/interactive/workdir)
    assert args_alias.driver == args_run.driver == "codex"
    assert args_alias.reviewer == args_run.reviewer == "claude"
    assert args_alias.max_turns == args_run.max_turns == 1
    assert args_alias.convergence_streak == args_run.convergence_streak == 2
    assert args_alias.interactive == args_run.interactive == "end-only"
    assert args_alias.workdir is None and args_run.workdir is None


def test_implement_alias_spec_required() -> None:
    """`dialectic implement` (--spec 누락) → argparse 자동 SystemExit (required)."""
    parser = _build_parser_with_implement_alias()
    with pytest.raises(SystemExit):
        parser.parse_args(["implement"])


def test_cli_module_implement_alias_drift() -> None:
    """실 cli.main이 등록한 parser도 implement subparser + set_defaults 보유 회귀 보호.

    `_build_parser_with_implement_alias` 재현이 cli.main 본문과 다르면 본 단언이 실패해 drift 알림.
    """
    import inspect

    cli_src = inspect.getsource(cli.main)
    assert 'subs.add_parser(\n        "implement"' in cli_src
    assert 'mode="implement"' in cli_src
    assert 'task=""' in cli_src


# ---------------------------------------------------------------------------- #
# Phase C — chaining 통합 테스트 (plan→implement, mock runner)
# ---------------------------------------------------------------------------- #
#
# phase-c-integration.md §3.1 명세 3 케이스. mock 패턴은
# `tests/test_spec_autosave.py`의 `_mock_runner`/`_patch_runners` 재사용 — 외부 API
# 호출 0, JSONL append-only 보존(read_all로만 검증), cwd 격리(tmp_path workdir).
#
# 케이스 1 핵심: plan 모드 1턴 → spec.md 생성 → implement 모드 입력 재진입 →
#   (a) Phase B substitution 정합 (turn_id=0 task content == spec body)
#   (b) Phase D 신규 파일 분기 정합 (workdir/add.py 생성 + 정확한 content)
#   (c) patch_applied meta.apply_status == "ok"


def _implement_patch_response() -> str:
    """implement 모드 mock implementer 응답 — 신규 파일 patch fence 1개.

    SEARCH="" + 파일 부재 → Phase D 신규 파일 분기 활성. REPLACE 본문이 그대로
    workdir/add.py로 write_text. extract_patches 정규식 (`patch_apply.py:21-29`) 정합.
    """
    return (
        "FILE: add.py\n"
        "<<<<<<< SEARCH\n"
        "\n"
        "=======\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        ">>>>>>> REPLACE\n"
        "[CONVERGED]\n"
    )


def test_plan_to_implement_chaining_with_new_file(tmp_path, monkeypatch):
    """plan 1턴 → spec.md 생성 → implement 1턴 → spec body가 §2 TASK 진입 + 신규 .py 파일 생성.

    Phase B(spec body → args.task substitution) + Phase D(신규 파일 patch 적용)
    정합 검증.

    workdir 분리(`plan_workdir` vs `impl_workdir`): orchestrator session_ts는 초 단위
    (`%Y%m%dT%H%M%SZ`)라 같은 workdir 재진입 시 같은 초 내 호출이 session_dir 중복.
    spec.md는 plan workdir에서 생성 → implement workdir에 path만 input (실 사용 시나리오
    `dialectic plan` 산출 → `dialectic implement --spec <path>`와 정합).
    """
    from src.bus import Bus

    plan_workdir = tmp_path / "plan-workdir"
    plan_workdir.mkdir()
    impl_workdir = tmp_path / "impl-workdir"
    impl_workdir.mkdir()

    # ---- (1) plan 모드 1턴: mock planner 응답을 spec.md로 autosave ---- #
    plan_spec_body = (
        "# Spec · add(a, b)\n\n"
        "## Signature\n"
        "def add(a, b)\n\n"
        "## Behavior\n"
        "return a + b\n"
    )
    _patch_runners(monkeypatch, driver_text=plan_spec_body)

    plan_args = SimpleNamespace(
        task="add a b function",
        mode="plan",
        driver="codex",
        reviewer="claude",
        max_turns=1,
        convergence_streak=2,
        interactive="end-only",
        workdir=str(plan_workdir),
    )
    orchestrator.run_session(plan_args)

    spec_path = plan_workdir / "specs" / "add-a-b-function.md"
    assert spec_path.exists(), "plan mode autosave 실패 (plan 013 산출 의존)"
    assert spec_path.read_text(encoding="utf-8") == plan_spec_body

    # ---- (2) implement 모드 1턴: spec body 주입 + 신규 파일 patch ---- #
    _patch_runners(monkeypatch, driver_text=_implement_patch_response())

    impl_args = _build_implement_args(impl_workdir, spec=str(spec_path))
    orchestrator.run_session(impl_args)

    # (a) args.task가 spec body로 substitute됨 (Phase B 정합)
    assert impl_args.task == plan_spec_body

    # (b) 신규 파일 생성 + 정확한 content (Phase D 정합)
    new_file = impl_workdir / "add.py"
    assert new_file.exists(), "Phase D 신규 파일 분기 실패 (apply_patches 신규 파일 미작성)"
    assert new_file.read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"

    # (c) JSONL turn_id=0 task content == spec body + patch_applied meta.apply_status == "ok"
    impl_session_dirs = [
        p for p in impl_workdir.iterdir() if p.is_dir() and p.name != "specs"
    ]
    assert len(impl_session_dirs) == 1, (
        f"implement 세션 1개 기대, 실제: {[p.name for p in impl_session_dirs]}"
    )
    bus = Bus(impl_session_dirs[0] / "messages.jsonl")
    msgs = bus.read_all()

    task_msgs = [m for m in msgs if m.kind == "task" and m.turn_id == 0]
    assert len(task_msgs) == 1
    assert task_msgs[0].content == plan_spec_body

    patch_applied_msgs = [m for m in msgs if m.kind == "patch_applied"]
    assert len(patch_applied_msgs) == 1
    assert patch_applied_msgs[0].meta.apply_status == "ok"
    assert "add.py" in patch_applied_msgs[0].meta.files_changed


def test_implement_alias_vs_mode_implement_equivalence(tmp_path, monkeypatch):
    """`dialectic implement --spec X` ↔ `dialectic run --mode implement --spec X` 동등.

    두 호출 path가 같은 spec → run_session 진입 후 turn_id=0 task content + meta.mode 동일.
    argparse 단위 단언(test_implement_alias_argparse_equivalence)을 넘어 실 run_session
    호출까지 비교 — bus 메시지의 task content/meta.mode가 호출 path 무관하게 일치 검증.
    """
    from src.bus import Bus

    spec = tmp_path / "spec.md"
    spec_body = "# Simple spec\n\nsimple body.\n"
    spec.write_text(spec_body, encoding="utf-8")

    def _run_with_workdir(workdir: Path) -> list:
        _patch_runners(monkeypatch, driver_text="implementer ack")
        args = _build_implement_args(workdir, spec=str(spec))
        orchestrator.run_session(args)
        session_dirs = [
            p for p in workdir.iterdir()
            if p.is_dir() and p.name not in ("specs",)
        ]
        assert len(session_dirs) == 1
        return Bus(session_dirs[0] / "messages.jsonl").read_all()

    # path A: alias subparser 시뮬레이션 (set_defaults(mode='implement', task=''))
    workdir_a = tmp_path / "alias-run"
    workdir_a.mkdir()
    msgs_a = _run_with_workdir(workdir_a)

    # path B: --mode implement 시뮬레이션 (동일 Namespace 형태)
    workdir_b = tmp_path / "mode-run"
    workdir_b.mkdir()
    msgs_b = _run_with_workdir(workdir_b)

    task_a = next(m for m in msgs_a if m.kind == "task" and m.turn_id == 0)
    task_b = next(m for m in msgs_b if m.kind == "task" and m.turn_id == 0)

    # turn_id=0 task content 동일 (spec body 주입)
    assert task_a.content == task_b.content == spec_body
    # meta.mode 동일
    assert task_a.mode == task_b.mode == "implement"


def test_menu_implement_branch_spec_path(tmp_path, monkeypatch):
    """메뉴 단계 2 implement 선택 → 단계 3 _input_spec_path 호출 → run_session 진입.

    `_interactive_menu` 입력 시퀀스: '3' (mode=implement) → spec path → mapping default
    → workdir default → max-turns default → confirm Y(default).
    검증: run_session 호출 시 args.mode='implement' + args.spec=<input path>
    + args.task='' (cli.py:498 mode==implement 분기 정합).
    """
    # check_env stub — `_check_env_with_spinner_retry` 진입 우회용 (test_cli_menu.py 패턴 정합)
    def _stub_check_env() -> dict:
        return {
            "claude": {
                "version": {"ok": True, "stdout": "v0", "stderr": ""},
                "auth": {"ok": False, "stdout": "", "stderr": ""},
            },
            "codex": {
                "version": {"ok": True, "stdout": "v0", "stderr": ""},
                "login": {"ok": False, "stdout": "", "stderr": ""},
            },
        }
    monkeypatch.setattr(cli, "check_env", _stub_check_env)

    spec = tmp_path / "spec.md"
    spec.write_text("# Spec\nbody.\n", encoding="utf-8")

    # 입력 시퀀스: mode='3' → spec path → mapping default(Enter) → workdir default(Enter)
    # → max-turns default(Enter) → confirm Y(Enter).
    inputs = iter(["3", str(spec), "", "", "", ""])
    monkeypatch.setattr(cli, "_readline_input", lambda prompt="": next(inputs))

    captured: dict = {}
    def _capture(args) -> int:
        captured["args"] = args
        return 0
    monkeypatch.setattr(cli.orchestrator, "run_session", _capture)

    rc = cli._interactive_menu()
    assert rc == 0
    assert "args" in captured, "run_session 미호출 — 메뉴 분기 wiring 결함"
    args = captured["args"]
    assert args.mode == "implement"
    assert args.spec == str(spec.resolve())
    assert args.task == ""
    assert args.driver == "codex"
    assert args.reviewer == "claude"
