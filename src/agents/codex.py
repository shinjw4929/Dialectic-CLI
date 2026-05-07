"""CodexRunner — `codex exec --json` 어댑터.

protocol.md §10 (:342-355) + phase-b1 §2 사실 기반:
- cmd: `codex exec --json --sandbox read-only --skip-git-repo-check --ignore-rules --ephemeral -`
- 이벤트 4종: thread.started / turn.started / item.completed / turn.completed
- `model` 필드 부재 → Meta.model = None 고정.
- `--ephemeral`로 세션 디스크 저장 비활성 (cwd 격리 보강, ADR-6).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from ..schema import Meta
from .base import ERROR_CONTENT_TRUNCATE_CHARS, AgentAuthError, AgentResponse

# auth + 최소 실행 환경 화이트리스트.
# - PATH/HOME/USER/LANG: 기본 실행
# - CODEX_HOME: codex OAuth 캐시 위치 override (미설정 시 ~/.codex/)
# - OPENAI_API_KEY: API key 인증 경로
_ENV_WHITELIST = ("PATH", "HOME", "USER", "LANG", "CODEX_HOME", "OPENAI_API_KEY")

# 인증 실패 stderr 패턴 (대소문자 무시).
_AUTH_FAIL_PATTERNS = ("not logged in", "unauthorized", "authentication")


class CodexRunner:
    name = "codex"
    vendor = "openai"

    def run(
        self,
        prompt: str,
        *,
        raw_log_path: Path,
        timeout_s: int,
        workdir: Path,
    ) -> AgentResponse:
        cmd = [
            "codex", "exec",
            "--json",
            "--sandbox", "read-only",
            "--skip-git-repo-check",
            "--ignore-rules",
            "--ephemeral",          # 세션 디스크 저장 비활성 (cwd 격리 보강)
            "-",                    # stdin 모드
        ]
        env = self._build_env()     # PATH·HOME·USER·LANG + auth 화이트리스트
        t0 = time.monotonic()
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",       # P-ENCODING (R-001) — locale 의존 차단, 한국어 prompt 안전
            timeout=timeout_s,
            cwd=workdir,            # 격리 강제 (ADR-6)
            env=env,
            check=False,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # raw stream 저장 (어댑터 책임 — parse 실패 라인·stderr 보존용).
        # encoding="utf-8" 명시 — 시스템 기본 인코딩 의존 차단 (비ASCII stream UnicodeEncodeError 방지).
        # stderr도 함께 디스크 보존: returncode!=0 분기에서 디버깅 정보 손실 차단.
        raw_blob = result.stdout
        if result.stderr:
            raw_blob = f"{raw_blob}\n--- STDERR ---\n{result.stderr}"
        raw_log_path.write_text(raw_blob, encoding="utf-8")

        # 인증 실패 감지 — orchestrator가 catch하여 README §환경설정 안내.
        if result.returncode != 0:
            stderr_lower = (result.stderr or "").lower()
            if any(p in stderr_lower for p in _AUTH_FAIL_PATTERNS):
                raise AgentAuthError((result.stderr or "")[:ERROR_CONTENT_TRUNCATE_CHARS])
            # 그 외 비정상 종료: claude 어댑터와 동일 패턴으로 즉시 빈 응답 반환 (P-VENDOR 비대칭 차단).
            # _parse_events fall-through 시 partial Meta가 박혀 forensic 비대칭 발생 — 둘 다
            # text="" + empty_meta로 통일하여 orchestrator의 _error_msg 환원이 일관 동작.
            # stderr_excerpt 보존 — protocol.md §9 정합 (P-STDERR_LOSS, _error_msg content 합성).
            stderr_excerpt = (result.stderr or "").strip()[:ERROR_CONTENT_TRUNCATE_CHARS] or None
            return AgentResponse(
                text="",
                raw_path=raw_log_path,
                meta=self._empty_meta(latency_ms, workdir),
                stderr_excerpt=stderr_excerpt,
            )

        # JSONL 이벤트 파싱.
        text, thread_id, usage = self._parse_events(result.stdout)

        meta = Meta(
            vendor="openai",
            agent_cli="codex",
            model=None,             # codex 이벤트에 model 부재
            session_id=None,
            thread_id=thread_id,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cached_input_tokens=usage.get("cached_input_tokens", 0),
            reasoning_output_tokens=usage.get("reasoning_output_tokens", 0),
            cost_usd=None,          # codex stream에 cost 정보 부재
            latency_ms=latency_ms,
            is_mock=False,
            workdir=str(workdir),
        )
        return AgentResponse(text=text, raw_path=raw_log_path, meta=meta)

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_env() -> dict[str, str]:
        """환경변수 화이트리스트 통과 — 외부 영향 차단 + auth 통로 보존."""
        return {k: os.environ[k] for k in _ENV_WHITELIST if k in os.environ}

    @staticmethod
    def _empty_meta(latency_ms: int, workdir: Path) -> Meta:
        """비정상 종료 fallback용 빈 Meta — `text=""`와 함께 반환 (claude 어댑터와 동일 패턴)."""
        return Meta(
            vendor="openai",
            agent_cli="codex",
            model=None,
            session_id=None,
            thread_id=None,
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=0,
            reasoning_output_tokens=0,
            cost_usd=None,
            latency_ms=latency_ms,
            is_mock=False,
            workdir=str(workdir),
        )

    def _parse_events(
        self, stdout: str
    ) -> tuple[str, str | None, dict[str, Any]]:
        """JSONL 이벤트에서 (text, thread_id, usage) 추출.

        - thread.started.thread_id → thread_id
        - item.completed.item.text (type == "agent_message") → text 누적
        - turn.completed.usage → usage dict
        - parse 실패 라인은 raw에 보존 + skip.
        - item.completed 0건이면 text="" (orchestrator가 empty_response 환원).
        """
        text_parts: list[str] = []
        thread_id: str | None = None
        usage: dict[str, Any] = {}

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue  # raw는 이미 저장됨

            etype = evt.get("type")
            if etype == "thread.started":
                tid = evt.get("thread_id")
                if isinstance(tid, str):
                    thread_id = tid
            elif etype == "item.completed":
                item = evt.get("item") or {}
                if item.get("type") == "agent_message":
                    txt = item.get("text")
                    if isinstance(txt, str):
                        text_parts.append(txt)
            elif etype == "turn.completed":
                u = evt.get("usage") or {}
                if isinstance(u, dict):
                    usage = u

        text = "\n".join(text_parts) if text_parts else ""
        return text, thread_id, usage
