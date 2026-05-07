# Validation — 결함 패턴 → 규칙 환원

> 본 도구를 운영하면서 **반복 발견된 결함 패턴을 규칙으로 추출**하여 다음 세션부터 같은 결함이 자동 차단되도록 적재한다. 4계층 중 **Validation 계층**의 핵심 자산.

본 문서는 운영 중에 채워진다. 초기 상태는 스켈레톤 (구조만 정의).

---

## 0. 환원 흐름

```
결함 발견 (review-plan / review-code / 사용자 발견)
    ↓
1회성? → 단순 수정 권고만 (본 문서에 추가 X)
반복? → 본 문서에 규칙으로 추가 + 관련 .md/스킬에 검사 항목으로 승격
    ↓
다음 작업부터 자동 차단
```

**판정 기준** (반복으로 분류):
- 같은 도메인에서 2회 이상 발견
- 다른 도메인이지만 패턴이 동일 (예: 어댑터마다 cwd 누락)
- 사용자가 "이건 반복될 결함이다"라고 직관적으로 판단

---

## 1. 규칙 카탈로그

각 규칙은 다음 형식:

```markdown
### R-NNN: <규칙 이름>

- **계층**: Context / Knowledge / Protocol / Validation 중 하나
- **도메인**: 안전성 / 인터페이스 / 컨벤션 / spec / plan / 등
- **발견 경로**: review-code · review-plan · 사용자 발견 등
- **발견 횟수**: N회 (시점)
- **규칙**: <검사 가능 표현>
- **위반 시**: P0 / P1 / P2
- **승격 대상**: <어느 .md/체크리스트에 추가됐나>
- **사례**:
  1. <발견 1: 어떤 작업에서, 어떤 코드/문서에서>
  2. <발견 2>
```

---

## 2. 현재 적재된 규칙

### R-001: 파일 I/O `encoding="utf-8"` 명시 필수 (P-ENCODING)

- **계층**: Knowledge (안전성 — 인코딩 무결성)
- **도메인**: 안전성 — 파일 I/O 시스템 기본 인코딩 의존 차단
- **발견 경로**: review-code (Day 2 round 1·3 누적)
- **발견 횟수**: **5회** → 정식 환원 (2026-05-08)
- **규칙**: 모든 `Path.read_text()` / `Path.write_text()` / `open()` 호출에 `encoding="utf-8"` 명시. 누락 시 P0.
  - **이유**: 시스템 기본 인코딩 의존 → 비UTF-8 환경에서 UnicodeDecodeError/UnicodeEncodeError. 한국어 본문(role.md, narrative test) + 비ASCII raw stream 모두 위험.
- **위반 시**: **P0** (review-code-checklist.md §1 안전성 도메인 등재)
- **승격 대상**:
  - `docs/dev-docs/Checklists/review-code-checklist.md` §1 안전성 P0 행 (✓ Day 2 적재)
  - `docs/dev-docs/code-conventions.md` §3·§4 narrative 추가 검토 (deferred — 다음 §3·§4 갱신 시 함께)
- **사례** (8회 누적 — 3 라운드 review-code 발견):
  1. `src/agents/codex.py:67` `raw_log_path.write_text(result.stdout)` — round 1 fix → `encoding="utf-8"`
  2. `src/agents/claude.py:69` 동일 패턴 — round 1 fix
  3. `src/orchestrator.py:116` `ROLE_FILE[role].read_text()` (P0, 한국어 role.md) — round 3 fix
  4. `tests/test_cwd_isolation_integration.py:28` `tmp_claude.write_text(한국어)` (P1) — round 3 fix
  5. `tests/test_cwd_isolation_integration.py:25,36` `repo_sentinel.write_text` + `raw.read_text` (P2, ASCII이지만 컨벤션) — round 3 fix
  6. **`src/agents/codex.py:55` `subprocess.run(text=True, input=prompt)` encoding 미명시** (P0, 한국어 prompt → `LC_ALL=C PYTHONUTF8=0`에서 UnicodeEncodeError + orchestrator error JSONL 우회) — round 5 fix
  7. **`src/agents/claude.py:60` 동일 패턴** (P0) — round 5 fix
  8. **`src/env_check.py:60` `_run_capture` `subprocess.run(text=True)` encoding 미명시** (P1, localized CLI 출력 decode 실패 가능) — round 5 fix
  - 추가 narrative 정정 (P1, round 5): `docs/dev-docs/systems/cwd-isolation.md:90` + `orchestrator.md:41` 신규 systems 문서 예시가 R-001과 충돌하는 형태 (encoding 없는 `write_text/read_text`) — fix 적용
