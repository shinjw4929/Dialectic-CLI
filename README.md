# Dialectic-CLI

> Cross-vendor multi-agent collaboration through dialectic (thesis ↔ antithesis ↔ synthesis).

> **Status (2026-05-07)**: Day 2 — `run` 모드 한 턴 E2E 동작. driver(codex) → reviewer(claude) 한 턴 + JSONL bus + cwd 격리(ADR-6) + `[CONVERGED]` streak 자동 종료(ADR-9). `plan`/`implement`/`compare` 모드 + 사용자 인터랙티브 UI는 Day 3+.

기획자가 task 한 줄을 던지면, **다른 벤더의 두 AI 코딩 에이전트**가 변증법 루프로 협업하고, 사용자가 매 턴 synthesis를 수행하는 도구.

- **Driver 포지션**: 한 벤더 (e.g., Codex CLI) — 구현·계획 *생성*
- **Reviewer 포지션**: 다른 벤더 (e.g., Claude Code) — 충실도 검토 + 일반 결함 *비판*
- **사용자 (synthesis)**: 매 턴 결정 + 자유 directive → 다음 턴 양쪽 prompt에 주입

같은 모델 self-play의 self-preference bias를 깨려면 **다른 벤더**여야 한다는 thesis 위에 설계된 도구.

---

## 지원 플랫폼

- **Linux / WSL2** — 1차 검증 환경. ADR-10 `validate_patch_path` (`Path.resolve()` symlink 해소)는 Linux/WSL 기준 검증.
- **macOS** — 동일 POSIX 동작 가정 (별도 정식 검증 0).
- **Windows native** — deferred. `Path.resolve()` symlink 처리 OS 차이 + drive letter 정규화 별도 검증 필요. 별도 plan(`006-windows-native-support`) backlog.

---

## TODO (코드 미구현, 일정은 `outline/05-timeline.md`)

| 영역 | 산출물 | Day |
|---|---|---|
| `pyproject.toml` + `dialectic` entry point | `pip install -e .` 가능 상태 | Day 2 |
| 메시지 스키마·JSONL bus | `src/schema.py`, `src/bus.py` | Day 2 |
| 어댑터 (Codex / Claude) | `src/agents/{base,codex,claude}.py` + cwd 격리 | Day 2 |
| Orchestrator 한 턴 E2E (run 모드) | `src/orchestrator.py` | Day 2 |
| 사용자 개입 UI (6지선다 + directive) | `src/ui.py` | Day 3 |
| CLI 메뉴 fallback + 4 서브커맨드 | `src/cli.py` (run/plan/implement/compare/logs) | Day 3 |
| `plan` / `implement` 모드 (role 매핑) | orchestrator MODE_ROLES | Day 3 |
| Mock 어댑터 + `--record` | `src/agents/mock.py` | Day 3-4 |
| `compare --parallel` | ThreadPoolExecutor batch | Day 4 |
| `dialectic logs` 서브커맨드 | 내장 흐름 관찰 | Day 4 |
| 데모 task 풀 실행 + mock 자산 녹음 | `tasks/wave_difficulty/recordings/` | Day 4 |
| 데모 영상 (asciinema/mp4) | 5분 | Day 4 |
| `setup.sh` 깨끗한 환경 검증 | 실패 0 보장 | Day 4 |

---

## 더 읽기 (Day 1에 작성된 .md 하네스)

런타임 사양 (B 층):
- **`docs/runtime-docs/protocol.md`** — 메시지 스키마, 턴 라이프사이클, 모드↔role 매핑, 실패 모드
- **`docs/runtime-docs/roles/*.md`** — 4 role 정의 (implementer / spec-reviewer / planner / plan-reviewer)

개발 사양 (A 층):
- **`docs/dev-docs/architecture.md`** — 왜 dialectic, 왜 cross-vendor, 4계층 매핑, ADR 8개
- **`docs/dev-docs/assignment-requirements.md`** — 과제 본문 ↔ 본 도구 매핑
- **`docs/dev-docs/code-conventions.md`** — Python·도구 specific 규칙
- **`docs/dev-docs/Documentation-Checklist.md`** — 변경 → .md 동기화 매핑
- **`docs/dev-docs/codex-compat.md`** — Codex의 `.claude/skills/*` 호환 정책 정본
- **`docs/dev-docs/validation.md`** — 결함 → 규칙 환원 (운영 중 채워짐)

개발 흔적:
- `outline/` — 결정 흐름 (Q1~Q17)
- `prompts/` — 개발 시 에이전트에 사용한 .md (Day 2부터 누적)
- `git log` — 의미 단위 commit으로 사고 진화 추적

---

## 환경 설정

