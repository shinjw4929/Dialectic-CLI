"""JSONL append-only message bus.

code-conventions.md §4 정합:
- 매 append 후 `f.flush()` 강제 (프로세스 죽어도 부분 기록 보존).
- update / delete API 미노출 (append-only 보장).
- 빈 파일 → `read_all()`은 `[]` 반환.
"""

import json
import os
import sys
from pathlib import Path

from .schema import Message


class Bus:
    """JSONL 한 줄 = 한 메시지. 라인 순서 = 시간 순 (append-only)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, msg: Message) -> None:
        """메시지를 JSONL 라인으로 append. f.flush() + os.fsync() 강제 — JSONL 무결성 (P-JSONL).

        f.flush()는 Python 버퍼만 OS로 이동, OS 페이지 캐시는 메모리 — 강제 종료 시 손실 가능.
        os.fsync(f.fileno())로 디스크 sync 강제. 매 메시지 fsync 비용은 한 턴 E2E 단위에선 미미
        (라인 4~5개). max-turns 확장 또는 compare 모드 병렬 시 fsync 정책 재검토 (ADR 갱신 후 결정).
        """
        line = json.dumps(msg.to_dict(), ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

    def read_all(self) -> list[Message]:
        """파일 라인 순서대로 모든 메시지를 반환. 빈 파일 → [].

        손상 라인(JSONDecodeError) 1개로 전체 read_all() 실패 차단 (P-JSONL):
        - 손상 라인은 skip + stderr 경고 (raw 라인은 파일에 그대로 보존)
        - orchestrator가 `read_all()[-1].msg_id` 패턴으로 직전 메시지 추출 시
          단일 손상 라인이 turn 전체 종료를 막지 않음
        """
        if not self.path.exists():
            return []
        messages: list[Message] = []
        with open(self.path, "r", encoding="utf-8") as raw:
            for lineno, raw_line in enumerate(raw, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    sys.stderr.write(
                        f"[Bus.read_all] {self.path}:{lineno} JSONDecodeError "
                        f"({exc.msg}) — 라인 skip, raw 보존됨\n"
                    )
                    continue
                # Message.from_dict()는 KeyError/TypeError → ValueError raise (schema.py).
                # JSON 문법은 맞지만 schema 깨진 라인(필수 키 누락 등) 1개로 전체 read 실패 차단 (P-JSONL).
                try:
                    messages.append(Message.from_dict(payload))
                except ValueError as exc:
                    sys.stderr.write(
                        f"[Bus.read_all] {self.path}:{lineno} schema ValueError "
                        f"({exc}) — 라인 skip, raw 보존됨\n"
                    )
                    continue
        return messages
