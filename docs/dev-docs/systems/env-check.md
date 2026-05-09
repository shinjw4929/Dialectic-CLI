# env-check — `dialectic doctor`

`src/env_check.py` (~52 LOC) 진리문서. claude/codex 인증·환경 점검 — 비용 0 (사용자 home에 `.mcp.json` 부재 시).

## 호출 표면

```bash
dialectic doctor   # 인자 없음
```

`src/cli.py`의 argparse subparser `doctor` → `_print_env_check()` → `check_env()`.

## check_env() 호출 4종 (벤더 대칭, P-VENDOR 환원 적용)

| 항목 | 명령 | timeout | 비용 |
|---|---|---|---|
| `claude.version` | `claude --version` | 5s | 0 |
| `claude.auth` | `claude auth status` | 10s | 0 (인증 상태 JSON 출력) |
| `codex.version` | `codex --version` | 5s | 0 |
| `codex.login` | `codex login status` | 10s | 0 (인증 상태) |

각 호출은 `_run_capture(cmd, env, timeout, cwd=None)` → `subprocess.run(... cwd=cwd or Path.home(), env=env, check=False)`.

## 병렬 호출 (plan 010-observability Phase B, 2026-05-09)

4개 sub-check는 `concurrent.futures.ThreadPoolExecutor(max_workers=4)`로 동시 실행 — 외부 의존성 0 (표준 라이브러리). wall clock 직렬 합 worst 30s → max(개별 timeout) worst 10s 수준 축소.

```python
specs = [
    ("claude", "version", ["claude", "--version"], 5),
    ("claude", "auth",    ["claude", "auth", "status"], 10),
    ("codex",  "version", ["codex", "--version"], 5),
    ("codex",  "login",   ["codex", "login", "status"], 10),
]
with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(lambda s: _run_capture(s[2], env=env_pass, timeout=s[3]), specs))
```

- `executor.map`은 입력 순서로 결과 yield → 별도 재정렬 불필요 (`as_completed` 미사용 — 완료 순서 비결정 회피)
- `_safe_env()` 1회 계산 후 4 future에 공유 (읽기 전용 dict 전달이라 race 없음)
- `_run_capture` 시그니처 변경 X — 호출자만 병렬화. subprocess는 process-level이라 4개 동시에 timeout 도달해도 future 독립
- 결과 dict insertion 순서 보존: claude/version → claude/auth → codex/version → codex/login (사용자 표 안정성)
- 측정: stub sleep 1s × 4 sub-check 시 직렬 합 4s 대비 병렬 wall clock ≤ 1.5s 단언 (`tests/test_env_check_parallel.py`)


**`claude doctor` 영구 제외** (validation.md §4.4 P-VENDOR 환원 사례 1, 2026-05-09):
- codex는 외부 subprocess로 부를 doctor 동등 명령 부재 (`/status`는 codex CLI 내부 슬래시 명령) — claude doctor만 호출 시 벤더 비대칭.
- `claude doctor`가 capture_output=True 호출 시 tty/pipe 분기로 30s+ hang (사용자 환경 사례: tty 0.5s vs subprocess 12s+ timeout).
- 본 도구 책임은 "두 CLI 설치 + 인증 통과"까지. doctor의 connectivity check 등은 claude CLI 자체 진단 — 외부 도구 scope.
- 사용자가 doctor 결과 필요 시 `claude doctor` 직접 호출.

## env 화이트리스트 (`_safe_env`)

```python
_SYS_VARS = ("PATH", "HOME", "USER", "LANG")
_AUTH_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CODEX_HOME")
# claude 어댑터(`agents/claude.py:_ENV_AUTH_PREFIXES`)와 동기화 — `CLAUDE_CODE_*` prefix 매칭.
# CLAUDE_CODE_OAUTH_TOKEN, CLAUDE_CODE_USE_BEDROCK 등 모든 변수 통과 (P-VENDOR 차단).
_AUTH_PREFIXES = ("CLAUDE_CODE_",)

def _safe_env() -> dict:
    return {k: os.environ[k] for k in (*_SYS_VARS, *_AUTH_VARS) if k in os.environ}
```

- `USER`/`LANG`은 본 plan 결정 (code-conventions.md §3 예시는 PATH/HOME/AUTH만 — §3 sync deferred)
- `_build_env`(어댑터) 화이트리스트와 중복 — `src/_env.py` 단일 진실 분리는 Day 3+ 검토 (narrative 권고만)

## cwd 정책 (P-CWD)

`_run_capture`의 `cwd=cwd or Path.home()` default — code-conventions §3 "cwd 명시 필수" P0 규약 준수. `Path.home()` 선택 이유:

- OAuth 캐시 위치 (`~/.claude/`, `~/.codex/`)에서 인증 정보 안정적 read
- Dialectic-CLI repo 루트가 아니라 ADR-6 두 층 누수와 무관
- (이전: 사용자 `~/.mcp.json` 존재 시 `claude doctor`가 stdio MCP 서버 spawn 부수효과 — doctor 영구 제외 후 무관)

## 출력 형식

```python
return {
    "claude": {
        "version": {"ok": bool, "stdout": str[:200], "stderr": str[:200]},
        "auth":    {...},
    },
    "codex": {
        "version": {...},
        "login":   {...},
    },
}
```

`_print_env_check()`가 ANSI 색상 표 형식으로 사용자에게 출력 (rich/textual 미사용 — 외부 의존성 0).

## 인증 미설정 환경 동작

- `auth/login status` 명령 non-zero exit 또는 "not logged in" 메시지 → `r["ok"] = False`
- 사용자에게 친절한 안내 (붉은 색 ANSI + README §환경설정 링크)
- mock fallback (outline/03 §3.1, §4.4 Q5·C): Day 2 mock 어댑터 미구현이라 활성 X. Day 3+ mock + `--mock <recording_dir>` + 자동 fallback 한 묶음

## 변경 시 갱신 영향

| 코드 변경 | 갱신 대상 |
|---|---|
| `check_env` 호출 항목 추가 | 본 §check_env() 표 + `cli.py _print_env_check` 출력 |
| `_safe_env` 화이트리스트 변수 추가 | 본 §env 화이트리스트 + `agents.md` `_build_env` (중복 동기화) + 향후 `code-conventions.md §3` 갱신 검토 |
| `_run_capture` 시그니처 (cwd 기본값 등) | 본 §cwd 정책 + `cwd-isolation.md` Layer 1 |
| timeout 변경 (예: auth 10s) | 본 §check_env() 표 |
| 신규 CLI 진단 명령 (Day 3+ `dialectic logs` 등) | 본 §호출 표면 → 신규 SSOT 또는 본 파일 확장 |

## 관련 문서

- `architecture.md` ADR-5 (mock 모드 + 인증 부재 자동 fallback)
- `code-conventions.md §3` (subprocess 규약 — env_check도 적용)
- `cwd-isolation.md` Layer 1 (subprocess `cwd=` 명시)
- `agents.md` (어댑터 `_build_env` 화이트리스트 동일 정책)
