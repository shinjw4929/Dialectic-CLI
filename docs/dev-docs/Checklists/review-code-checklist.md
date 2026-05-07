# review-code Checklist — Dialectic-CLI

> `review-code` 스킬이 코드 검사 시 사용하는 항목 표. 3 도메인 (안전성·인터페이스·컨벤션)별로 검사 가능 표현. 본 표에 없는 항목은 사각지대.

---

## 도메인 1: 안전성 (Security)

외부 CLI subprocess 호출 + 토큰 + 파일 I/O가 핵심 위험 영역.

| 항목 | 검사 패턴 | 위반 시 |
|---|---|---|
| `shell=True` 사용 | grep `shell=True` in `subprocess.*` 호출 | **P0** |
| `cmd_list` 분리 | subprocess 인자가 list인지, str로 concat인지 | **P0** (str concat 시) |
| subprocess `cwd` 명시 | grep `subprocess.run\(` 호출 후 `cwd=` 인자 검사 | **P0** (누락) |
| subprocess `timeout` 명시 | grep 동일, `timeout=` 인자 검사 | **P1** |
| subprocess `env` 통제 | `env=` 인자가 명시적 dict인지, 환경변수 통째 통과인지 | **P1** |
| 토큰 환경변수 노출 | `print(os.environ)` 또는 log에 키 이름 (`ANTHROPIC_API_KEY` 등) 포함 | **P0** |
| 토큰 값 log 노출 | log에 토큰 값 자체가 포함되는 path 검사 | **P0** |
| 경로 traversal 차단 | 사용자 입력 경로가 `Path.resolve()` 후 `--workdir` 하위 검증되는가 | **P0** |
| mock recording 임의 경로 | 사용자 지정 mock 경로의 검증 여부 | **P1** |
| JSON 파싱 raise 처리 | `json.loads()` 실패 시 raw 보존 + `kind=error` 메시지? | **P1** |
| MAX_BUDGET 검증 | `--max-budget-usd` 또는 동등 안전장치 명시? | **P1** |
| auth 실패 처리 | `AgentAuthError` 별도 클래스로 catch? 사용자에게 친절 안내? | **P1** |

## 도메인 2: 인터페이스 (Interface)

본 도구의 핵심 추상화 — 어댑터 / JSONL bus / 모드↔role 매핑.

| 항목 | 검사 패턴 | 위반 시 |
|---|---|---|
| AgentRunner Protocol 준수 | 모든 어댑터가 동일 시그니처? `name`, `vendor`, `run()` 모두 보유? | **P0** |
| keyword-only 인자 | `def run(self, prompt, *, raw_log_path, ...)`의 `*` 누락? | **P0** |
| AgentResponse 반환 | `run()`이 `AgentResponse` 반환? dict 반환 시 위반 | **P0** |
| AgentResponse frozen | `@dataclass(frozen=True)` 적용? | **P1** |
| JSONL 필수 필드 — msg_id | `uuid.uuid4()` 부여? 누락 가능 path? | **P0** |
| JSONL 필수 필드 — parent_id | task 메시지 제외 모든 메시지에 명시? | **P0** |
| JSONL 필수 필드 — is_mock | mock 어댑터 결과에 `meta.is_mock=true`? 실 호출은 `false`? | **P0** |
| JSONL 필수 필드 — workdir | `meta.workdir`에 resolved cwd 기록? | **P1** |
| JSONL ts ISO-8601 UTC | `datetime.now(timezone.utc).isoformat()` 패턴? | **P1** |
| JSONL append-only | bus 코드가 file open mode `"a"`? truncate 시도? | **P0** |
| JSONL flush | 매 메시지 후 `f.flush()`? | **P1** |
| MODE_ROLES dict 일관 | `src/orchestrator.py` MODE_ROLES와 `docs/runtime-docs/protocol.md` §3, `docs/dev-docs/architecture.md` §4가 일치? | **P0** |
| 모드별 role.md 존재 | MODE_ROLES가 가리키는 모든 role이 `docs/runtime-docs/roles/<role>.md` 파일 존재? | **P0** |
| 어댑터 비대칭 | 한 어댑터(codex/claude/mock)만 다른 옵션·반환·예외? | **P1** |

