# Phase B2 · claude 어댑터 — 001-run-mode-core

## 0. 메타

- Phase ID: **B2**
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: A (`src/agents/base.py`, `src/schema.py:Meta`)
- 병렬 그룹: **B** (B1 codex ↔ B2 claude 동시 실행 가능)
- 예상 LOC: ~80

## 1. 목표

`ClaudeRunner` 작성 — `claude -p ...` 호출, JSON 응답 파싱, `text`+`Meta` 추출. cwd 격리(OS 차원)는 `subprocess.run(..., cwd=workdir)`로 보장. `--bare`(앱 차원 CLAUDE.md auto-discovery skip)는 OAuth/keychain 인증 거부 명세 때문에 본 plan 미사용 — Day 4 ADR-9(`disable_bare` 토글) 후보로 deferred.

## 2. 입력

- Phase A 산출물: `src/agents/base.py:AgentRunner`, `src/schema.py:Meta`.
- `docs/runtime-docs/protocol.md` §10 (`:342-355`, claude 호출 옵션 — 본 plan은 `--bare` 미사용, `--append-system-prompt` 제거).
- `docs/dev-docs/code-conventions.md` §3 (`:31-58`, subprocess 규약).
- 사전 검증된 사실 (00-plan.md §1.3):
  - `claude -p --tools "" --no-session-persistence --max-budget-usd 1.0 --output-format json` 모두 존재.
  - `claude --help` 명세: "Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read)" — `--bare` 사용 시 OAuth 거부. **본 plan은 Max OAuth 환경 비용 0 호출 보장을 위해 `--bare` 미사용**.
  - `-p --output-format json` 실 호출: 2.4s, OAuth 환경 비용 $0 (Max 구독 한도), `session_id`·`total_cost_usd`·`usage.cache_*` 포함.

## 3. 출력

### 3.1 `src/agents/claude.py` (신규, ~80 LOC)

```python
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
            "--max-budget-usd", "1.0",      # 비용 안전장치
            "--output-format", "json",
            # --bare 미사용 — OAuth 거부 명세 + Max 구독 무료 호출 우선. cwd 격리는 OS 차원(cwd=workdir)만.
            # --bare 토글은 Day 4 ADR-9 후보 (API key 사용자 대상 보강).
        ]
        env = self._build_env()
        t0 = time.monotonic()
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=workdir,                    # 격리 강제 (ADR-6, 1차 방어선)
            env=env,
            check=False,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        raw_log_path.write_text(result.stdout)

        # 단일 JSON 응답 파싱 (--output-format json)
        payload = json.loads(result.stdout)  # parse 실패는 caller로 raise → orchestrator가 kind=error
        text = payload.get("result", "") or payload.get("text", "")
        usage = payload.get("usage", {})
        meta = Meta(
            vendor="anthropic", agent_cli="claude",
            model=payload.get("model"),     # claude 응답에 model 포함
            session_id=payload.get("session_id"),
            thread_id=None,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cached_input_tokens=usage.get("cache_read_input_tokens", 0),
            reasoning_output_tokens=0,    # claude는 reasoning 별도 보고 안 함 — 0 고정
            cost_usd=payload.get("total_cost_usd"),
            latency_ms=latency_ms,
            is_mock=False,
            workdir=str(workdir),
        )
        return AgentResponse(text=text, raw_path=raw_log_path, meta=meta)
```

### 3.2 헬퍼

- `_build_env()` — `PATH`·`HOME`·`USER`·`LANG`만 + auth 화이트리스트 (`ANTHROPIC_API_KEY`, `CLAUDE_CODE_*` 등).

## 4. 작업 단위

