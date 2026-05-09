# Code Conventions — Dialectic-CLI

> 본 도구의 Python 코드 작성 시 따라야 할 규칙. 일반 PEP가 아닌 **본 도구 specific** 규칙 위주. `review-code` 스킬의 "인터페이스" 도메인의 검사 기준.

---

## 1. Python 표준

- **버전**: Python 3.10+ (PEP 604 union types `int | None`, `dataclass(slots=True)`, `match`).
- **타입 힌트**: 모든 함수 시그니처에 필수. 함수 본문 안의 변수 힌트는 가독성 위해 필요할 때만.
- **dataclass 우선**: 단순 데이터 컨테이너는 `@dataclass(frozen=True)` 또는 `(slots=True)`. plain dict 대신.
- **Protocol**: 추상 인터페이스는 `typing.Protocol` 사용 (ABC 상속 X). `AgentRunner` 가 대표 사례.
- **포맷**: 4-space indent, max line 100자, double quote 우선.

---

## 2. 외부 의존성 0 원칙

본 도구는 **표준 라이브러리만** 사용한다 (`subprocess`, `json`, `pathlib`, `argparse`, `dataclasses`, `typing`, `concurrent.futures`, `tempfile`, `uuid`, `datetime`, `signal`, `termios`, `tty`, `select`, `threading`).

**금지**:
- `rich` / `textual` / `click` / `pydantic` / `httpx` 등 외부 패키지
- 단, **개발 의존성**(`pytest` 등)은 `pyproject.toml`의 `[project.optional-dependencies] dev`에 한함

**이유**: 본 도구를 실행하는 환경의 의존성 부담 최소화. `pip install -e .` 한 번이면 끝나야 한다.

**예외 절차**: 외부 의존을 추가하려면 `docs/dev-docs/architecture.md` ADR에 결정 추가 + 본 문서에 사유 기록.

---

## 3. Subprocess 호출 규칙

`src/agents/*.py`의 어댑터는 모두 다음을 지킨다:

```python
result = subprocess.run(
    cmd_list,                       # 절대 shell=True 쓰지 않음 (injection 위험)
    input=prompt,                   # stdin으로 전달
    capture_output=True,
    text=True,
    timeout=300,                    # 명시 필수 (default 무한대로 두지 않음)
    cwd=resolved_workdir,           # 명시 필수 (cwd 격리, ADR-6)
    env={                           # 외부 환경변수 누수 차단
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(Path.home()),
        # 필요한 인증 변수만 명시적으로 통과
        **({k: os.environ[k] for k in AUTH_VARS if k in os.environ}),
    },
    check=False,                    # 실패는 우리가 처리, raise로 두지 않음
)
```

**위반 사례 (review-code "안전성" 도메인 P0 결함)**:
- `shell=True` — command injection 위험
- `cwd` 미명시 — 본 repo cwd에서 호출되어 개발용 .md 누수
- `timeout` 미명시 — 행 잠재
- `env` 통째 통과 — 사용자 환경 노출 가능

---

## 4. JSONL 메시지 스키마 규칙

`logs/messages.jsonl` 작성 시:

- **append-only**: 기존 라인 절대 수정 금지. 정정이 필요하면 새 메시지를 `kind=meta` 또는 `kind=error`로 추가.
- **flush 강제**: 매 메시지 작성 후 `f.flush()` 호출. 프로세스가 죽어도 부분 기록 보존.
- **fsync 선택**: 재현·검증용 디스크 보존이 critical한 경우 `os.fsync(f.fileno())` 추가.
- **`msg_id` UUID 필수**: `uuid.uuid4()`로 매 메시지 고유 ID 부여.
- **`parent_id` 필수 (task 메시지 제외)**: 어떤 메시지에 응답한 것인지 명시. DAG 추적의 근간.
- **`meta.is_mock` 필수**: 실 호출이면 `false`, mock 재생이면 `true`. 정직성.
- **`meta.workdir` 필수**: resolved cwd 기록 (재현성 검증).
- **`ts`는 UTC ISO-8601**: `datetime.now(timezone.utc).isoformat()`. 로컬 타임존 X.

