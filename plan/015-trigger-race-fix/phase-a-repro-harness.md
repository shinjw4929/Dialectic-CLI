# Phase A · repro harness — 015-trigger-race-fix

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: —
- 예상 LOC: ~50 (자동 pytest pty) + ~50 (수동 standalone) + ~20 (테스트)

## 1. 목표

TriggerListener `__exit__` → prompt readline byte 절도 race를 **에이전트 응답 호출 0건**으로 재현하는 harness 2종 구축. 자동 (pytest pty 기반 CI 회귀 보호) + 수동 (사용자 환경 의존성 검증). 본 Phase 이후 Phase B 가설 fix가 harness로 race 해소 여부를 즉시 검증 가능.

## 2. 입력

- [`src/ui.py:297-547`](../../src/ui.py) — TriggerListener 본문 (3차 fix 누적 코드)
- [`src/ui.py:146-247`](../../src/ui.py) — prompt_end_or_iterate 본문
- [`src/ui.py:118-143`](../../src/ui.py) — `_read_line_for_prompt` helper
- [`docs/dev-docs/validation.md`](../../docs/dev-docs/validation.md) §3 C-015 — race narrative
- [`tests/test_trigger_listener.py`](../../tests/test_trigger_listener.py) — fake termios mock 패턴 참고
- 사전 검증된 사실:
  - WSL2 PTY 환경에서 race 재현 (사용자 보고)
  - mock fake termios로는 race 재현 X (실 fd 미사용)
  - POSIX `pty` 표준 라이브러리로 child process spawn + stdin byte injection 가능
- 사용자 환경 narrative 수집 대상 (Phase A §6에 기록):
  - terminal emulator (Windows Terminal / VSCode integrated / native xterm 등)
  - locale (LC_ALL, LANG)
  - WSL 버전 (`wsl --version` 출력)
  - Python 버전
  - race 재현률 (10회 시연 중 N회 발생)

## 3. 출력

### 3.1 `tests/test_listener_race_pty.py` (신규, 자동 재현)

채택: **`pty.openpty` + `subprocess.Popen`** (단일 결정 — `pty.spawn`은 main process replace + multiprocessing은 fork 의존성으로 macOS/spawn-mode race 차이). 외부 의존성 0 (`pty` + `subprocess` + `os` + `select` stdlib만).

```python
# spec
"""TriggerListener __exit__ → prompt readline race 자동 재현 (PTY 기반).

pty.openpty로 master/slave fd pair 생성 → subprocess.Popen에 slave를 stdin/stdout/
stderr로 attach → child가 TriggerListener + prompt_end_or_iterate cycle 실행 →
parent가 master fd에 byte injection (TRIGGER_BYTE 0x06 + 'y\\n') + master fd에서
output drain → child exit code + stdout/stderr 분석으로 race 검출.

외부 의존성 0 (`pty` + `subprocess` + `os` + `select` 표준). PTY 미지원
(macOS 일부, Windows native)은 pytest skip.
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

REPO_ROOT = Path(__file__).resolve().parent.parent

CHILD_SCRIPT = """
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
"""


def _spawn_child_with_pty(script: str) -> tuple[subprocess.Popen, int]:
    """pty.openpty로 master/slave fd pair → subprocess.Popen에 slave attach.
    
    parent는 master fd로 byte 주입 + output 읽기.
    """
    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        [sys.executable, "-c", script.format(repo_root=str(REPO_ROOT))],
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
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
        proc.wait(timeout=5.0)
    finally:
        os.close(master_fd)
        if proc.poll() is None:
            proc.kill()
    # race 0 단언 — race 잔존 시 fail
    assert b"RESULT key=e" in output, (
        f"race 재현 — 'y' 입력이 빈 줄로 처리됨. output: {output!r}"
    )


@pytest.mark.skipif(sys.platform != "linux", reason="PTY harness Linux only")
def test_trigger_race_repro_directive_text():
    """trigger 후 한글 directive 입력 → race 0이면 RESULT key='i' directive='색깔...'.
    
    race 잔존 시: 빈 줄 처리 → fallback.
    """
    # 위 패턴 동일, 입력만 b"\xec\x83\x89\xea\xb9\x94\n" (UTF-8 '색깔')
    ...  # spec — 본문은 위 패턴 복제 + 입력 byte 변경


@pytest.mark.skipif(sys.platform != "linux", reason="PTY harness Linux only")
def test_no_race_no_trigger():
    """trigger 안 보낸 정상 cycle — prompt에 'y' 즉시 입력 → RESULT key='e'.
    
    회귀 안전망 — race fix가 정상 흐름을 깨지 않음 검증.
    """
    ...  # spec — trigger byte 생략 + 'y\n' 입력 + RESULT key='e' 단언
```

