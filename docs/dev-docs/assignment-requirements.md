# 과제 요구사항 ↔ Dialectic-CLI 매핑

> 본 문서는 과제 요구사항을 본 도구와 1:1로 매핑한 자가 검증 자료.

---

## 1. 과제 목표 (메일 본문 인용)

> AI 코딩 에이전트(Claude Code, Codex, Gemini CLI 등)를 사용하여, 여러 AI 에이전트가 서로 통신하며 사용자와 협업할 수 있는 도구를 만드세요.

**본 도구의 해석**: "AI 코딩 에이전트"는 Codex CLI / Claude Code 등 LLM 기반 코딩 도구. "여러 에이전트가 통신"은 두 에이전트 간 양방향 메시지 교환. "사용자와 협업"은 단순 관찰자가 아닌 synthesis 생성자로 매 턴 개입.

→ 본 도구는 **변증법 구조**(thesis–antithesis–synthesis)로 이를 충족: 한 벤더가 thesis를 제시하면 다른 벤더가 antithesis를 형성하고, 사용자가 synthesis를 만들어 다음 턴에 양쪽 prompt에 주입한다.

---

## 2. 과제 조건 ↔ 본 도구 만족 방식

| # | 메일 본문 조건 | 본 도구 만족 방식 | 검증 자료 |
|---|---|---|---|
| 1 | **두 개 이상의 AI 에이전트가 메시지를 주고받을 수 있어야 합니다** | 포지션 2개(driver/reviewer) × 벤더 2개(Codex CLI / Claude Code). run/plan/implement 모드 동일 매핑(`MODE_ROLES` SSOT). 통신 = `<workdir>/<session_ts>/messages.jsonl` append-only JSONL bus + 매 턴 풀 트랜스크립트(`HISTORY` 섹션) 양쪽 prompt 주입 → **양방향** (직접 IPC 0, ADR-1) | session 폴더의 `messages.jsonl` 한 번 보면 자명. `docs/runtime-docs/protocol.md` §1.1 통신 모델 + §4 턴 라이프사이클 |
| 2 | **사용자가 이 협업 과정에 개입하거나 관찰할 수 있어야 합니다** | (개입) `--interactive` 3 모드 — `end-only` (자동 dialectic + 종료 직전 결정) / `critical` (Ctrl+F 비동기 트리거 + CONVERGED·max-turns 도달 시 prompt) / `full` (매 턴 끝 6지선다 a/r/m/i/e/s) + directive 자유 텍스트 → 단순 승인 아닌 synthesis 생성. (관찰) 실시간 stdout + `dialectic logs --follow` 내장 명령(plan 010) + 사후 `messages.jsonl` | `kind=decision` 메시지 + `docs/dev-docs/architecture.md` §5 통신 모델 |
| 3 | **통신 방식, 프로토콜, UI, 언어·프레임워크는 자유** | Python 3.10+ · subprocess(`codex exec`/`claude --print --output-format=stream-json`) · JSONL append-only bus · stdin/stdout TUI (Rich/Textual 미사용 — **외부 의존성 0** 정책) | `docs/runtime-docs/protocol.md` + `pyproject.toml` `dependencies = []` |
| 4 | **AI 코딩 에이전트를 사용하여 개발해야 합니다** | 본 repo 자체를 Claude Code + Codex CLI 페어 프로그래밍으로 작성. dev-time .md 하네스 4계층(Context/Knowledge/Protocol/Validation) 자체가 본 도구의 운영 자산 — `CLAUDE.md` / `AGENTS.md` / `docs/dev-docs/Documentation-Checklist.md` / `docs/dev-docs/validation.md` / `.claude/skills/*` (create-plan/review-plan/execute-plan/sync-docs/review-code/commit) | `git log --oneline` (plan 단위 commit), `plan/completed/` (산출 history), `.claude/skills/`, `outline/` (의사결정 보드 Q1~Q22) |
| 5 | **README대로 실행했을 때 동작해야 합니다** | `setup.sh` 한 스크립트(WSL2/Ubuntu 기준 quickstart)로 venv·repo wrapper·`~/.local/bin/dialectic` symlink 일괄 구성. **vendor CLI 인증은 사용자 책임** (mock fallback 영구 deferred — 실 codex/claude 호출만). plan→implement chaining(plan 013/014)으로 빈 workdir 신규 파일 생성까지 시연 가능 | `README.md` quickstart + `dialectic run --task ...` (run 모드) / `dialectic run --mode plan --task ...` → `dialectic implement --spec <path>` (plan→implement chaining, plan 014) / `tasks/implement-dijkstra/task.md` 본 시나리오 |

