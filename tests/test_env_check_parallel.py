"""Phase B · check_env 병렬화 단언 (plan 010-observability).

- wall clock: 4 sub-check 직렬 합 4s 대비 병렬 ≤ 1.5s
- 결과 dict insertion 순서: claude/version → claude/auth → codex/version → codex/login
- 1개 sub-check timeout 시 다른 3개 정상 반환 (병렬 독립성)
"""

import time
from unittest.mock import patch

from src.env_check import check_env


def _stub_sleep_ok(cmd, env, timeout):
    """1초 sleep 후 ok=True 반환 — 직렬 호출 시 4s, 병렬이면 ~1s."""
    time.sleep(1.0)
    return {"ok": True, "stdout": " ".join(cmd), "stderr": ""}


def test_check_env_parallel_wall_clock_under_1_5s() -> None:
    with patch("src.env_check._run_capture", side_effect=_stub_sleep_ok):
        start = time.monotonic()
        result = check_env()
        elapsed = time.monotonic() - start
    assert elapsed <= 1.5, f"wall clock {elapsed:.2f}s > 1.5s — 병렬 미동작 의심"
    assert result["claude"]["version"]["ok"] is True
    assert result["codex"]["login"]["ok"] is True


def test_check_env_dict_insertion_order() -> None:
    with patch("src.env_check._run_capture", side_effect=_stub_sleep_ok):
        result = check_env()
    # tool 그룹 순서
    assert list(result.keys()) == ["claude", "codex"]
    # sub-check 순서 (insertion 순서 = specs 순서)
    assert list(result["claude"].keys()) == ["version", "auth"]
    assert list(result["codex"].keys()) == ["version", "login"]


def test_check_env_single_timeout_isolated() -> None:
    """1개 sub-check만 timeout 결과 반환 시 다른 3개 정상 단언 (병렬 독립성)."""

    def stub_one_timeout(cmd, env, timeout):
        time.sleep(0.2)
        if cmd[:2] == ["claude", "auth"]:
            return {"ok": False, "stdout": "", "stderr": "timeout"}
        return {"ok": True, "stdout": " ".join(cmd), "stderr": ""}

    with patch("src.env_check._run_capture", side_effect=stub_one_timeout):
        result = check_env()
    assert result["claude"]["version"]["ok"] is True
    assert result["claude"]["auth"]["ok"] is False
    assert result["claude"]["auth"]["stderr"] == "timeout"
    assert result["codex"]["version"]["ok"] is True
    assert result["codex"]["login"]["ok"] is True
