"""TriggerListener __exit__ → prompt readline race 자동 재현 (PTY 기반).

pty.openpty로 master/slave fd pair 생성 → subprocess.Popen에 slave를 stdin/stdout/
stderr로 attach → child가 TriggerListener + prompt_end_or_iterate cycle 실행 →
parent가 master fd에 byte injection (TRIGGER_BYTE 0x06 + 'y\\n') + master fd에서
output drain → child exit code + stdout/stderr 분석으로 race 검출.

외부 의존성 0 (`pty` + `subprocess` + `os` + `select` 표준). PTY 미지원
(macOS 일부, Windows native)은 pytest skip.

NOTE (plan 015 Phase A 한계): pty.openpty + subprocess 조합에서 child가 prompt
label("User Synthesis ...")을 master 측 buffer로 도달시키지 못하는 PTY 동기화
이슈 발견 (test_no_race_no_trigger 회귀 안전망조차 fail). race 검출 신뢰성
미확보 → 본 모듈 3 케이스 모두 module-level skip으로 동결. 사용자 환경
검증은 `tools/repro_listener.py` 수동 standalone에 의존 (실 stdin/stdout).
plan 015 Phase D R-NNN 환원 시 reference 자료로 보존.
"""

from __future__ import annotations

import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skip(
    reason="PTY harness 신뢰성 미확보 — Phase A 한계 narrative (수동 tools/repro_listener.py로 대체)"
)

REPO_ROOT = Path(__file__).resolve().parent.parent

CHILD_SCRIPT = """
import os
import sys
sys.path.insert(0, {repo_root!r})
from src.ui import TriggerListener, prompt_end_or_iterate
import time

with TriggerListener() as trigger:
    # parent가 master fd로 0x06 byte 주입 — listener thread가 0.1s cycle로 detect
    time.sleep(0.5)
# __exit__ 완료 후 prompt 진입 — parent가 'y\\n' 주입
key, directive = prompt_end_or_iterate(1, "test trigger")
print(f"RESULT key={{key}} directive={{directive!r}}", flush=True)
os._exit(0)
"""


def _spawn_child_with_pty(script: str) -> tuple[subprocess.Popen, int]:
    """pty.openpty로 master/slave fd pair → subprocess.Popen에 slave attach.

    parent는 master fd로 byte 주입 + output 읽기.
    """
    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        [sys.executable, "-c", script.format(repo_root=str(REPO_ROOT))],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)  # parent는 master만 사용
    return proc, master_fd


def _read_until(master_fd: int, marker: bytes, timeout_s: float = 5.0) -> bytes:
    """master fd에서 marker bytes 등장 또는 timeout까지 read."""
    deadline = time.monotonic() + timeout_s
    buf = bytearray()
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.1)
        if ready:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf.extend(chunk)
            if marker in bytes(buf):
                return bytes(buf)
    return bytes(buf)


@pytest.mark.skipif(sys.platform != "linux", reason="PTY harness Linux only")
def test_trigger_race_repro_y_input():
    """trigger 후 'y' 입력 → race 0이면 RESULT key='e' (auto_end_user).

    race 잔존 시: prompt readline이 빈 줄로 받음 → INVALID_RETRY_LIMIT 도달 →
    key='c' fallback (allow_continue=True default).
    """
    proc, master_fd = _spawn_child_with_pty(CHILD_SCRIPT)
    try:
        # 1) trigger byte 0x06 주입 (sleep 0.5s 안에)
        time.sleep(0.1)  # child setup 시간
        os.write(master_fd, b"\x06")
        # 2) prompt 표시될 때까지 wait — "User Synthesis" label 등장
        _read_until(master_fd, b"User Synthesis", timeout_s=3.0)
        # 3) 'y\n' 주입 — race 0이면 RESULT key='e'
        os.write(master_fd, b"y\n")
        output = _read_until(master_fd, b"RESULT", timeout_s=5.0)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
    # race 0 단언 — race 잔존 시 fail
    assert b"RESULT key=e" in output, (
        f"race 재현 — 'y' 입력이 빈 줄로 처리됨. output: {output!r}"
    )


@pytest.mark.skipif(sys.platform != "linux", reason="PTY harness Linux only")
def test_trigger_race_repro_directive_text():
    """trigger 후 한글 directive 입력 → race 0이면 RESULT key='i' directive='색깔...'.

    race 잔존 시: 빈 줄 처리 → fallback.
    """
    proc, master_fd = _spawn_child_with_pty(CHILD_SCRIPT)
    try:
        # 1) trigger byte 0x06 주입 (sleep 0.5s 안에)
        time.sleep(0.1)  # child setup 시간
        os.write(master_fd, b"\x06")
        # 2) prompt 표시될 때까지 wait — "User Synthesis" label 등장
        _read_until(master_fd, b"User Synthesis", timeout_s=3.0)
        # 3) UTF-8 '색깔\n' 주입 — race 0이면 RESULT key='i' directive='색깔'
        os.write(master_fd, b"\xec\x83\x89\xea\xb9\x94\n")
        output = _read_until(master_fd, b"RESULT", timeout_s=5.0)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
    # race 0 단언 — race 잔존 시 fail
    assert b"RESULT key=i" in output and "색깔".encode("utf-8") in output, (
        f"race 재현 — '색깔' 입력이 빈 줄로 처리됨. output: {output!r}"
    )


@pytest.mark.skipif(sys.platform != "linux", reason="PTY harness Linux only")
def test_no_race_no_trigger():
    """trigger 안 보낸 정상 cycle — prompt에 'y' 즉시 입력 → RESULT key='e'.

    회귀 안전망 — race fix가 정상 흐름을 깨지 않음 검증.
    """
    proc, master_fd = _spawn_child_with_pty(CHILD_SCRIPT)
    try:
        # 1) trigger byte 미주입 — sleep 0.5s 자연 경과 후 prompt 진입
        # 2) prompt 표시될 때까지 wait — "User Synthesis" label 등장
        _read_until(master_fd, b"User Synthesis", timeout_s=3.0)
        # 3) 'y\n' 주입 — 정상 흐름이면 RESULT key='e'
        os.write(master_fd, b"y\n")
        output = _read_until(master_fd, b"RESULT", timeout_s=5.0)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
    # 정상 cycle 단언 — fix가 정상 흐름을 깨면 fail
    assert b"RESULT key=e" in output, (
        f"정상 cycle 깨짐 — 'y' 입력이 정상 처리되지 않음. output: {output!r}"
    )
