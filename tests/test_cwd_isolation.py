"""ADR-6 cwd 격리 단위 테스트 — monkeypatch subprocess.run.

세 검증:
1. CodexRunner cmd_list에 `--ephemeral`/`--sandbox read-only`/`--ignore-rules` 포함 + cwd=workdir.
2. ClaudeRunner cmd_list에 `--tools`/`--no-session-persistence`/`--max-budget-usd`/`--output-format json`
   포함 + `--bare`/`--append-system-prompt` **부재** + cwd=workdir.
3. run_session() — `--workdir = repo 루트` 사용자 입력 우회 차단 (SystemExit, ADR-6).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agents.claude import ClaudeRunner
from src.agents.codex import CodexRunner


# ---------------------------------------------------------------------------- #
# codex
# ---------------------------------------------------------------------------- #

def test_codex_runner_passes_workdir_not_repo_root(monkeypatch, tmp_path):
    called: dict = {}
    fake_stdout = (
        '{"type":"thread.started","thread_id":"t-x"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1,'
        '"cached_input_tokens":0,"reasoning_output_tokens":0}}\n'
    )

    def fake_run(cmd, *args, **kw):
        called["cmd"] = cmd
        called.update(kw)
        return SimpleNamespace(stdout=fake_stdout, stderr="", returncode=0)

    monkeypatch.setattr("src.agents.codex.subprocess.run", fake_run)
    raw = tmp_path / "raw.jsonl"
    CodexRunner().run("p", raw_log_path=raw, timeout_s=10, workdir=tmp_path)

    assert called["cwd"] == tmp_path
    assert called["cwd"] != Path.cwd()
    assert called.get("shell", False) is False
    assert "--ephemeral" in called["cmd"]
    assert "--sandbox" in called["cmd"] and "read-only" in called["cmd"]
    assert "--ignore-rules" in called["cmd"]
    assert "--skip-git-repo-check" in called["cmd"]


# ---------------------------------------------------------------------------- #
# claude
# ---------------------------------------------------------------------------- #

def test_claude_runner_passes_workdir(monkeypatch, tmp_path):
    called: dict = {}
    fake_payload = json.dumps({
        "result": "ok",
        "model": "claude-x",
        "session_id": "s-1",
        "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0},
        "total_cost_usd": 0.0,
    })

    def fake_run(cmd, *args, **kw):
        called["cmd"] = cmd
        called.update(kw)
        return SimpleNamespace(stdout=fake_payload, stderr="", returncode=0)

    monkeypatch.setattr("src.agents.claude.subprocess.run", fake_run)
    raw = tmp_path / "raw.jsonl"
    ClaudeRunner().run("p", raw_log_path=raw, timeout_s=10, workdir=tmp_path)

    assert called["cwd"] == tmp_path
    assert called["cwd"] != Path.cwd()
    assert called.get("shell", False) is False
    assert "--tools" in called["cmd"]
    assert "--no-session-persistence" in called["cmd"]
    assert "--max-budget-usd" in called["cmd"]
    assert "--output-format" in called["cmd"] and "json" in called["cmd"]
    # OAuth 호환 결정 + 4섹션 stdin 결정과 일관
    assert "--bare" not in called["cmd"]
    assert "--append-system-prompt" not in called["cmd"]


# ---------------------------------------------------------------------------- #
# run_session — repo 루트 차단
# ---------------------------------------------------------------------------- #

def test_run_session_rejects_repo_root_workdir():
    from src.orchestrator import run_session

    repo_root = Path(__file__).resolve().parent.parent
    args = SimpleNamespace(
        workdir=str(repo_root), task="x",
        driver="codex", reviewer="claude",
        max_turns=1, mode="run",
        convergence_streak=2, interactive="end-only",
    )
    with pytest.raises(SystemExit, match="ADR-6"):
        run_session(args)
