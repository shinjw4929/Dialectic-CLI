"""Phase A · 011-menu-expansion — `_input_mode` 단위 테스트.

plan/011-menu-expansion/phase-a-mode-select.md §3.2 명세 6 케이스.
mock 패턴: `monkeypatch`로 `_readline_input` 교체 (`tests/test_cli_menu.py` 동일 패턴).
"""

from __future__ import annotations

import pytest

from src import cli


def _seq_factory(items):
    """입력 시퀀스 → `_readline_input` stub. StopIteration 시 EOFError raise.

    `_safe_input`은 EOFError 발생 시 종료 확인 prompt 1회 더 호출함 — 종료 확인에서도
    EOFError이면 `_MenuExit` raise. 테스트에서는 종료 확인까지 EOFError로 마무리.
    """
    it = iter(items)

    def _stub(prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return _stub


def test_input_mode_run(monkeypatch):
    """1 입력 → 'run' 반환."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory(["1"]))
    assert cli._input_mode() == "run"


def test_input_mode_plan(monkeypatch):
    """2 입력 → 'plan' 반환."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory(["2"]))
    assert cli._input_mode() == "plan"


def test_input_mode_implement_back(monkeypatch, capsys):
    """3 입력 → implement 안내 출력 + 재입력 (back to mode 메뉴) → 1 → 'run'."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory(["3", "1"]))
    assert cli._input_mode() == "run"
    out = capsys.readouterr().out
    assert "implement" in out
    assert "다른 모드" in out


def test_input_mode_compare_back(monkeypatch, capsys):
    """4 입력 → compare 안내 출력 + 재입력 → 2 → 'plan'."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory(["4", "2"]))
    assert cli._input_mode() == "plan"
    out = capsys.readouterr().out
    assert "compare" in out
    assert "다른 모드" in out


def test_input_mode_default_enter(monkeypatch):
    """빈 입력 (Enter) → 'run' 반환 (현재 동작 보존)."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([""]))
    assert cli._input_mode() == "run"


def test_input_mode_invalid_retry(monkeypatch, capsys):
    """'9' 같은 invalid → 재입력 (retry) 후 '1' → 'run'."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory(["9", "abc", "1"]))
    assert cli._input_mode() == "run"
    out = capsys.readouterr().out
    assert "1/2/3/4 중 선택" in out


# Phase B · `_input_mapping` 4 케이스 (phase-b-mapping-select.md §3.2)


def test_input_mapping_codex_claude(monkeypatch):
    """1 입력 → ('codex', 'claude') 반환."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory(["1"]))
    assert cli._input_mapping() == ("codex", "claude")


def test_input_mapping_claude_codex(monkeypatch):
    """2 입력 → ('claude', 'codex') 반환 (스왑)."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory(["2"]))
    assert cli._input_mapping() == ("claude", "codex")


def test_input_mapping_default_enter(monkeypatch):
    """빈 입력 (Enter) → ('codex', 'claude') default."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([""]))
    assert cli._input_mapping() == ("codex", "claude")


def test_input_mapping_invalid_retry(monkeypatch, capsys):
    """'3' (outline 외, same-vendor 4종 X) → 재입력 후 '2' → ('claude', 'codex')."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory(["3", "xyz", "2"]))
    assert cli._input_mapping() == ("claude", "codex")
    out = capsys.readouterr().out
    assert "1/2 중 선택" in out


# Phase C · `_input_workdir` (phase-c-workdir-select.md §3.2 — single-prompt UX)


def test_input_workdir_auto_default(monkeypatch):
    """빈 입력 (Enter) → None 반환 (orchestrator default 위임)."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([""]))
    assert cli._input_workdir() is None


def test_input_workdir_existing_dir(monkeypatch, tmp_path):
    """기존 디렉토리 입력 → resolve된 절대 경로 반환."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([str(tmp_path)]))
    result = cli._input_workdir()
    assert result == str(tmp_path.resolve())


def test_input_workdir_create_confirm(monkeypatch, tmp_path, capsys):
    """존재 X 경로 + 생성 확인 'Y' → mkdir + 반환."""
    target = tmp_path / "new_subdir"
    assert not target.exists()
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([str(target), "Y"]))
    result = cli._input_workdir()
    assert result == str(target.resolve())
    assert target.is_dir()
    out = capsys.readouterr().out
    assert "디렉토리 생성" in out


def test_input_workdir_create_default_enter(monkeypatch, tmp_path):
    """존재 X 경로 + 생성 확인 Enter (Y default) → mkdir + 반환."""
    target = tmp_path / "auto_create"
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([str(target), ""]))
    result = cli._input_workdir()
    assert result == str(target.resolve())
    assert target.is_dir()


def test_input_workdir_create_decline_then_existing(monkeypatch, tmp_path, capsys):
    """존재 X 경로 + 'n' 거부 → 재입력 → 기존 디렉토리 → 반환."""
    missing = tmp_path / "decline_target"
    monkeypatch.setattr(
        cli, "_readline_input", _seq_factory([str(missing), "n", str(tmp_path)])
    )
    result = cli._input_workdir()
    assert result == str(tmp_path.resolve())
    assert not missing.exists()
    out = capsys.readouterr().out
    assert "취소" in out


def test_input_workdir_file_rejected(monkeypatch, tmp_path, capsys):
    """파일 경로 입력 → 거부 + 재입력 → 기존 디렉토리 → 반환."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("x")
    monkeypatch.setattr(
        cli, "_readline_input", _seq_factory([str(file_path), str(tmp_path)])
    )
    result = cli._input_workdir()
    assert result == str(tmp_path.resolve())
    out = capsys.readouterr().out
    assert "파일은 workdir로 사용 불가" in out


def test_input_workdir_eof(monkeypatch):
    """EOF → `_safe_input` 종료 확인 → 종료 확인도 EOF → `_MenuExit` propagate."""
    monkeypatch.setattr(cli, "_readline_input", _seq_factory([]))
    with pytest.raises(cli._MenuExit):
        cli._input_workdir()