본 spec 본문에는 1번 케이스(`test_trigger_race_repro_y_input`)만 완전 작성 — 2·3번 케이스는 동일 패턴 복제 + 입력 byte/단언 변경. **`...` ellipsis는 narrative placeholder가 아니라 spec 명세상 "위 패턴 복제 지시"로 의도** (execute-plan subagent가 spec docstring을 따라 본문 작성).

### 3.2 `tools/repro_listener.py` (신규, 수동 standalone)

dummy AgentRunner는 본 harness가 production 코드를 호출하지 않고 listener + prompt cycle만 시연하는 의도 — AgentRunner Protocol 직접 stub 불필요 (orchestrator 진입 X). codex/claude 호출 0 → API 비용 0.

```python
# spec
"""TriggerListener race 수동 재현 — 사용자가 직접 Ctrl+F + 입력 시연.

production AgentRunner stub 없이 listener + prompt_end_or_iterate cycle만
독립 시연. codex/claude 호출 0 → API 비용 0. 빠른 fix iteration용.

사용법:
    ./.venv/bin/python tools/repro_listener.py [--turns N]

각 턴: 1초 sleep (driver/reviewer 응답 simulate) → with 블록 끝나면 trigger
검사 → prompt 진입 → 사용자 Y/c/text 입력. race 발생 시 명시적 메시지.

prompt_end_or_iterate 시그니처 — keyword-only `*, allow_continue=True,
allow_iterate_no_directive=True` default 사용 (trigger 단독 + CONVERGED 둘
다 해당, Y/n/c/text 모두 노출).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# repo_root sys.path 등록 — venv activate 안 해도 src 모듈 import 가능
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ui import TriggerListener, prompt_end_or_iterate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=3)
    args = parser.parse_args()

    print("[repro] TriggerListener race 수동 재현 — Ctrl+F 누른 뒤 prompt에 'y'/'c'/text 입력")
    print(f"[repro] {args.turns}턴 실행 (각 턴 1초 sleep으로 driver/reviewer 응답 simulate)")

    for turn in range(1, args.turns + 1):
        print(f"\n=== Turn {turn}/{args.turns} ===")
        # with 블록 안에서 sleep — listener thread가 0.1s cycle로 trigger byte 검사
        with TriggerListener() as trigger:
            time.sleep(1.0)  # driver/reviewer 응답 simulate
            triggered = trigger.is_set()
        # __exit__ 완료 후 prompt 진입 — last_turn 또는 trigger 시 prompt
        last_turn = (turn == args.turns)
        if triggered or last_turn:
            reason = "Ctrl+F 트리거" if triggered else f"max-turns {args.turns} 도달"
            # allow_continue=triggered (trigger면 Y/c/text), allow_iterate_no_directive=last_turn
            key, directive = prompt_end_or_iterate(
                turn, reason,
                allow_continue=triggered,
                allow_iterate_no_directive=last_turn,
            )
            print(f"[repro] result: key={key!r}, directive={directive!r}")
            if directive is None and key not in ("e", "i"):
                # race 의심 — 사용자 input과 mismatch 시 명시
                print(
                    "[repro] WARNING: directive=None + key not in (e, i) — "
                    "possible race (사용자 input이 prompt에 도달 못 함)",
                    file=sys.stderr,
                )
            if key == "e":
                print("[repro] auto_end_user — 종료")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**주요 정정 (review-plan P0 #2 환원)**:
- `triggered = trigger.is_set()`을 with 블록 **안**에서 capture (블록 종료 후 다음 iter 변수 재바인딩 손실 차단)
- `last_turn` 별도 boolean 추출 (trigger 단독 vs CONVERGED/last_turn 분기 명확화)
- `prompt_end_or_iterate` keyword-only 인자 `allow_continue`/`allow_iterate_no_directive` 명시 (시그니처 정합)
- race 검출 narrative — directive=None + key not in (e, i) 시 stderr WARNING (사용자 input mismatch)

### 3.3 `tools/__init__.py` 또는 디렉토리 정합

- `tools/` 디렉토리는 신규. `__init__.py` 불필요 (script 디렉토리, 패키지 X)
- `pyproject.toml` `packages` 영향 0 (src/ 한정)
- `.gitignore` 영향 0

## 4. 작업 단위

- [ ] `tools/` 디렉토리 신설 (`mkdir -p tools`)
- [ ] `tools/repro_listener.py` 작성 — dummy harness, ~50 LOC
- [ ] `tests/test_listener_race_pty.py` 작성 — pty.openpty + subprocess.Popen + stdin write + stdout capture, ~50 LOC + ~3-5 테스트
- [ ] PTY 환경 차이 cover — `pytest.mark.skipif(sys.platform != "linux", reason="PTY Linux only")`
- [ ] 사용자에게 수동 시연 요청: `./.venv/bin/python tools/repro_listener.py --turns 3` 후 Ctrl+F + 'y' 입력 → race 재현 narrative 보고
- [ ] 사용자 환경 narrative 수집 → 본 phase §6에 기록 (terminal emulator, locale, WSL 버전, race 재현률)
- [ ] `pytest -q tests/test_listener_race_pty.py` 신규 ≥3 케이스 추가 (race 재현 케이스 + race 0건 검증 케이스)

## 5. 검증

- `python -c "from pathlib import Path; assert Path('tools/repro_listener.py').exists()"` 성공
- `./.venv/bin/python tools/repro_listener.py --help` 정상 출력
- `./.venv/bin/python tools/repro_listener.py --turns 1` 실행 → 1초 sleep 후 prompt 진입 (Ctrl+F 안 눌러도 max-turns 도달)
- `pytest -q tests/test_listener_race_pty.py` 신규 케이스 실행 — race 재현 검증 (pre-fix는 fail, post-fix는 pass)
- `pytest -q` 전체 회귀 0 (특히 `tests/test_trigger_listener.py` + `tests/test_prompt_end_or_iterate.py`)
- 사용자 시연 narrative 수집 보고 — 본 phase §6 갱신

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **PTY 환경 차이 (CI 자동 재현 어려움)**
   - WSL2 PTY는 Linux native와 약간 다른 PTY 동작 (kernel level 일부 차이)
   - pytest CI(GitHub Actions Ubuntu)에서 race 재현 안 될 수 있음 — 단 회귀 보호 가치는 유지 (race 0 환경에서 통과)
   - 차단: 수동 standalone harness 병렬 — 사용자 환경 의존성 검증

2. **dummy AgentRunner stub 정합성**
   - production AgentRunner Protocol 시그니처 무시 가능 (dummy는 listener cycle만 시연)
   - 단 향후 plan 007 mock 어댑터 신설 시 dummy harness가 stale 가능 — 본 plan §5 위험 5 narrative와 정합

3. **사용자 환경 narrative 수집**
   - 환경 정보가 race fix 정공법 결정의 핵심 input
   - 사용자가 narrative 안 알려주면 Phase B/C 가설 추측 의존
   - 차단: 사용자 시연 보고 시 환경 narrative 명시 요청 (본 phase §4 작업 단위에 추가)

4. **`tools/` 디렉토리 신설 sync-docs cascade — Phase D 단일 책임**
   - `tools/`는 신규 디렉토리 — Documentation-Checklist.md §1 매핑 행 추가 필수
   - 단일 책임 위치: **Phase D §3.5** (cascade docs 단계에 통합)
   - 본 Phase A는 디렉토리 신설 + 파일 작성만 (매핑 추가는 Phase D)

5. **harness 자체가 race 재현 못 함 (PTY 환경 한계)**
   - pty.openpty + subprocess 조합이 listener thread + readline race를 정확히 simulate 못 할 가능성
   - 차단: subprocess 대신 multiprocessing.Process로 child 실행 + os.fork (Linux) — single-process race 더 직접 재현 가능
   - Phase A에서 자동 재현 실패 시 narrative 명시 + 수동 standalone에 의존