- [ ] `src/agents/claude.py` 생성 — `ClaudeRunner` 클래스, `run()` keyword-only 시그니처.
- [ ] `cmd_list`에서 **`--append-system-prompt` 제거** — 4섹션 prompt 전체를 stdin으로 전달 (protocol.md §5와 일관). 본 변경은 protocol.md §8 line 305 cmd_list 갱신 필요 — Phase D §3.5 작업으로 동기화.
- [ ] `cmd_list`에 `--bare` 미사용 — OAuth 인증 거부 명세 우선. cwd 격리는 OS 차원(`cwd=workdir`)만 의존. 보안 보강은 Day 4 ADR-9 후보.
- [ ] `subprocess.run` 호출에 `cwd=workdir`, `timeout=timeout_s`, `env=...`, `check=False`, `shell=True` 부재 검증.
- [ ] JSON 파싱 — `result.stdout`이 단일 JSON 객체 (`--output-format json`).
- [ ] `Meta` 구성 — `session_id`·`model`·`cost_usd`·토큰 4종 추출.
- [ ] `meta.is_mock = False` (정직성).
- [ ] auth 변수 화이트리스트 상수 (`ANTHROPIC_API_KEY`, `CLAUDE_CODE_*`).
- [ ] **인증 실패 감지 → `AgentAuthError` raise** — `result.returncode != 0` + `stderr`에 `"please log in"` / `"unauthorized"` / `"authentication"` (대소문자 무시) 포함 시 `raise AgentAuthError(stderr[:500])`. JSON parse 실패는 caller로 `json.JSONDecodeError` raise (orchestrator가 catch 후 `_error_msg`). 그 외 비정상 종료는 `text=""` 반환. Day 2는 단순 패턴 매치 — 운영 중 stderr 패턴 누적 후 Day 3+에서 정교화.

## 5. 검증

- `python -c "from src.agents.claude import ClaudeRunner; r = ClaudeRunner(); assert r.name == 'claude' and r.vendor == 'anthropic'"` exit 0.
- 짧은 prompt 실 호출:
  ```python
  import tempfile; from pathlib import Path
  from src.agents.claude import ClaudeRunner
  wd = Path(tempfile.mkdtemp(prefix="dialectic-test-"))
  raw = wd / "raw.jsonl"
  resp = ClaudeRunner().run("Reply with single digit: 1+1=?", raw_log_path=raw, timeout_s=60, workdir=wd)
  assert resp.text and resp.meta.session_id and resp.meta.cost_usd is not None and resp.meta.is_mock is False
  ```
- raw_log_path에 단일 JSON 객체 저장.
- cwd 격리(OS 차원) 검증: Phase D `test_cwd_isolation_integration.py` 시나리오 A에서 dialectic repo 루트에 sentinel 마커 둔 채 임시 dir을 workdir로 호출 → raw stream에 마커 0회. monkeypatch 단위 테스트는 cmd_list에 `cwd=workdir` 인자 + `--bare` 부재 단언.

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **OAuth 호환 결정** (P-VENDOR) — claude `--bare`는 OAuth/keychain 인증 거부 명세. 본 plan은 Max 구독 OAuth 환경 무료 호출 보장을 위해 **`--bare` 미사용** 결정. cwd 격리는 OS 차원(subprocess `cwd=workdir`)만 의존. 단점: `--workdir <user-codebase>` 명시 시 그 코드베이스의 `CLAUDE.md`가 prompt에 흘러들어갈 위험 — 단 사용자가 명시적으로 그 디렉토리를 가리킨 동작이라 의도된 시나리오로 해석. `--workdir` 미명시(`tempfile.mkdtemp`) 시는 임시 dir에 `CLAUDE.md` 0이라 안전. Day 4 ADR-9 후보로 `disable_bare` 토글 + API key 사용자 대상 검증 deferred.
2. **`--max-budget-usd 1.0` 초과** — 응답 받기 전 차단 → `kind=meta, content="budget_exceeded"` orchestrator가 처리.
3. **JSON 파싱 실패** — `--output-format json` 명시했어도 stderr 섞이거나 빈 응답 가능. raw 보존 + `kind=error` 처리.
4. **`session_id` 없음** — 정상 응답에는 항상 포함되지만 부재 시 `None` 허용 (Meta 시그니처).
5. **timeout** — `subprocess.TimeoutExpired` raise → orchestrator catch.
6. **cwd 격리 단독 의존 — 진정성 검증 한계** (P-CWD/P-LEAK) — `--bare` 미사용으로 본 plan은 cwd 격리(OS 차원)에만 의존. `subprocess.run(..., cwd=workdir)`이 진짜 따라가는지는 OS·subprocess 표준 보장이지만, 진정한 ADR-6 검증(repo 루트의 CLAUDE.md 누수 0)은 통합 테스트 필요 — phase-d §3.4 시나리오 A로 검증. Day 4 ADR-9 결정 시 `--bare` 토글로 2층 방어선까지 검증.