## 도메인 3: 컨벤션 (Convention)

`docs/dev-docs/code-conventions.md` 기반.

| 항목 | 검사 패턴 | 위반 시 |
|---|---|---|
| 타입 힌트 | 모든 함수 시그니처에 hint? `def foo(x):` 미타입? | **P1** |
| 외부 의존성 추가 | `import` 문에 표준 라이브러리 외? `pyproject.toml` 추가됐나? ADR 있나? | **P0** (ADR 없이 추가 시) |
| `pyproject.toml` 일관 | `import`된 패키지가 `pyproject.toml`에 명시? 누락 또는 잉여? | **P1** |
| 함수 길이 | 100 lines 초과? | **P2** |
| 매직 넘버 | 250, 300, 5549 등 하드코딩 — 상수/인자/환경변수? | **P2** |
| 주석 정책 — WHAT 주석 | "this iterates over list" 같은 자명한 주석? | **P2** |
| 주석 정책 — 이전 작업 참조 | "이건 turn loop에서 호출됨", "wave_difficulty task에서 발견" 같은 주석? | **P2** |
| TODO 표기 | `# TODO(YYYY-MM-DD)` 형식? 날짜 누락? | **P2** |
| README 정합성 | 새 CLI 옵션·서브커맨드가 README에 반영? | **P1** |
| docs/runtime-docs/protocol.md 정합성 | 어댑터·orchestrator 변경이 protocol.md에 반영? (sync-docs 결과와 cross-check) | **P1** |
| Documentation-Checklist 매핑 | 변경 유형이 §1에 매핑되어 있나? 누락이면 매핑 추가? | **P1** |
| 한 commit = 한 의도 | git log 검사 — 커밋이 분류 기준 따르는가 | **P2** |
| commit 메시지 | "WIP", "fix" 같은 모호 메시지? 동사로 시작? | **P2** |

---

## P0/P1/P2 적용 원칙

| Priority | 의미 | 결과 |
|---|---|---|
| **P0** | 보안·정합성·기능 직접 위협. 즉시 수정 필요 | 자동 chaining 시 `commit` 차단. 사용자 fix 후 재검사 |
| **P1** | 결함 원인 가능성. 가능한 한 빨리 수정 | 보고만. commit은 진행 가능 |
| **P2** | 개선 권고. 직접 위협 X | 보고만. 사용자 판단 |

## 사용 방법 (review-code 스킬에서)

1. 검사 대상 파일 식별 (인자 또는 git diff)
2. 도메인 1~3 순회. 각 도메인 × 각 항목별 검사
3. 위반 시 줄 번호 + 코드 발췌 + P 라벨 + 권고 fix
4. 결과를 review-code 보고 형식으로 출력 (스킬 SKILL.md §결과 보고)

## 환원 (validation.md)

같은 항목 위반이 **반복 발견**되면:
- 단순 수정 권고를 넘어 `docs/dev-docs/validation.md`에 규칙으로 환원 권고
- 환원된 규칙은 future plan의 review-plan-checklist 또는 review-code-checklist에 검사 항목으로 승격 가능
- 자동 환원 X — 사용자 판단
- 결함 발견 시 `validation.md` §4.4 P-id 표 조회 → 매치하면 P-id 인용 (예: `P-CWD`). 매치 X면 빈 칸 (신규 패턴 발견 신호 — §4.5 절차 따라 부여 검토).

## 본 표 자체의 변경

- 새 검사 항목 추가 시 도메인(1~3)·P 레벨 명시
- 본 도구의 새 패턴(예: 새 어댑터, 새 모드, 새 보안 위험 영역) 도입 시 자동 검토 권고
- `docs/dev-docs/Documentation-Checklist.md` §1.4 매핑 갱신 (review-code-checklist.md → review-code SKILL.md)
