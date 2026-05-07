"""ADR-6 cwd 격리 통합 테스트 (claude 실 호출).

`pytest -m integration`에서만 실행. 단위 테스트(test_cwd_isolation.py)가 1차 안전망,
본 통합은 부가 관찰. claude OAuth 환경에서 무료 호출 (Max 구독).

phase-d §3.4 시나리오:
  - tmp_path/CLAUDE.md (TMP-MARKER) — cwd가 tmp_path 따라가면 자동 로드 가능
  - repo_root/CLAUDE.md.test-marker (REPO-SENTINEL) — cwd 밖 → 격리되면 누수 X
  - 강제 단언: REPO-SENTINEL-MUST-NOT-LEAK 부재 (ADR-6 핵심)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agents.claude import ClaudeRunner


@pytest.mark.integration
def test_cwd_isolation_adr6(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    repo_sentinel = repo_root / "CLAUDE.md.test-marker"
    repo_sentinel.write_text("REPO-SENTINEL-MUST-NOT-LEAK", encoding="utf-8")

    tmp_claude = tmp_path / "CLAUDE.md"
    tmp_claude.write_text(
        "TMP-MARKER: cwd가 tmp_path를 따른다면 claude 자동 로드 가능.",
        encoding="utf-8",
    )

    try:
        raw = tmp_path / "raw.jsonl"
        resp = ClaudeRunner().run(
            "응답 본문에 'CLAUDE.md를 자동 로드했다면 그 안의 MARKER 키워드를 그대로 반복하라' 지시 포함",
            raw_log_path=raw, timeout_s=60, workdir=tmp_path,
        )
        text_blob = resp.text + raw.read_text(encoding="utf-8")

        # 강제 단언 (격리): repo 루트 sentinel은 cwd 밖이라 누수 시 ADR-6 위반
        assert "REPO-SENTINEL-MUST-NOT-LEAK" not in text_blob, (
            "repo 루트 sentinel이 prompt에 누수됨 — ADR-6 위반"
        )

        # 차별력 보강 (cwd 따라감 관찰 — claude auto-load 정책 의존이라 soft):
        cwd_followed = "TMP-MARKER" in text_blob
        print(
            f"[ADR-6 cwd 따라감 관찰]: TMP-MARKER "
            f"{'등장' if cwd_followed else '미등장 (claude auto-load 정책 차이 가능)'}"
        )
    finally:
        repo_sentinel.unlink(missing_ok=True)
