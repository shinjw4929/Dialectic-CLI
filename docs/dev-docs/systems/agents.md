# agents — `AgentRunner` Protocol + `CodexRunner` / `ClaudeRunner`

`src/agents/{base,codex,claude}.py` 진리문서.

## AgentRunner Protocol (base.py)

```python
@dataclass(frozen=True, slots=True)
class AgentResponse:
    text: str
    raw_path: Path
    meta: Meta
    stderr_excerpt: str | None = None   # 비정상 종료 시 stderr 발췌 (P-STDERR_LOSS round 7 fix)


class AgentRunner(Protocol):
    name: str             # "codex" | "claude" | "mock"
    vendor: str           # "openai" | "anthropic" | "mock"

    def run(
        self,
        prompt: str,
        *,
        raw_log_path: Path,
        timeout_s: int,
        workdir: Path,
    ) -> AgentResponse: ...
```

**규약**:
- keyword-only 인자 (`*` 강제) — 인자 순서 의존 차단
- 어댑터 본문 `subprocess.run(..., cwd=workdir, encoding="utf-8")` 명시 (ADR-6 + R-001)
- raw stream을 `raw_log_path`에 직접 저장 (orchestrator 후처리 X)
- 인증 실패는 `AgentAuthError` raise — 일반 비정상 종료는 `text="" + stderr_excerpt=stderr[:N]` 반환 (orchestrator가 빈 응답 분기에서 `_error_msg` content에 합성, protocol.md §9 정합)

## CodexRunner

### cmd_list

```python
["codex", "exec", "--json", "--sandbox", "read-only",
 "--skip-git-repo-check", "--ignore-rules", "--ephemeral", "-"]
```

| 옵션 | 효과 |
|---|---|
| `--json` | JSONL 이벤트 출력 |
| `--sandbox read-only` | 코드 실행 X, 파일 수정 X |
| `--skip-git-repo-check` | 임시 cwd에서도 동작 |
| `--ignore-rules` | cwd `.rules` 무시 (외부 영향 차단). 사용자 `--workdir <user-codebase>` 시나리오에서 의도된 무시 — Day 3+ `--respect-rules` 옵션 검토 |
| `--ephemeral` | 세션 디스크 저장 비활성 (cwd 격리 보강) |
| `-` | stdin 모드 |

### JSONL 이벤트 4종 파싱

```python
thread.started{thread_id}     → Meta.thread_id
turn.started                  → (관찰만)
item.completed{item:{type:"agent_message", text}}  → text 누적
turn.completed{usage:{input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}}  → Meta usage
```

parse 실패 라인은 `raw_log_path`에 보존 + skip. 모두 fail이면 `text=""` 반환.

### Meta 채움

- `vendor="openai"`, `agent_cli="codex"`
- `model=None` (codex 이벤트에 model 필드 부재 — 정직성)
- `session_id=None`, `thread_id=<thread.started.thread_id>`
- `cost_usd=None` (codex stream에 cost 정보 부재)
- `reasoning_output_tokens=usage.get("reasoning_output_tokens", 0)` (codex만 보고)
- `convergence_streak` 미전달 → default None (orchestrator가 critique 분기에서 갱신)

### auth 화이트리스트

`_ENV_WHITELIST = ("PATH", "HOME", "USER", "LANG", "CODEX_HOME", "OPENAI_API_KEY")` — `_build_env()`가 통과.

### 인증 실패 감지

`returncode != 0` + `stderr.lower()`에 `("not logged in", "unauthorized", "authentication")` 중 하나 포함 → `raise AgentAuthError(stderr[:500])`.

## ClaudeRunner

### cmd_list

```python
["claude", "-p",
 "--tools", "",
 "--no-session-persistence",
 "--max-budget-usd", "1.0",
 "--output-format", "json"]
```

| 옵션 | 효과 |
|---|---|
| `--tools ""` | 모든 툴 비활성 (텍스트 in/out만) |
| `--no-session-persistence` | 디스크 세션 비활성 |
| `--max-budget-usd 1.0` | 비용 안전장치 |
| `--output-format json` | stdout이 단일 JSON 객체 |

### 미사용 옵션 (의도적 부재)