- Python 3.10+
- 외부 의존성 0 (표준 라이브러리만, dev: pytest)
- `claude` CLI v2.1+ (Anthropic) + `codex` CLI v0.128+ (OpenAI)

```bash
pip install -e .
dialectic doctor           # claude/codex --version + auth status (비용 0)
```

`dialectic doctor`가 인증 누락을 보고하면:
- claude: `claude auth` (Max 구독 OAuth 또는 `ANTHROPIC_API_KEY` 환경변수)
- codex: `codex login` (또는 `OPENAI_API_KEY` 환경변수)

`--workdir` 안내 — 미지정 시 `tempfile.mkdtemp(prefix="dialectic-")`로 임시 dir 자동 생성. **Dialectic-CLI repo 루트는 ADR-6에 의해 사용 불가** (개발용 .md가 런타임 prompt에 누수되므로 SystemExit).

---

## 5초 데모

```bash
source .venv/bin/activate
dialectic doctor                                           # 환경 점검
dialectic run --task "Reply with single digit: 1+1=?" \
    --workdir /tmp/dialectic-demo \
    --driver codex --reviewer claude --max-turns 1
cat /tmp/dialectic-demo/logs/messages.jsonl                # 4 라인+ (task + proposal + critique + meta)
```

## `dialectic run` CLI 옵션 (Day 2)

| 옵션 | default | 설명 |
|---|---|---|
| `--task <text>` | (필수) | 사용자 task 한 줄 (driver/reviewer prompt §2 TASK 주입) |
| `--workdir <path>` | `tempfile.mkdtemp(prefix='dialectic-')` | 작업 디렉토리. **Day 2: 미지정 시에도 cleanup X — 결과 확인 통로**. 종료 시 stderr에 workdir + `logs/messages.jsonl` 경로 안내. `/tmp/dialectic-*` 누적은 사용자가 주기 정리. **Dialectic-CLI repo 루트·하위 사용 불가** (ADR-6, SystemExit) |
| `--driver {codex,claude}` | `codex` | thesis 발화 위치 |
| `--reviewer {codex,claude}` | `claude` | antithesis 발화 위치 |
| `--max-turns N` | `1` | 최대 turn 수. 도달 시 `auto-end (max-turns reached)`. 양수만 (`_positive_int` 가드) |
| `--mode {run}` | `run` | Day 2는 `run`만. plan/implement/compare는 Day 3+ |
| `--convergence-streak K` | `2` | reviewer `[CONVERGED]` 누적 K턴 도달 시 `auto_end_converged` (outline/02 §2.9). ADR-9: `--max-turns < K+1` 시 K=1 fallback + stderr 경고. 양수만 |
| `--interactive {end-only}` | `end-only` | Day 2는 `end-only`만 (인터랙티브 미구현 — max-turns/streak까지 자동). Day 3+에서 full/critical 추가 |

`dialectic doctor`는 인자 없음 — claude/codex `--version` + `auth/login status` + `claude doctor` 비용 0 점검.

## 현재 동작 모드

- **Day 2**: `run` 모드만 정식 검증 (driver+reviewer 한 턴 E2E + `[CONVERGED]` 자동 종료). `plan`/`implement`/`compare`는 **CLI `--mode` choices에 미노출** — `MODE_ROLES`/`ROLE_FILE` dict에만 키 선반영(Day 3+ 호환). 사용자가 `--mode plan` 호출 시 argparse error로 차단. Day 3+에서 인터랙티브 UI + spec 입력 메커니즘(`--spec @<path>`) + `--mode` choices 확장.
- **Day 3+**: 사용자 6지선다 UI, mock 어댑터, `compare --parallel`, `dialectic logs`.

---

## 개발 / 기여

`CLAUDE.md` (Claude Code) 또는 `AGENTS.md` (Codex CLI)가 개발용 진입점. 본 repo 자체가 Claude Code + Codex CLI 페어 프로그래밍으로 작성됨.

Codex에서 포팅된 `.claude/skills/*` workflow를 `$sync-docs`처럼 명시적으로 호출하려면:

```bash
./dialectic-skill sync-docs

# 또는 pip install -e . 이후:
dialectic-skill
dialectic-skill sync-docs
dialectic-skill review-plan plan/001-run-mode-core
dialectic-skill --show review-code
```

`dialectic-skill <workflow>`는 `docs/dev-docs/codex-compat.md`의 정책을 따르는 `$<workflow>` 명시 호출 문구를 출력한다. 출력된 문구를 Codex 대화에 넣으면 canonical `.claude/skills/<workflow>/SKILL.md` 절차가 Codex 방식으로 적용된다.

---

## 라이선스

MIT (예정)
