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
| 1 | **두 개 이상의 AI 에이전트가 메시지를 주고받을 수 있어야 합니다** | 포지션 2개(driver/reviewer) × 벤더 2개(Codex CLI / Claude Code). 4개 모드에서 동일. compare 모드는 N×2 병렬. 통신 = `logs/messages.jsonl` append-only bus + 매 턴 풀 트랜스크립트(`HISTORY` 섹션) 양쪽 prompt 주입 → **양방향** | `logs/messages.jsonl` 한 번 보면 자명. `docs/runtime-docs/protocol.md` §1.3 turn lifecycle |
| 2 | **사용자가 이 협업 과정에 개입하거나 관찰할 수 있어야 합니다** | (개입) 매 턴 종료 6지선다(a/r/m/i/e/s) + directive 자유 텍스트 — 단순 승인 아닌 synthesis 생성. (관찰) 실시간 화면 + `dialectic logs --follow` 내장 명령 + 사후 `messages.jsonl` + `SYNTHESIS.md` | `kind=decision` 메시지 + `docs/dev-docs/architecture.md` §통신 모델 |
| 3 | **통신 방식, 프로토콜, UI, 언어·프레임워크는 자유** | Python 3.10+ · subprocess + headless mode · JSONL · stdin/stdout TUI (Rich/Textual 미사용 — 의존성 0 우선) | `docs/runtime-docs/protocol.md` |
| 4 | **AI 코딩 에이전트를 사용하여 개발해야 합니다** | 본 repo 자체를 Claude Code + Codex CLI 페어 프로그래밍으로 작성. dev-time .md(`CLAUDE.md` / `AGENTS.md` / `docs/dev-docs/Documentation-Checklist.md` / `.claude/skills/*`) 보존 | `prompts/`, `git log` (의미 단위 commit), `.claude/skills/` |
| 5 | **README대로 실행했을 때 동작해야 합니다** | `setup.sh` 한 스크립트 + mock 모드 자동 fallback (인증 부재 시) → 임의 환경에서 막힘 0 | `README.md` 첫 단락, `dialectic run --mock tasks/wave_difficulty` |

---

## 3. 제출물 ↔ 본 repo 위치 매핑

| 메일 본문 항목 | 본 repo 산출물 |
|---|---|
| **작동하는 코드 (GitHub repo 또는 .zip)** | https://github.com/shinjw4929/Dialectic-CLI 공개. main 브랜치가 작동 상태 보장 |
| **개발 과정에서 에이전트에 활용한 .md 파일** | (a) 하네스 `.md` (`CLAUDE.md`, `AGENTS.md`, `docs/*`, `.claude/skills/*`) — 도구가 다른 에이전트에 주는 .md (b) 개발 프롬프트 `prompts/` — Claude Code/Codex로 본 도구를 만들 때 사용자가 입력한 메시지 모음 (c) 사고 흔적 `outline/` + git log |
| **에이전트 세션 로그(JSONL) 또는 화면 녹화** | **둘 다 제출**: `logs/messages.jsonl` (정제된 메시지 버스) + `logs/sessions/*.jsonl` (raw stream) + `tasks/*/recordings/*.jsonl` (mock 재생용 사전 녹음) + 5분 데모 영상 (asciinema `.cast` 또는 mp4) |

---

## 4. 유의사항 (메일 본문 인용 + 대응)

| 메일 본문 | 본 도구 대응 |
|---|---|
| 사용 도구 제한 없음 (Claude Code, Cursor, Codex 등 자유) | Claude Code + Codex CLI 페어 프로그래밍 채택 (cross-vendor narrative의 핵심) |
| 기한 내 1회만 응시 가능, 제출 후 수정 어려움 | Day 4 (5/9) 19:00을 절대 마감으로 설정, 4시간 버퍼 확보 |
| 일정 조정 필요 시 출제측 문의 | 현재 일정대로 진행 가능 |

---

## 5. 마감

**2026-05-09 (토) 23:59** (한국 표준시).

본 repo 작성 시점: 2026-05-06 22:00 → **D-3** (3일 + 마감일 1일 버퍼).

---

## 6. 빠른 자가 검증 (1분 동선)

1. **메일 본문**과 §2 표를 1:1로 비교 → 누락 0 확인
2. `dialectic run --mock tasks/wave_difficulty` 실행 → 5초 안에 화면 흐름 시작
3. `cat logs/messages.jsonl | head -20` → driver/reviewer/user 3 발화자가 한 task에 대해 메시지 교환
4. `docs/dev-docs/architecture.md` ADR 8개 표 → 핵심 결정 5분 안에 훑기

이 4단계가 모두 막힘 없이 진행되면 본 도구는 과제 명시 조건을 모두 충족.

---

> 권장 동선의 2단계 (README → 본 문서 → architecture.md → harness → code).