- **검사 자동화**: `grep -nE "(read_text|write_text|open|subprocess\.run)\(" src/ tests/` 후 `encoding=` 인자 부재 시 P0 보고. **subprocess.run의 text=True 케이스도 포함** (round 5에서 누락 catch됨 — 검사 패턴 광역화 필요).
- **관련 §3 후보**: C-006 (본 R-001로 승격됨, §3에서 §2로 이동 narrative)

---

## 3. 환원 가능 후보 (관찰 중)

규칙으로 승격할지 결정 전 단계. 1회만 발견된 결함을 잠정 적재.

### C-001: deserialize 손상 라인 단일 발견으로 전체 read 실패 금지

- **계층**: Knowledge (인터페이스 무결성)
- **도메인**: 인터페이스 — JSONL 무결성
- **발견 경로**: review-code (Day 2 commit 직전)
- **발견 횟수**: 1회 (2026-05-08)
- **연관 P-id**: **P-JSONL**
- **패턴**: `Bus.read_all()`이 `json.JSONDecodeError`/`Message.from_dict()` `KeyError` 손상 라인 1개로 전체 read 실패. orchestrator가 `read_all()[-1].msg_id` 패턴으로 직전 메시지 추출 시 단일 손상 라인이 turn 전체 종료를 막음.
- **fix 패턴 (이번 라운드 적용)**:
  - `bus.py:read_all()` — `try/except json.JSONDecodeError` → stderr 경고 + raw 라인 보존 + 손상 라인 skip + lineno 표시
  - `schema.py:from_dict()` — `try/except (KeyError, TypeError)` → 친절 ValueError + dict keys 보존 (`raise from exc`)
- **승격 판정 (다음 발견 시)**: 같은 패턴이 새 어댑터/모드/저장소(`tasks/<task>/recordings/` mock)에서 재발 시 → R-NNN으로 정식 환원 + `review-code-checklist.md` §2 "JSONL 무결성" P0 행으로 승격

### C-002: frozen dataclass protocol invariant self-가드

- **계층**: Knowledge (인터페이스 정합성)
- **도메인**: 인터페이스 — 직접 인스턴스 생성 경로 자기 검증
- **발견 경로**: review-code (Day 2)
- **발견 횟수**: 1회 (2026-05-08)
- **연관 P-id**: **P-INVARIANT** (신규 — §4.4 표 등재)
- **패턴**: `Message`/`Meta` frozen dataclass의 protocol-level invariant(`ts` ISO8601 Z 형식, `from`/`kind`/`mode` enum 값 집합 등)가 `__post_init__` self-가드 X 상태. orchestrator `_now_ts()` 같은 단일 진입점이 형식을 박지만 어댑터·테스트가 직접 `Message(ts=...)` 생성 경로에서는 자기 검증 부재. test 단독 검증은 fail-late.
- **fix 패턴 (이번 라운드 적용)**:
  - `schema.py` 모듈 레벨 `_TS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")`
  - `Message.__post_init__()` 정규식 단언 → 위반 시 ValueError
- **승격 판정 (다음 발견 시)**: 다른 invariant(예: `kind` enum 미준수, `seq_in_turn` 음수)가 직접 인스턴스 생성 경로에서 누수되면 → R-NNN 환원 + 본 패턴을 `Meta.__post_init__`으로 확장 권고

### C-003: Protocol/공통 base의 어댑터 책임 docstring 명시 (P-VENDOR 인접)

