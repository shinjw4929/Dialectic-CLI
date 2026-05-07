# Phase B1 · codex 어댑터 — 001-run-mode-core

## 0. 메타

- Phase ID: **B1**
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: A (`src/agents/base.py`, `src/schema.py:Meta`)
- 병렬 그룹: **B** (B1 codex ↔ B2 claude 동시 실행 가능)
- 예상 LOC: ~95

## 1. 목표

`CodexRunner` 작성 — `codex exec --json` 호출, JSONL 이벤트 파싱, `text`+`Meta` 추출. cwd 격리 + `--ephemeral`로 디스크 누수 차단.

## 2. 입력

- Phase A 산출물: `src/agents/base.py:AgentRunner`, `src/schema.py:Meta`.
- `docs/runtime-docs/protocol.md` §10 (`:342-355`, codex 호출 옵션 — 단 `--ephemeral`은 본 plan에서 추가).
- `docs/dev-docs/code-conventions.md` §3 (`:31-58`, subprocess 규약).
- 사전 검증된 사실 (00-plan.md §1.3):
  - `codex exec --json --sandbox read-only --skip-git-repo-check --ignore-rules --ephemeral -` 모두 존재.
  - 출력 이벤트 4종: `thread.started{thread_id}` / `turn.started` / `item.completed{item:{type:"agent_message", text}}` / `turn.completed{usage:{input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}}`.
  - **`model` 필드 부재** → `Meta.model = None` 고정.

## 3. 출력

### 3.1 `src/agents/codex.py` (신규, ~95 LOC)

```python
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
            timeout=timeout_s,
            cwd=workdir,            # 격리 강제 (ADR-6)
            env=env,
            check=False,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # raw stream 저장
        raw_log_path.write_text(result.stdout)

        # JSONL 이벤트 파싱
        text, thread_id, usage = self._parse_events(result.stdout)
        if not text:
            # 빈 응답 또는 parse_failure — kind=error로 환원은 orchestrator
            ...

        meta = Meta(
            vendor="openai", agent_cli="codex",
            model=None,             # codex 이벤트에 model 부재
            session_id=None, thread_id=thread_id,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cached_input_tokens=usage.get("cached_input_tokens", 0),
            reasoning_output_tokens=usage.get("reasoning_output_tokens", 0),
            cost_usd=None,          # codex는 cost 정보 부재 (None)
            latency_ms=latency_ms,
            is_mock=False,
            workdir=str(workdir),
        )
        return AgentResponse(text=text, raw_path=raw_log_path, meta=meta)
```

### 3.2 헬퍼

- `_build_env()` — `PATH`·`HOME`·`USER`·`LANG`만 통과. `CODEX_HOME` / `OPENAI_API_KEY` 등 auth 변수가 환경에 있으면 통과 (whitelist 상수에 명시).
- `_parse_events(stdout)` — 라인 단위 `json.loads`. `thread.started.thread_id` + `item.completed.item.text` 모음 + `turn.completed.usage` 추출. parse 실패 라인은 무시 (raw는 이미 저장됨).

## 4. 작업 단위

- [ ] `src/agents/codex.py` 생성 — `CodexRunner` 클래스, `run()` keyword-only 시그니처.
- [ ] `cmd_list`에 `--ephemeral` 명시 (claude `--no-session-persistence` 대응 — cwd 격리 보강).
- [ ] `subprocess.run` 호출에 `cwd=workdir`, `timeout=timeout_s`, `env=...`, `check=False`, `shell=True` 부재 검증.
- [ ] `_parse_events()` — 4 이벤트 타입 처리, `agent_message` text 모음, parse 실패 라인 skip.
- [ ] `meta.model = None` 명시 (codex 이벤트에 model 부재 — phase 메타 §2 사실 반영).
- [ ] `meta.cost_usd = None` (codex stream에 cost 정보 부재).
- [ ] `meta.is_mock = False` (정직성, `code-conventions.md` §4).
- [ ] auth 변수 화이트리스트 상수 정의 (`CODEX_HOME`, `OPENAI_API_KEY` 등 — 필요 변수만).
- [ ] **인증 실패 감지 → `AgentAuthError` raise** — `result.returncode != 0` + `stderr`에 `"not logged in"` / `"unauthorized"` / `"authentication"` (대소문자 무시) 포함 시 `raise AgentAuthError(stderr[:500])`. 그 외 비정상 종료는 `text=""` 반환(orchestrator가 빈 응답 분기에서 `_error_msg`로 환원). Day 2는 단순 패턴 매치 — 운영 중 stderr 패턴 누적 후 Day 3+에서 정교화.

## 5. 검증

- `python -c "from src.agents.codex import CodexRunner; r = CodexRunner(); assert r.name == 'codex' and r.vendor == 'openai'"` exit 0.
- 짧은 prompt 실 호출:
  ```python
  import tempfile; from pathlib import Path
  from src.agents.codex import CodexRunner
  wd = Path(tempfile.mkdtemp(prefix="dialectic-test-"))
  raw = wd / "raw.jsonl"
  resp = CodexRunner().run("Reply with single digit: 1+1=?", raw_log_path=raw, timeout_s=60, workdir=wd)
  assert resp.text and resp.meta.thread_id and resp.meta.model is None and resp.meta.is_mock is False
  ```
- raw_log_path 파일에 JSONL 이벤트 4종(thread.started/turn.started/item.completed/turn.completed) 존재.
- `cwd`가 `wd`(임시 dir)이지 dialectic repo 루트가 아님 — Phase D test_cwd_isolation에서 monkeypatch로 정식 검증.

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **`--ephemeral` 옵션이 향후 codex 버전에서 사라질 위험** — 현재 0.128.0 검증 완료. 어댑터에 옵션 명시 + Phase D에서 codex --version 점검(이미 env_check).
2. **빈 응답 (item.completed 0건)** — `text = ""`로 반환, orchestrator가 `kind=error, content="empty_response"` 처리.
3. **JSON parse 실패 라인** — raw는 보존, 어댑터는 skip + 마지막에 합산. 모든 라인 fail이면 `text=""` → empty_response.
4. **timeout (>300s)** — `subprocess.TimeoutExpired` raise → orchestrator catch하여 `kind=error, content="timeout"`.
5. **`reasoning_output_tokens`** — `usage`에 별도 필드로 등장. **결정 (P1 fix)**: `Meta.reasoning_output_tokens` 필드를 phase-a §3.1에서 신규 추가하여 별도 캡처 (silent 손실 방지). claude·mock은 0. 본 어댑터는 `usage.get("reasoning_output_tokens", 0)`로 추출 후 `Meta(reasoning_output_tokens=...)` 인자로 전달.
6. **OAuth 캐시 위치** — `CODEX_HOME` env 미설정 시 `~/.codex/`. `HOME`을 화이트리스트에 포함하면 동작. `CODEX_HOME` 명시되어 있으면 그것도 통과.
7. **`--ignore-rules`와 사용자 `.rules` 파일 — 의도된 무시** (P-VENDOR) — 사용자가 `--workdir <user-codebase>`에 `.rules`를 둔 시나리오에서 codex가 그것을 무시하도록 본 plan 결정 (`protocol.md` §10 :342-355 "ignore-rules: cwd의 `.rules` 파일 무시 (외부 영향 차단)"). 즉 사용자 codebase의 규칙이 driver의 응답에 반영되지 않음 — 의도된 동작이지만 사용자에게는 비자명. Day 3+에서 사용자가 자신의 `.rules`를 driver에게 전달하길 원하는 시나리오는 별도 옵션(`--respect-rules` 같은) 검토 권고. 본 plan 범위 밖.
