"""ClaudeRunner — `claude -p ...` 어댑터.

protocol.md §10 (`:342-355`) + code-conventions.md §3 (`:31-58`) 정합.

- `--bare` 미사용: OAuth/keychain 인증 거부 명세 — Max 구독 OAuth 환경 비용 0 호출 우선.
  cwd 격리는 OS 차원(`subprocess.run(..., cwd=workdir)`)만 의존. `disable_bare` 토글은
  Day 4 ADR-9 후보로 deferred.
- `--append-system-prompt` 제거: 4섹션 prompt를 stdin 통째 전달 (protocol.md §5 일관).
- `--output-format json`: stdout이 단일 JSON 객체. parse 실패는 caller로 raise
  → orchestrator가 `kind=error`로 처리.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from ..schema import Meta
from .base import ERROR_CONTENT_TRUNCATE_CHARS, AgentAuthError, AgentResponse


# auth 변수 화이트리스트 — _build_env()에서 통과시킬 prefix/이름.
_ENV_BASE_KEYS = ("PATH", "HOME", "USER", "LANG")
_ENV_AUTH_KEYS = ("ANTHROPIC_API_KEY",)
_ENV_AUTH_PREFIXES = ("CLAUDE_CODE_",)

# 인증 실패 stderr 패턴 (대소문자 무시 substring 매치).
_AUTH_ERROR_PATTERNS = ("please log in", "unauthorized", "authentication")

# claude --max-budget-usd 비용 안전장치 (모듈 상수 — 변경 시 grep 한 곳).
_MAX_BUDGET_USD = "1.0"


class ClaudeRunner:
    name = "claude"
    vendor = "anthropic"

    def run(
        self,
        prompt: str,
        *,
        raw_log_path: Path,
        timeout_s: int,
        workdir: Path,
    ) -> AgentResponse:
        cmd = [
            "claude", "-p",
            "--tools", "",                  # 모든 툴 비활성 (텍스트 in/out만)
            "--no-session-persistence",     # 디스크 세션 비활성
            "--max-budget-usd", _MAX_BUDGET_USD,  # 비용 안전장치 (모듈 상수)
            "--output-format", "json",
            # --bare 미사용 — OAuth 거부 명세 + Max 구독 무료 호출 우선. cwd 격리는 OS 차원만.
            # --append-system-prompt 제거 — 4섹션 prompt를 stdin 통째 전달.
        ]
        env = self._build_env()
        t0 = time.monotonic()
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",               # P-ENCODING (R-001) — locale 의존 차단, 한국어 prompt 안전
            timeout=timeout_s,
            cwd=workdir,                    # 격리 강제 (ADR-6, 1차 방어선)
            env=env,
            check=False,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # raw stream 저장 — encoding="utf-8" 명시 (비ASCII UnicodeEncodeError 차단).
        # stderr도 함께 보존: returncode!=0 분기에서 디버깅 정보 손실 차단.
        raw_blob = result.stdout
        if result.stderr:
            raw_blob = f"{raw_blob}\n--- STDERR ---\n{result.stderr}"
        raw_log_path.write_text(raw_blob, encoding="utf-8")

        # 인증 실패 감지 — returncode != 0 + stderr에 auth 패턴 (substring 매치).
        # 패턴 미매치 시 silent 빈 응답 환원이지만 stderr 일부를 사용자에게 노출 — 디버깅 보강.
        # Day 3+ 운영 stderr 누적 후 패턴 정교화 또는 returncode 단독 분기 검토 (C-005 인접).
        if result.returncode != 0:
            stderr_lc = (result.stderr or "").lower()
            if any(p in stderr_lc for p in _AUTH_ERROR_PATTERNS):
                raise AgentAuthError((result.stderr or "")[:ERROR_CONTENT_TRUNCATE_CHARS])
            # 패턴 미매치 비정상 종료 — stderr 일부 노출 (silent 빈 응답 mitigation) + 빈 응답 fallback.
            stderr_excerpt = (result.stderr or "").strip()[:ERROR_CONTENT_TRUNCATE_CHARS] or None
            if stderr_excerpt:
                sys.stderr.write(
                    f"[ClaudeRunner] returncode={result.returncode}, auth 패턴 미매치 "
                    f"— 빈 응답 환원. stderr: {stderr_excerpt!r}\n"
                )
            return AgentResponse(
                text="",
                raw_path=raw_log_path,
                meta=self._empty_meta(latency_ms, workdir),
                stderr_excerpt=stderr_excerpt,
            )

        # 단일 JSON 응답 파싱 — parse 실패는 caller로 raise (orchestrator catch).
        payload = json.loads(result.stdout)
        text = payload.get("result", "") or payload.get("text", "")
        usage = payload.get("usage", {}) or {}
        meta = Meta(
            vendor="anthropic",
            agent_cli="claude",
            model=payload.get("model"),
            session_id=payload.get("session_id"),
            thread_id=None,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cached_input_tokens=usage.get("cache_read_input_tokens", 0),
            reasoning_output_tokens=0,      # claude는 reasoning 별도 보고 X — 0 고정
            cost_usd=payload.get("total_cost_usd"),
            latency_ms=latency_ms,
            is_mock=False,
            workdir=str(workdir),
        )
        return AgentResponse(text=text, raw_path=raw_log_path, meta=meta)

    @staticmethod
    def _build_env() -> dict[str, str]:
        """auth 화이트리스트 — 시스템 기본 + Anthropic auth 변수만 통과."""
        src = os.environ
        env: dict[str, str] = {}
        for k in _ENV_BASE_KEYS + _ENV_AUTH_KEYS:
            if k in src:
                env[k] = src[k]
        for k, v in src.items():
            if any(k.startswith(p) for p in _ENV_AUTH_PREFIXES):
                env[k] = v
        return env

    @staticmethod
    def _empty_meta(latency_ms: int, workdir: Path) -> Meta:
        """비정상 종료 fallback용 빈 Meta — `text=""`와 함께 반환."""
        return Meta(
            vendor="anthropic",
            agent_cli="claude",
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