- **계층**: Knowledge (인터페이스 명세)
- **도메인**: 인터페이스 — 어댑터 비대칭 사전 차단
- **발견 경로**: review-code (Day 2)
- **발견 횟수**: **3회 누적** (2026-05-08 review-code 2 라운드)
  1. **R1 사례 (예방적)**: `AgentRunner.run()` Protocol 정의에 docstring 부재 — 어댑터 책임이 시그니처에 미반영
  2. **R2 사례 (실제 비대칭)**: `codex.py:76-86` returncode!=0 + 비-auth 분기에서 `_parse_events` fall-through (partial Meta) vs `claude.py:77-86` 즉시 `_empty_meta` 반환. 같은 비정상 종료에 응답 형태 불일치, claude 쪽 token usage 정직성 손실 → **fix 적용**: codex도 즉시 `text="" + _empty_meta()` 반환 (claude 패턴 통일)
  3. **R2 사례 (env 화이트리스트 비대칭)**: `claude.py:_ENV_AUTH_PREFIXES = ("CLAUDE_CODE_",)` (run 시점) ↔ `env_check.py:_AUTH_VARS` (doctor 시점) 비대칭 — `CLAUDE_CODE_USE_BEDROCK` 등 다른 변수 환경에서 doctor와 실 호출 env 다름 → **fix 적용**: env_check에 `_AUTH_PREFIXES` prefix 매칭 추가 (어댑터 정책 동기화)
- **연관 P-id**: **P-VENDOR**
- **fix 패턴 (Day 3 mock 어댑터 추가 시 정식 환원 R-NNN 권고)**:
  - `AgentRunner.run()` docstring에 어댑터 계약 명시 (raw 저장 책임 + 빈 응답 패턴 + 인증 실패 raise + Meta 14 필드 + returncode!=0 응답 형태 통일)
  - 어댑터 ↔ env_check 정책 단일 진실원 분리 (`src/_env.py` narrative 권고 — phase-c §3.3 명시)
- **승격 판정**: 3회 누적 + mock 어댑터(Day 3+) 작성 중 4번째 비대칭 발견 시 즉시 R-NNN으로 §2에 환원
- **deferred 결정 (2026-05-08)**: 사례 1쌍(codex/claude 어댑터)만이라 narrative 풍부도 약함. mock 어댑터(Day 3+) 작업 중 새 비대칭 발견 시 R-002로 정식 환원 — Day 2 commit 시점에는 §3 후보 상태 유지. **Day 3 plan 진입 시 cross-check**: 첫 작업으로 본 §3 C-003 검사 + mock 어댑터 작업이 P-VENDOR 비대칭 통로인지 확인.

### C-004: argparse `type=int` 단독 음수/0 의미 오류 통과 (P-CLI_GUARD 신규)

- **계층**: Knowledge (인터페이스 — CLI 인자 검증)
- **도메인**: 컨벤션 — argparse 가드 패턴
- **발견 경로**: review-code (Day 2 round 2)
- **발견 횟수**: 1회 (2026-05-08)
- **연관 P-id**: **P-CLI_GUARD** (신규 §4.4 표 등재)
- **패턴**: `--max-turns type=int default=1` / `--convergence-streak type=int default=2` — argparse `type=int`는 변환만 검증, 음수/0 가드 X. 의미 오류 입력(예: `--max-turns 0` 빈 루프, `--convergence-streak 0` streak >= 0 분기 즉시 종료)이 silently 통과하여 ADR-9 fallback 의도와 어긋남.
- **fix 패턴 (이번 라운드 적용)**: `src/cli.py:_positive_int(raw)` 헬퍼 — argparse `type=_positive_int` 적용. 1 미만 입력 시 `ArgumentTypeError` raise + 친절 메시지.
- **승격 판정**: 새 CLI 인자 추가(Day 3+ `--max-budget-usd`, `--timeout`, `--mock <recording_dir>` 등) 중 같은 패턴 재발 시 → R-NNN + `code-conventions.md §6` (CLI 인자 처리)에 `_positive_int` 패턴 표준화

### C-006: `Path.read_text()`/`write_text()` encoding 미명시 — 광역 패턴 → **§2 R-001로 승격 (2026-05-08)**