**위반 사례 (review-code "인터페이스" 도메인 P0 결함)**:
- 기존 라인 수정 (특히 turn N의 메시지를 turn N+1에서 덮어쓰기 시도)
- `msg_id` 누락
- `meta.is_mock` 미기록 → mock/실 호출 구분 불가

---

## 5. 어댑터 인터페이스 (AgentRunner)

`src/agents/base.py`:

```python
from typing import Protocol
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class AgentResponse:
    text: str
    raw_path: Path
    meta: Meta     # frozen dataclass — schema.Meta 재사용 (14 필드, protocol.md §2)
    stderr_excerpt: str | None = None  # 비정상 종료 시 stderr 발췌 (P-STDERR_LOSS).
                                       # orchestrator 빈 응답 분기에서 _error_msg content에 합성 (protocol.md §9)

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

**규칙**:
- 모든 어댑터(`codex.py`, `claude.py`, `mock.py`)가 동일 시그니처 준수.
- `run()`은 keyword-only 인자(`*`) 사용 — 인자 순서 의존 차단.
- `AgentResponse`는 frozen — 호출 후 변경 불가.
- 어댑터는 자기 raw stream을 `raw_log_path`에 직접 저장 (orchestrator가 후처리 안 함).
- 인증 실패는 `AgentAuthError` (별도 정의), 일반 실패(빈 응답·비정상 종료)는 `AgentResponse.text=""`로 반환하고 raw stream에 stderr 보존. orchestrator가 `if not resp.text` 분기에서 `_error_msg`로 환원 (`Meta` frozen dataclass에 `error` 필드 부재 — 인덱싱 자체 불가능).

**위반 사례**:
- `claude.py`만 keyword-only 안 쓰고 positional 인자 받음 → 어댑터 비대칭
- mock에서 `is_mock=true` 안 박음 → 정직성 위반
- `AgentResponse.meta`를 `dict`로 두고 vendor별 임의 키 추가 → 타입 안전성·정직성 손상 (Meta 14 필드 schema 일관 강제)

---

## 6. CLI 인자 처리

`src/cli.py` (또는 `src/main.py`):

- **메뉴 fallback**: 인자 없이 실행 시 단계별 메뉴 (환경 점검 → 모드 → task → 매핑 → workdir).
- **인자 우선**: 인자로 명시된 포지션은 메뉴 스킵. 빈 포지션만 메뉴로 묻기.
- **`--non-interactive` 플래그**: 빈 포지션이 있어도 default 적용 또는 fail. compare 모드는 항상 비대화형.
- **subcommand**: `argparse.add_subparsers()` — `dialectic run` / `plan` / `implement` / `compare` / `logs` (관찰).
- **`--task @<path>`**: `@` 접두사면 파일 내용 로드, 그렇지 않으면 raw 텍스트.
- **`--workdir`** 미지정 시 `tempfile.mkdtemp(prefix="dialectic-")` fallback (ADR-6).

---

## 7. 출력 (사용자 인터페이스)

- **`rich`/`textual` 금지** (외부 의존). ANSI escape 직접 사용.
- **공통 출력 함수**: `src/ui.py`의 `panel(title, body, color=None)` 등으로 일관성.
- **mock 표시**: 어댑터 출력 헤더에 `· MOCK` 라벨 (정직성).
- **진행 표시**: 어댑터 호출 중 spinner. `\r` + 짧은 단위로 갱신, 완료 시 줄바꿈.

### TriggerListener 패턴 (`src/ui.py:TriggerListener`, plan 009 산출)

- **POSIX 한정**: `termios.tcsetattr` + `tty.setcbreak` + `select.select` 사용. Windows native cmd는 `termios` import 부재 → no-op fallback (`__enter__` 즉시 return self, `is_set()` 항상 False)
- **isatty 가드**: `sys.stdin.isatty()` False 시 raw mode 진입 skip (Spinner `:122` 동일 패턴) — pytest capture·pipe 환경 안전
- **cleanup-restart**: 매 턴 시작 시 `with TriggerListener() as trigger`로 새로 진입, 턴 끝 `__exit__` (try/finally `tcsetattr` 복원). subprocess `claude/codex` 호출 동안 stdin 충돌 차단 — `run_turn` 내부 `stdin_canonical_off` 컨텍스트와 가동 시점 분리 (R5)
- **threading.Event**: 리스너 thread가 Ctrl+F (chr(0x06)) 감지 시 set. `is_set()`로 main thread 비동기 polling (턴 끝)
- **SIGINT hand-off**: `_setup_sigint_handler(listener)` 등록 — abort 시 `listener.__exit__`로 raw mode 복원 후 `sys.exit(130)` (POSIX SIGINT 표준 종료 코드, R3)

---

## 8. 보안

- **subprocess injection 차단**: `shell=True` 절대 X. `cmd_list`로 분리.
- **토큰 노출 금지**: 환경변수 dump 금지. 로그에 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` 등 키 이름조차 출력 X.
- **파일 I/O 경로 검증**: 사용자 입력 경로는 `Path.resolve()` 후 `--workdir` 하위 검증 (path traversal 차단).
- **mock 녹음 검증**: 재생 전 JSONL 라인이 `msg_id`/`from`/`kind` 등 필수 필드 보유 확인. 임의 JSONL 재생 X.

