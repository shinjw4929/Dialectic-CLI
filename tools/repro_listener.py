"""TriggerListener race 수동 재현 — 사용자가 직접 Ctrl+F + 입력 시연.

production AgentRunner stub 없이 listener + prompt_end_or_iterate cycle만
독립 시연. codex/claude 호출 0 → API 비용 0. 빠른 fix iteration용.

사용법:
    ./.venv/bin/python tools/repro_listener.py [--turns N] [--sleep SEC]

각 턴: --sleep 초(default 5) Spinner 표시 (driver/reviewer 응답 simulate) →
with 블록 끝나면 trigger 검사 → prompt 진입 → 사용자 Y/c/text 입력. race
발생 시 명시적 메시지. Spinner 가시화 + 충분한 시간으로 Ctrl+F 2회 연타 가능.

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

from src.ui import Spinner, TriggerListener, prompt_end_or_iterate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=3)
    parser.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        help="턴당 sleep 초 (Spinner 표시 시간) — Ctrl+F 2회 연타 여유. default 5.0",
    )
    args = parser.parse_args()

    print("[repro] TriggerListener race 수동 재현 — Ctrl+F 누른 뒤 prompt에 'y'/'c'/text 입력")
    print(
        f"[repro] {args.turns}턴 실행 — 각 턴 {args.sleep}초 Spinner "
        f"(driver/reviewer 응답 simulate)"
    )

    for turn in range(1, args.turns + 1):
        print(f"\n=== Turn {turn}/{args.turns} ===")
        # with 블록 안에서 Spinner — listener thread가 0.1s cycle로 trigger byte 검사
        # Spinner가 stderr에 ⠋ 프레임 출력 → 사용자가 turn 진행 가시화
        with TriggerListener() as trigger:
            with Spinner(f"turn {turn}/{args.turns} 진행 중 (Ctrl+F = 개입)"):
                time.sleep(args.sleep)
            triggered = trigger.is_set()
        # __exit__ 완료 후 prompt 진입 — last_turn 또는 trigger 시 prompt
        last_turn = (turn == args.turns)
        if triggered or last_turn:
            reason = "Ctrl+F 트리거" if triggered else f"max-turns {args.turns} 도달"
            # allow_continue=triggered (trigger면 Y/c/text), allow_iterate_no_directive=last_turn
            key, directive = prompt_end_or_iterate(
                turn,
                reason,
                allow_continue=triggered,
                allow_iterate_no_directive=last_turn,
            )
            print(f"[repro] result: key={key!r}, directive={directive!r}")
            # race 검출: prompt_end_or_iterate가 INVALID_RETRY_LIMIT 도달 시 fallback —
            # allow_continue=True면 ('c', None), 아니면 ('e', None). 정상 입력은
            # ('e', None) / ('i', None) / ('i', text) / ('c', None — 사용자 명시) 모두 valid.
            # race 잔존 단서: 사용자가 'y'/'n'/text 입력했는데 prompt가 빈 줄로 받음 →
            # 사용자가 직접 회수 보고 (자동 검출 어려움 — 사용자 의도 vs key 비교 X).
            # 본 standalone harness는 결과만 출력 — 사용자가 입력 vs key 매치 직접 판단.
            if key == "e":
                print("[repro] auto_end_user — 종료")
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