**승격 완료**: 5회 누적 + 어댑터 한정 아닌 광역 패턴 입증 + Day 2 commit 직전 review-code 3 라운드에서 P0 발견 → 즉시 §2 R-001로 정식 환원. 이후 발견 사례는 R-001 "사례" 항목에 누적.

아래는 승격 전 후보 narrative (history 보존용):

- **계층**: Knowledge (안전성 — 인코딩)
- **도메인**: 안전성 — 파일 I/O 시스템 기본 인코딩 의존
- **발견 경로**: review-code (Day 2 round 1·3)
- **발견 횟수**: **5회 누적** (2026-05-08)
  1. `src/agents/codex.py:67` `raw_log_path.write_text(result.stdout)` — round 1 fix
  2. `src/agents/claude.py:69` `raw_log_path.write_text(result.stdout)` — round 1 fix
  3. **`src/orchestrator.py:116` `ROLE_FILE[role].read_text()` (P0)** — round 3 fix. role.md(한국어 본문) 시스템 기본 인코딩 의존 → 비UTF-8 환경에서 build_prompt 전체 실패
  4. `tests/test_cwd_isolation_integration.py:28` `tmp_claude.write_text("TMP-MARKER: cwd가 ...")` (P1, 한국어) — round 3 fix
  5. `tests/test_cwd_isolation_integration.py:25,36` `repo_sentinel.write_text` + `raw.read_text` (P2, ASCII이지만 컨벤션) — round 3 fix
- **연관 P-id**: **P-ENCODING** (§4.4 등재)
- **fix 패턴 (모든 라운드 적용)**: `Path.write_text(..., encoding="utf-8")` / `Path.read_text(encoding="utf-8")` 명시.
- **승격 판정**: 5회 누적 + **어댑터 한정 패턴 아님 입증** (orchestrator + tests에서도 발생). 즉시 `review-code-checklist.md §1 안전성` P0 행으로 승격 권고:
  > "모든 `Path.read_text()`/`write_text()`/`open()` 호출에 `encoding="utf-8"` 명시. 누락 시 P0."
- **§2 정식 환원 (R-001 후보)**: 본 라운드 5건 누적은 정식 R-NNN 환원 트리거 (직전 §3 C-N 후보들과 달리 "5회 누적 + 광역 패턴" 두 조건 동시 만족).

### C-007: prompt 생성 함수가 try/except 밖 호출 — file I/O 예외 fail-fast 누수 (C-005 인접)

- **계층**: Knowledge (안전성 — orchestrator 실패 모드)
- **도메인**: 안전성 — try 블록 위치 부정확
- **발견 경로**: review-code (Day 2 round 6)
- **발견 횟수**: 1회 (2026-05-08, fix 적용)
- **연관 P-id**: C-005 인접 (다음 발견 시 P-id 부여 결정)
- **패턴**: `build_prompt(...)` 호출이 `try:` 블록 밖 — `ROLE_FILE[role].read_text(encoding="utf-8")`이 `FileNotFoundError` (role.md 부재) / `UnicodeDecodeError` (encoding 부정) / `OSError`(`PermissionError`) raise 시 main 스택까지 전파, `kind=error` JSONL 라인 미기록 + raw traceback 노출.
- **fix 패턴 (이번 라운드 적용)**: `build_prompt`를 `try:` 블록 안으로 이동 + catch 튜플 확장 (C-005 갱신 동시 적용).
- **승격 판정**: 다음 prompt-build 경로(예: `_serialize_history` 외부 file I/O 추가) 또는 새 외부 자원 read 함수에서 같은 패턴 재발 시 → R-NNN + `code-conventions.md` "외부 자원 read는 try 블록 안" 규칙 추가.

### C-008: 가드(SystemExit) 전 자원 할당 → cleanup leak