---

## 9. 테스트 (pytest)

`tests/` 디렉터리:

- **단위 테스트**: 각 어댑터·bus·schema 모듈마다 `tests/test_<module>.py`.
- **cwd 격리 테스트**: `tests/test_cwd_isolation.py` — Dialectic-CLI cwd에 더미 `CLAUDE.md` 둔 채 어댑터 호출 → raw stream에 더미 내용 0 검증.
- **JSONL append-only 테스트**: `tests/test_bus_append.py` — 동일 라인 두 번 쓰면 두 라인이 됨, 기존 라인 수정 시도 시 검증 실패.
- **mock 동치성 테스트**: `tests/test_mock_equivalence.py` — 같은 prompt에 실 호출 결과 vs mock 재생 결과 구조 일치 (text·meta 필드 동일 종류).
- **외부 호출 없는 테스트**: 단위 테스트는 mock 어댑터 사용. 실 API 호출 테스트는 `pytest -m integration` 별도.

---

## 10. 주석 정책

- **WHY를 적는다**: 왜 이렇게 작성했는지가 비자명한 경우만.
- **WHAT을 적지 않는다**: 코드를 읽으면 자명한 내용은 적지 않음.
- **이전 작업 참조 금지**: "이건 turn loop에서 호출됨", "wave_difficulty task에서 발견된 버그 수정" 등 PR 설명에 들어갈 내용은 코드 주석 아닌 commit message에.
- **TODO 표기**: `# TODO(YYYY-MM-DD): ...` — 날짜 + 의도. 마감 후 미해결 TODO는 issue로 승격 또는 삭제.

---

## 11. Commit 메시지

`.claude/skills/commit/SKILL.md` 참조. 핵심:

- 의미 단위로 commit. "WIP" / "fix" 같은 모호한 메시지 금지.
- 1줄 제목(50자) + 빈 줄 + 본문(72자 wrap).
- 동사로 시작: "Add ...", "Refactor ...", "Document ..." 등.
- 한 commit = 한 의도. 어댑터 변경과 README 갱신을 한 commit에 묶지 않기.

**예시**:
- ✓ `Add codex adapter with cwd isolation`
- ✓ `Refactor JSONL bus to enforce append-only via fcntl lock`
- ✗ `WIP`
- ✗ `fix bug`
- ✗ `update`

---

## 12. 변경 시 동기화

본 문서 갱신 시 함께 갱신할 대상은 `docs/dev-docs/Documentation-Checklist.md` 표 참조. 일반 원칙:

- 새 어댑터 옵션 (subprocess 호출 변화) 추가 → §3 갱신 + `docs/runtime-docs/protocol.md` §10 갱신
- 새 메시지 스키마 필드 → §4 갱신 + `docs/runtime-docs/protocol.md` §2 갱신 + `src/schema.py`
- 새 외부 의존성 추가 (예외 시) → §2 갱신 + `docs/dev-docs/architecture.md` ADR 추가
