"""환경 점검 — claude/codex --version + auth/login status (벤더 대칭, P-VENDOR 환원).

비용 0 호출 (token 사용 없음). code-conventions.md §3 (`:31-58`) cwd 명시 + 화이트리스트 정합.
`claude doctor`는 영구 제외 (validation.md §4.4 P-VENDOR 환원 사례 1, 2026-05-09):
- codex 외부 subprocess doctor 동등 명령 부재 (`/status`는 codex CLI 내부)
- `claude doctor` capture_output=True 호출 시 tty/pipe 분기로 30s+ hang
- 사용자가 doctor 결과 필요 시 `claude doctor` 직접 호출
"""

import os
import subprocess
from pathlib import Path
from typing import Any

# code-conventions.md §3 화이트리스트 — auth + 시스템 변수만 통과.
# 본 plan 결정: PATH+HOME (§3 예시) + USER/LANG 추가.
_SYS_VARS = ("PATH", "HOME", "USER", "LANG")
_AUTH_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CODEX_HOME")
# claude 어댑터(`agents/claude.py:_ENV_AUTH_PREFIXES`)와 동기화 — `CLAUDE_CODE_*` 모든 변수
# (CLAUDE_CODE_OAUTH_TOKEN, CLAUDE_CODE_USE_BEDROCK 등) 통과. doctor와 실 호출 env 비대칭 차단 (P-VENDOR).
_AUTH_PREFIXES = ("CLAUDE_CODE_",)

# stdout/stderr 절단 길이 — agents/base.py:ERROR_CONTENT_TRUNCATE_CHARS=500 패턴 일관성.
# doctor 출력은 사용자에게 표 형식으로 보여주는 용도라 더 짧게 (200).
_OUTPUT_TRUNCATE_CHARS = 200


def _safe_env() -> dict[str, str]:
    """외부 환경변수 누수 차단 화이트리스트 — code-conventions.md §3 규약.

    어댑터(`agents/{codex,claude}.py`)와 동일 정책 — doctor 시점 ↔ 실 호출 시점 env 일관 (P-VENDOR).
    """
    env: dict[str, str] = {k: os.environ[k] for k in (*_SYS_VARS, *_AUTH_VARS) if k in os.environ}
    for k, v in os.environ.items():
        if any(k.startswith(p) for p in _AUTH_PREFIXES):
            env[k] = v
    return env


def check_env() -> dict[str, dict[str, dict[str, Any]]]:
    """비용 0 환경 점검 — claude/codex --version + auth/login status (벤더 대칭).

    `claude doctor`는 영구 제외 (P-VENDOR 차단):
    - codex는 외부 subprocess로 부를 doctor 동등 명령 부재 (`/status`는 codex CLI 내부
      슬래시 명령, subprocess 호출 불가). 본 도구가 claude doctor만 부르면 벤더 비대칭.
    - 본 도구 책임은 "두 CLI가 설치 + 인증 통과"까지. claude doctor의 connectivity
      check 등은 claude CLI 자체 진단 — 외부 도구 scope 외.
    - 일부 환경에서 `claude doctor`가 capture_output 호출 시 tty/pipe 분기로 30s+ hang
      (사용자 환경 사례: tty 0.5s vs pipe 12s+). PTY wrap (~30 LOC) 회피보다 영구 제외 단순.
    - 사용자가 doctor 결과 필요 시 `claude doctor` 직접 호출 (외부 도구).
    """
    env_pass = _safe_env()
    return {
        "claude": {
            "version": _run_capture(["claude", "--version"], env=env_pass, timeout=5),
            "auth":    _run_capture(["claude", "auth", "status"], env=env_pass, timeout=10),
        },
        "codex": {
            "version": _run_capture(["codex", "--version"], env=env_pass, timeout=5),
            "login":   _run_capture(["codex", "login", "status"], env=env_pass, timeout=10),
        },
    }


def _run_capture(
    cmd: list[str],
    env: dict[str, str],
    timeout: int,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """{ok, stdout, stderr}. cwd 미지정 시 Path.home() — code-conventions.md §3 P0 규약."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",  # R-001
            timeout=timeout, env=env, check=False,
            cwd=cwd or Path.home(),
        )
        return {
            "ok": r.returncode == 0,
            "stdout": r.stdout.strip()[:_OUTPUT_TRUNCATE_CHARS],
            "stderr": r.stderr.strip()[:_OUTPUT_TRUNCATE_CHARS],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout"}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": "command not found"}