- **계층**: Knowledge (안전성 — 자원 정리)
- **도메인**: 안전성 — 검사 순서·자원 lifecycle
- **발견 경로**: review-code (Day 2 round 6)
- **발견 횟수**: 1회 (2026-05-08, fix 적용)
- **연관 P-id**: (해당 없음 — 신규 패턴)
- **패턴**: `tempfile.mkdtemp()` 후 ADR-6 검사가 fail이면 `SystemExit` raise → `try/finally` 진입 전이라 임시 dir leak. edge case (`TMPDIR=/repo/sub` 등 사용자 환경)에서 발현.
- **fix 패턴 (이번 라운드 적용)**: ADR-6 검사 진입 시 `cleanup` 변수 사전 결정 + 검사 fail 시 `shutil.rmtree(workdir, ignore_errors=True)` 호출 후 `SystemExit`. (검사 순서를 mkdtemp 앞으로 이동도 대안이지만 `args.workdir` resolve 결과를 검사하는 메커니즘이 mkdtemp 뒤가 자연 — cleanup 명시가 더 단순.)
- **승격 판정**: 다른 자원 할당(예: file lock, network connection, db transaction) 후 가드 fail 시 leak 사례 발견 시 → R-NNN + "가드 전 자원 할당 시 cleanup 명시" 규칙. Python `contextlib.ExitStack` 패턴 권고.

### C-009: fatal error 발견 시 max-turns 반복 차단 (run_session loop break)

- **계층**: Knowledge (인터페이스 — turn loop 종료 조건)
- **도메인**: 인터페이스 — error 라인이 turn loop break trigger
- **발견 경로**: review-code (Day 2 round 7)
- **발견 횟수**: 1회 (2026-05-08, fix 적용)
- **연관 P-id**: (해당 없음 — 신규 패턴)
- **패턴**: `run_turn`이 인증 실패/CLI 미설치/parse 실패 등 error 발생 시 `_error_msg` append + return → `run_session`이 critique 부재로 streak=0 reset 후 다음 turn 진행 → AgentAuthError·FileNotFoundError 같은 fatal도 max-turns까지 반복 (token 소모 ↑). `protocol.md §9` "retry 1회" 명세와 모순.
- **fix 패턴 (이번 라운드 적용)**: run_session loop에 `last_msg.kind == "error" and last_msg.turn_id == turn` 검사 → `_meta_msg(content="auto-end (error: ...)")` append 후 early return. retry 1회는 Day 3+ 사용자 directive 기반 정책 결정 후 deferred.
- **승격 판정**: Day 3 mock 어댑터 또는 plan/implement 모드 추가 시 새 fatal 패턴 (mock recording 부재, spec 입력 부재) 발견 시 → R-NNN + `protocol.md §9` 실패 모드 표 보강.

### C-010: 임시 자원 cleanup default 정책 — 사용자 결과 확인 통로

- **계층**: Knowledge (UX — 자원 lifecycle vs 결과 확인)
- **도메인**: 인터페이스/UX
- **발견 경로**: review-code (Day 2 round 7)
- **발견 횟수**: 1회 (2026-05-08, 정책 변경 적용)
- **연관 P-id**: (해당 없음)
- **패턴**: `--workdir` 미지정 시 mkdtemp + finally rmtree → 사용자가 결과(messages.jsonl·raw streams)를 확인할 통로 부재. CLI는 workdir 출력도 X. 기본 호출 (`dialectic run --task ...`) 시 사용자가 plan narrative(JSONL 4 라인 + parent_id 체인 등)를 검증할 수 없음.
- **fix 패턴 (이번 라운드 적용)**: cleanup default를 False로 변경 + finally에서 `sys.stderr.write`로 workdir + `logs/messages.jsonl` + `raw streams` 경로 안내. mkdtemp 누적은 사용자가 `/tmp/dialectic-*` 주기 정리 (prefix가 `dialectic-`이라 grep 가능).
- **narrative 동기화**: `cwd-isolation.md` Layer 2 + README `--workdir` 옵션 표 narrative 갱신.
- **승격 판정**: Day 3+ 사용자 피드백(디스크 누적 불만 또는 결과 확인 권한 차단)이 발생 시 `--cleanup-workdir` 토글 또는 `~/.local/share/dialectic/runs/<ts>/` 같은 영속 경로로 변경 검토. 그 시점에 R-NNN 환원.

### C-005: orchestrator try/except 튜플 좁음 — fail-fast 누수 광역 패턴