---

## 3. 제출물 ↔ 본 repo 위치 매핑

| 메일 본문 항목 | 본 repo 산출물 |
|---|---|
| **작동하는 코드 (GitHub repo 또는 .zip)** | https://github.com/shinjw4929/Dialectic-CLI 공개. `main` 브랜치 working state. README quickstart로 빈 WSL2 머신에서 end-to-end 재현 가능 |
| **개발 과정에서 에이전트에 활용한 .md 파일** | (a) **하네스 4계층 .md** — Context(`CLAUDE.md`/`AGENTS.md`) / Knowledge(`docs/dev-docs/{architecture,code-conventions}.md`, `docs/runtime-docs/{protocol,roles/*}.md`, `docs/dev-docs/systems/*`, `docs/runtime-docs/systems/*`) / Protocol(`docs/dev-docs/Documentation-Checklist.md` + `.claude/skills/*`) / Validation(`docs/dev-docs/validation.md` 결함 → 규칙 환원 R-001~R-003) (b) **운영 흔적** — `outline/` (Q1~Q22 의사결정 보드), `plan/completed/` (15 plan 산출 + execution-log), `git log --oneline` (plan 단위 의미 commit) |
| **에이전트 세션 로그(JSONL) 또는 화면 녹화** | `<workdir>/<session_ts>/messages.jsonl` (정제 메시지 버스, `dialectic logs --follow`로 실시간 관찰) + `<workdir>/<session_ts>/sessions/*.jsonl` (raw stream — codex/claude stdout 그대로). default workdir = `~/.local/share/dialectic/runs/<ts-id>/` (XDG, plan 010). 시연 산출 예시는 README에 1턴 demo + 본 repo dijkstra 시연 결과 |

---

## 4. 유의사항 (메일 본문 인용 + 대응)

| 메일 본문 | 본 도구 대응 |
|---|---|
| 사용 도구 제한 없음 (Claude Code, Cursor, Codex 등 자유) | Claude Code + Codex CLI 페어 프로그래밍 채택 (cross-vendor narrative의 핵심) |
| 기한 내 1회만 응시 가능, 제출 후 수정 어려움 | 마감(2026-05-09 23:59 KST) 전 코드 동결 + push 완료. 사후 수정 0 |

---

## 5. 마감

**2026-05-09 (토) 23:59** (한국 표준시).

---

## 6. 빠른 자가 검증 (1분 동선)

1. **메일 본문**과 §2 표를 1:1로 비교 → 누락 0 확인
2. `dialectic run --task "$(cat tasks/implement-dijkstra/task.md)" --driver claude --reviewer codex --max-turns 1` → 1턴 driver↔reviewer 시연 (또는 `dialectic run --mode plan --task ...` → `dialectic implement --spec <plan 산출 spec.md>` chaining)
3. `WD=$(ls -td ~/.local/share/dialectic/runs/*/ | head -1) && head -5 "$WD"messages.jsonl` → driver/reviewer/user 3 발화자가 한 task에 대해 JSONL 메시지 교환
4. `docs/dev-docs/architecture.md` ADR 10개 표 → 핵심 결정 5분 안에 훑기

이 4단계가 모두 막힘 없이 진행되면 본 도구는 과제 명시 조건을 모두 충족.

---

> 권장 동선의 2단계 (README → 본 문서 → architecture.md → harness → code).
