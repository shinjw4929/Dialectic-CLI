"""AgentRunner Protocol + AgentResponse + AgentAuthError.

code-conventions.md §5 정합:
- 모든 어댑터(codex / claude / mock)가 동일 시그니처 준수.
- `run()`은 keyword-only 인자(`*`) — 인자 순서 의존 차단.
- `AgentResponse`는 frozen — 호출 후 변경 불가.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..schema import Meta

# 어댑터·orchestrator의 stderr/exception 메시지 truncation 길이 — 매직 넘버 회피.
# 너무 길면 messages.jsonl 라인 비대 + 사용자 가독성 ↓, 너무 짧으면 디버깅 정보 손실.
ERROR_CONTENT_TRUNCATE_CHARS = 500


@dataclass(frozen=True, slots=True)
class AgentResponse:
    text: str
    raw_path: Path
    meta: Meta            # schema.Meta 재사용
    # 비정상 종료(returncode != 0 + 비-auth 분기)에서 어댑터가 stderr 발췌 보존.
    # orchestrator 빈 응답 분기에서 _error_msg content에 합성 — protocol.md §9 정합 (P-STDERR_LOSS).
    # 정상 응답이거나 raw_log_path만으로 충분한 경우 None.
    stderr_excerpt: str | None = None


class AgentAuthError(Exception):
    """인증 실패 — orchestrator가 catch하여 README §환경설정 안내."""


class AgentRunner(Protocol):
    name: str
    vendor: str

    def run(
        self,
        prompt: str,
        *,
        raw_log_path: Path,
        timeout_s: int,
        workdir: Path,
    ) -> AgentResponse: ...