- **계층**: Knowledge (인터페이스 — orchestrator 실패 모드)
- **도메인**: 안전성 — catch 범위 부족
- **발견 경로**: review-code (Day 2 round 2·6)
- **발견 횟수**: **2회 누적** (2026-05-08)
- **연관 P-id**: (해당 없음 — 신규 패턴, 2회 누적이라 P-id 부여 검토)
- **패턴**: `orchestrator.run_turn`의 `try/except` 튜플이 좁아 새 예외 유형 누수 — main 스택 전파 + `kind=error` 미기록.
  1. **R1 사례 (round 2)**: `(subprocess.TimeoutExpired, json.JSONDecodeError, AgentAuthError)`만 → `FileNotFoundError` (CLI 미설치) 누수
  2. **R2 사례 (round 6)**: 위 + `FileNotFoundError`만 → `OSError`(PermissionError), `UnicodeDecodeError`(role.md decode), generic `ValueError`(json.loads non-JSONDecodeError) 누수
- **fix 패턴 (누적)**: catch 튜플을 `(TimeoutExpired, JSONDecodeError, AgentAuthError, FileNotFoundError, OSError, UnicodeDecodeError, ValueError)`로 광역화. 향후 신규 예외 유형 발견 시 추가.
- **승격 판정**: 3번째 누락 예외 발견 시 → R-NNN + `code-conventions.md` 또는 신규 패턴 정책. catch-all `except Exception`은 너무 넓어 부적절 — 명시적 enum 유지.

---

## 4. 운영 메커니즘

### 4.1 결함 발견 시점

- `review-code` 호출 결과 → §3 후보로 잠정 적재
- `review-plan` 호출 결과 → §3 후보
- 사용자 직접 발견 → 사용자 판단으로 §3 또는 §2 직접 적재
- 본 도구 실행 중 자체 결함 (실 호출 vs mock 동작 불일치 등) → §3

### 4.2 후보 → 규칙 승격

- §3 후보가 1회 더 발견되면 §2 규칙으로 승격
- 승격 시 ID(R-NNN) 부여, "승격 대상" 명시 — 어느 체크리스트·SKILL.md에 검사 항목으로 추가됐는가
- `docs/dev-docs/Documentation-Checklist.md` §1.4에 매핑 확인

### 4.3 규칙 진화

- 규칙이 승격된 후 새 사례가 또 발견되면 "사례" 항목에 누적 (빈도 추적)
- 규칙이 부적합하다고 판명되면 (false positive 양산 등) — 규칙 수정 또는 삭제. 삭제 시 사유 기록.

### 4.4 본 도구 specific 환원 패턴

본 도구 특수 영역에서 자주 발생할 수 있는 패턴 (선제 모니터링). 각 패턴에 short-id 부여 — review-code/review-plan 결함 보고 시 P-id 인용:

| P-id | 패턴 | 근거 ADR |
|---|---|---|
| **P-CWD** | cwd 격리 실수 — 어댑터마다 반복 가능성 ↑ | ADR-6 |
| **P-JSONL** | JSONL append-only 위반 — 멀티 어댑터·멀티 모드 동시 쓰기 시 위험 | ADR-1 |
| **P-MOCK** | mock vs 실 호출 비대칭 — `meta.is_mock` 누락, 출력 형식 차이 | ADR-5 |
| **P-MODE** | 모드↔role 매핑 일관성 — `MODE_ROLES` dict와 docs 사이 | ADR-3, ADR-7 |
| **P-LEAK** | 두 층 누수 — A 층 .md가 runtime prompt에 끼어듦 (cwd 격리가 막아주지만 구조 변경 시 재검증) | ADR-6 |
| **P-VENDOR** | 벤더 비대칭 — Codex만 / Claude만 갖는 옵션이 어댑터 인터페이스에 누수 | ADR-2 |
| **P-ENCODING** | `Path.write_text()`/`open()` 등 파일 I/O에 `encoding="utf-8"` 미명시 — 시스템 기본 인코딩 의존 → 비ASCII 출력 시 UnicodeEncodeError. **§2 R-001로 정식 환원** (2026-05-08, 5회 누적 + review-code-checklist §1 P0 승격) | ADR-1 (JSONL 무결성) |
| **P-STDERR_LOSS** | subprocess `result.stderr` 디스크 미보존 — returncode!=0 분기에서 raw_log엔 stdout만 들어가 디버깅 정보 손실 | ADR-1 (재현성) |
| **P-INVARIANT** | frozen dataclass protocol invariant(`ts` ISO8601 Z 형식, enum 값 집합 등)가 `__post_init__` self-가드 X — 직접 인스턴스 생성 경로(어댑터·테스트)에서 fail-late | ADR-1 (스키마 무결성) |
| **P-CLI_GUARD** | argparse `type=int` 단독은 음수/0 의미 오류 미차단 — `--max-turns 0` (빈 루프), `--convergence-streak 0` (즉시 종료) 같은 silent 통과. `_positive_int(min=N)` 헬퍼 패턴 권고 | ADR-4 (메뉴 + CLI 인자) |

