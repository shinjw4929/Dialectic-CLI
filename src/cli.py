"""Dialectic-CLI entry point.

현재 stub — 코드는 Day 2~4 작성 예정 (outline/05-timeline.md 참조).
"""

import sys


def main() -> int:
    """`dialectic` 명령 진입점."""
    print("dialectic-cli 0.1.0")
    print()
    print("현재 Day 1 — .md 하네스 28+ 파일 완료, 코드 미구현.")
    print("Day 2~4에 어댑터·orchestrator·UI·mock·compare 작성 예정.")
    print()
    print("자세한 내용:")
    print("  - README.md          현재 상태 + TODO 표")
    print("  - outline/README.md  결정 흐름 (Q1~Q17)")
    print("  - docs/dev-docs/architecture.md   왜 dialectic, ADR 8개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