| 옵션 | 미사용 사유 |
|---|---|
| `--bare` | OAuth/keychain 인증 거부 명세 — Max OAuth 환경 비용 0 호출 우선. cwd 격리는 OS 차원만 의존. Day 4 `disable_bare` 토글 ADR-9 후보 deferred |
| `--append-system-prompt` | 4섹션 prompt를 stdin 통째 전달 (`protocol.md §5` 일관) |

### JSON 응답 파싱

`payload = json.loads(result.stdout)`. parse 실패는 caller로 raise (`json.JSONDecodeError`) — orchestrator가 catch.

### Meta 채움

- `vendor="anthropic"`, `agent_cli="claude"`
- `model=payload.get("model")`, `session_id=payload.get("session_id")`, `thread_id=None`
- `cost_usd=payload.get("total_cost_usd")` (Max OAuth 환경에서 추정 표시, 실 청구 0)
- `cached_input_tokens=usage.get("cache_read_input_tokens", 0)` (claude 명명)
- `reasoning_output_tokens=0` (claude 별도 보고 X — 0 고정, 정직성)

비정상 종료(returncode != 0 + auth 패턴 不매치) 시 `_empty_meta()` fallback으로 14 필드 강제 채움 + `text=""` 반환.

### auth 화이트리스트

`_ENV_BASE_KEYS = ("PATH","HOME","USER","LANG")` + `_ENV_AUTH_KEYS = ("ANTHROPIC_API_KEY",)` + `_ENV_AUTH_PREFIXES = ("CLAUDE_CODE_",)` — `_build_env()`가 통과.

## 횡단 패턴 (P-ENCODING + P-STDERR_LOSS 차단)

두 어댑터 모두:

```python
raw_blob = result.stdout
if result.stderr:
    raw_blob = f"{raw_blob}\n--- STDERR ---\n{result.stderr}"
raw_log_path.write_text(raw_blob, encoding="utf-8")
```

- `encoding="utf-8"` 명시 — 시스템 기본 인코딩 의존 차단 (P-ENCODING)
- stderr 디스크 보존 — returncode!=0 분기에서 디버깅 정보 손실 차단 (P-STDERR_LOSS)

## 어댑터 비대칭 (P-VENDOR 잠재 위험)

| 항목 | codex | claude |
|---|---|---|
| `model` | None (이벤트에 부재) | `payload["model"]` |
| `session_id` / `thread_id` | thread_id만 | session_id만 |
| `cost_usd` | None | `total_cost_usd` |
| `reasoning_output_tokens` | usage 보고 | 0 고정 |
| `cached_input_tokens` 키명 | `cached_input_tokens` | `cache_read_input_tokens` |
| 비정상 종료 fallback | `text=""` 직접 반환 | `_empty_meta()` 헬퍼 |

비대칭은 어댑터 본문에 캡슐화 — orchestrator는 `AgentRunner` Protocol 인터페이스만 봄.

## 변경 시 갱신 영향

| 코드 변경 | 갱신 대상 |
|---|---|
| cmd_list 옵션 추가/제거 | 본 §cmd_list 표 + `protocol.md §10` (호출 옵션) + `tests/test_cwd_isolation.py` cmd_list 단언 |
| Meta 채움 필드 추가 | 본 §Meta 채움 + `jsonl-bus.md` §Meta + `protocol.md §2` |
| 인증 실패 stderr 패턴 | 본 §인증 실패 감지 + `tests/` (필요 시 신규) |
| auth 화이트리스트 변수 | 본 §auth 화이트리스트 + `code-conventions.md §3` 예시 (현재 USER/LANG 추가는 본 plan 결정, §3 sync deferred) |
| 신규 어댑터 (mock 등) | 본 §어댑터 비대칭 표 + `agents.md` 신규 §섹션 + `_resolve_runner` choices 갱신 |

## 관련 문서

- `architecture.md` ADR-2 (벤더 비대칭 흡수 — 어댑터 단일 인터페이스)
- `protocol.md §8` (어댑터 인터페이스), §10 (호출 옵션)
- `code-conventions.md §3` (subprocess 규약), §5 (`AgentRunner`)
- `validation.md` P-VENDOR / P-ENCODING / P-STDERR_LOSS