위 10가지는 본 도구 운영 초기에 1회씩 발생할 가능성이 있으므로, 발견 시 즉시 R-NNN으로 환원 권고 (1회 발견이라도). 환원된 R-NNN은 "사례" 항목에 P-id 인용 (예: `사례: P-CWD 1차 발생 — phase X에서 ...`).

**P-ENCODING / P-STDERR_LOSS 환원 사례** (Day 2 review-code 1차 발견):
- `src/agents/codex.py:67-72` + `src/agents/claude.py:69-74` — 두 어댑터 동시 발생 → review-code commit 전 fix:
  - `raw_log_path.write_text(result.stdout, encoding="utf-8")` (P-ENCODING 차단)
  - `raw_blob = result.stdout + "\n--- STDERR ---\n" + result.stderr if result.stderr else result.stdout` 패턴으로 stderr 보존 (P-STDERR_LOSS 차단)
- 향후 mock/3rd 어댑터 추가 시 재발 가능성 ↑ — review-code-checklist §1 "안전성" 항목으로 승격 권고.

**P-JSONL 환원 사례** (Day 2 review-code 1차 발견 — `§3 C-001` 후보 적재):
- `src/bus.py:read_all()` — `json.JSONDecodeError` catch 부재 → 손상 라인 1개로 전체 read 실패 위험. orchestrator가 `read_all()[-1].msg_id` 패턴으로 직전 메시지 추출 시 turn 전체 종료 막음.
- `src/schema.py:from_dict()` — `KeyError`/`TypeError` 시 raw 보존 0.
- fix: `try/except` + stderr 경고 + raw 라인/dict keys 보존 + caller에 친절 ValueError. 승격은 다음 발견 시 (§3 C-001 → R-NNN).

**P-INVARIANT 환원 사례** (Day 2 review-code 1차 발견 — `§3 C-002` 후보 적재, P-id 신규 등재):
- `src/schema.py` — `Message.ts: str` 필드만 있고 `__post_init__` 정규식 단언 0. orchestrator `_now_ts()`가 형식 보장하지만 직접 인스턴스 생성 경로 자기 검증 부재.
- fix: 모듈 레벨 `_TS_PATTERN` 정규식 + `Message.__post_init__` 단언 → 위반 시 ValueError.
- P-id 명명 절차 §4.5 1~4 따름 — 사용자 결정 후 본 표 등재 완료 (2026-05-08).

**P-STDERR_LOSS 환원 사례 누적** (Day 2 review-code round 1·7):
- round 1: codex.py + claude.py raw_log_path에 stderr 보존 — fix 적용
- **round 7 (P1)**: 어댑터가 raw_log에는 stderr 보존하지만 messages.jsonl `content` 필드에는 `"ValueError: empty_response"`만 박힘 → `protocol.md §9` 명세("`content=<stderr 발췌>`") 위반. fix: AgentResponse에 `stderr_excerpt: str | None = None` 필드 추가 + 어댑터 비-auth 분기에서 stderr[:N] 채움 + orchestrator 빈 응답 분기에서 ValueError 메시지에 stderr 합성. messages.jsonl 단독으로 사용자 디버깅 가능. 다음 발견 시 R-002 환원 검토.

**P-VENDOR 인접 후보** (Day 2 review-code 1차 발견 — `§3 C-003` 후보 적재):
- `src/agents/base.py:AgentRunner.run()` Protocol docstring 부재 — 어댑터 책임(raw 저장, 빈 응답, AgentAuthError, Meta 14 필드)이 시그니처에 미반영. mock 어댑터(Day 3+) 추가 시 비대칭 누수 통로.
- fix: deferred — Day 3 mock 작성 시 AgentRunner.run() docstring 보강 + 본 사례를 P-VENDOR로 환원 결정.

### 4.5 신규 패턴 P-id 부여

§4.4 6개 외 새 패턴 발견 시:

1. 패턴 의미 단위 명명 (예: 새로운 비대칭 = `P-NEWPATTERN`).
2. 사용자가 P-id 결정 (자동 부여 X — 의미 단위 일관성 위해).
3. validation.md §4.4 표에 신규 행 추가 + 근거 ADR 명시.
4. review-code/review-plan SKILL.md 보고 형식이 본 P-id 인식.

P-id 컨벤션:
- 형식: `P-` + 영문 대문자 단어
- 단어 1개: underscore 없음 (`P-CWD`, `P-JSONL`, `P-MOCK`, `P-MODE`, `P-LEAK`, `P-VENDOR`)
- 단어 2개: UPPER_SNAKE underscore 구분 (`P-ASYNC_RACE`, `P-RETRY_LIMIT`)
- 단어 3개+: 기각 — 의미 단위 짧게. 더 짧은 표현으로 재명명

---

## 5. 4계층과의 관계

| 계층 | Validation에서 환원 시 영향 |
|---|---|
| Context | CLAUDE.md / AGENTS.md의 Pre/Post Checklist에 검사 항목 추가 (예: "subprocess cwd 명시 검토") |
| Knowledge | docs/dev-docs/code-conventions.md에 새 규칙 추가, docs/dev-docs/architecture.md ADR 갱신 (큰 결정 영향 시) |
| Protocol | docs/dev-docs/Checklists/ 안 항목 승격, docs/dev-docs/Documentation-Checklist.md 매핑 추가 |
| Validation | 본 문서 §2 규칙 자체 진화 |

→ Validation은 다른 3 계층을 갱신하는 메타 계층. 결함을 영속적으로 흡수.

---

## 6. 본 문서 자체의 변경

- 새 규칙 추가 시 ID 순차 부여 (R-001, R-002, ...)
- 형식 변경 시 §1 형식 정의 갱신 + 기존 규칙 재포맷
- 본 문서 갱신은 `docs/dev-docs/Documentation-Checklist.md` §1.3에 매핑되어 있음 — sync-docs가 점검

---

> 초기 갱신: 2026-05-06 (스켈레톤). 운영 중 §2·§3 누적.
> Day 2 환원 (2026-05-08):
> - §3 후보 **10건** 적재 (C-001 P-JSONL / C-002 P-INVARIANT / C-003 P-VENDOR / C-004 P-CLI_GUARD / C-005 catch 튜플 광역 누락 / C-006 P-ENCODING / C-007 prompt 생성 try 밖 / C-008 가드 전 자원 할당 leak / **C-009 fatal error turn loop break** / **C-010 cleanup default 정책**)
> - §4.4 P-id 표 8 → **10**개 (P-INVARIANT·P-CLI_GUARD 신규)
> - **§2 R-001 정식 환원** — C-006 (P-ENCODING) 5회 → 8회 누적 + 광역 패턴 입증 → review-code-checklist §1 안전성 P0 행 승격 (자동 catch 활성)
> - C-003 (P-VENDOR)는 deferred — Day 3 mock 어댑터 작업 cross-check 후 R-002 환원 결정 (`outline/05-timeline.md` Day 3 첫 작업 명시)
> - **C-005는 round 2·6에서 2회 누적** — 3번째 누락 예외 발견 시 R-NNN 환원 권고. catch-all 금지, 명시적 enum 유지.
