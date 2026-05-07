# Documentation Checklist — Dialectic-CLI

> 코드/.md 변경 시 함께 갱신해야 할 파일 매핑. **Pre/Post-Implementation Checklist**의 핵심. 매 변경마다 본 표를 조회하면 누락 가능성을 구조적으로 제거.

`sync-docs` 스킬은 이 표를 기준으로 동작한다.

---

## 0. docs/ 폴더 구조 (진리문서 SSOT 위치)

```
docs/
├── dev-docs/                   # A 층 (개발용)
│   ├── architecture.md         # 인덱스 — 왜 dialectic + ADR + 4계층
│   ├── code-conventions.md     # Python 규칙 횡단
│   ├── validation.md           # 결함 → 규칙 환원 (P-id 표 §4.4)
│   ├── assignment-requirements.md
│   ├── codex-compat.md
│   ├── Documentation-Checklist.md  # (본 파일)
│   ├── Plans/                  # plan-writing-guide.md
│   ├── Checklists/             # review-{plan,code}-checklist.md
│   └── systems/                # 모듈별 진리문서 SSOT (NEW)
│       ├── INDEX.md            # 모듈 표 + 의존 그래프
│       ├── orchestrator.md     # turn loop + [CONVERGED] + ADR-9 + cli
│       ├── agents.md           # AgentRunner Protocol + 어댑터
│       ├── jsonl-bus.md        # Bus + Message/Meta schema
│       ├── cwd-isolation.md    # ADR-6 메커니즘 (횡단)
│       └── env-check.md        # dialectic doctor
└── runtime-docs/               # B 층 (런타임)
    ├── protocol.md             # 메시지 스키마 + 라이프사이클 (횡단)
    ├── roles/                  # 4 ROLE 본문
    │   ├── implementer.md
    │   ├── spec-reviewer.md
    │   ├── planner.md
    │   └── plan-reviewer.md
    └── systems/                # 모드별 진리문서 SSOT (NEW)
        ├── INDEX.md            # 4 모드 매트릭스
        └── run-mode.md         # Day 2 산출물 SSOT
```

**3 layer**:
1. **인덱스** (`architecture.md` / `protocol.md`): 횡단 결정·사양
2. **systems/** (NEW): 모듈/모드 단위 SSOT — 변경 시 반드시 갱신
3. **본 Documentation-Checklist**: 변경 → systems/ 매핑

---

## 1. 변경 유형 → 갱신 대상 매핑

### 1.1 코드 변경 (src/)

| 변경 부위 | 갱신 대상 |
|---|---|
| `src/agents/base.py` (AgentRunner Protocol·AgentResponse) | `docs/runtime-docs/protocol.md` §8, `docs/dev-docs/code-conventions.md` §5, **`docs/dev-docs/systems/agents.md`**, 모든 어댑터 (codex/claude/mock) 시그니처 검증 |
| `src/agents/codex.py` (Codex 호출 옵션·인자) | `docs/runtime-docs/protocol.md` §10, `docs/dev-docs/code-conventions.md` §3, **`docs/dev-docs/systems/agents.md`** |
| `src/agents/claude.py` (Claude 호출 옵션·인자) | `docs/runtime-docs/protocol.md` §10, `docs/dev-docs/code-conventions.md` §3, **`docs/dev-docs/systems/agents.md`** |
| `src/agents/mock.py` (재생 로직) | `docs/runtime-docs/protocol.md` §8 mock 어댑터, README 5초 데모 명령, `tasks/<task>/recordings/` 형식, **`docs/dev-docs/systems/agents.md`** |
| `src/orchestrator.py` 턴 라이프사이클 | `docs/runtime-docs/protocol.md` §4 turn lifecycle, **`docs/dev-docs/systems/orchestrator.md`**, **`docs/runtime-docs/systems/<mode>.md` (영향 받는 모드)** |
| `src/orchestrator.py` MODE_ROLES dict | `docs/runtime-docs/protocol.md` §3 모드↔role 매핑, `docs/dev-docs/architecture.md` §4, **`docs/dev-docs/systems/orchestrator.md`**, **`docs/runtime-docs/systems/INDEX.md`** 4 모드 매트릭스 |
| `src/bus.py` (JSONL writer·flush 정책) | `docs/runtime-docs/protocol.md` §2, `docs/dev-docs/code-conventions.md` §4, **`docs/dev-docs/systems/jsonl-bus.md`** |
| `src/schema.py` (메시지 dataclass 필드) | `docs/runtime-docs/protocol.md` §2 메시지 스키마 (필드 1:1 일치 검증), **`docs/dev-docs/systems/jsonl-bus.md` §schema** |
| `src/env_check.py` (`dialectic doctor` 점검 항목) | **`docs/dev-docs/systems/env-check.md`**, README §환경설정 |
| `src/cli.py` (서브커맨드·인자) | `README.md` 사용 예시, `docs/dev-docs/code-conventions.md` §6, `docs/dev-docs/architecture.md` §4 모드별 명령, **`docs/dev-docs/systems/orchestrator.md` §cli**, **`docs/runtime-docs/systems/<mode>.md` §1** |
| subprocess `cwd=` 또는 ADR-6 차단 메커니즘 (横단) | **`docs/dev-docs/systems/cwd-isolation.md`**, `docs/dev-docs/architecture.md` ADR-6, `outline/01-harness-layers.md` §1.3 |
| `src/ui.py` (사용자 개입 UI) | `outline/03-ux.md` §2.2/2.3 |
| `src/dev_skill_cli.py` (dev-time 스킬 wrapper) | `README.md` 개발 / 기여, `setup.sh` 설치 후 안내, `AGENTS.md`/`CLAUDE.md` Skills §5, `docs/dev-docs/codex-compat.md` Command Wrapper, `.codex/skills/<workflow>/SKILL.md` 존재 검증 |
| `dialectic-skill` repo-root wrapper | `README.md` 개발 / 기여, `setup.sh` 설치 후 안내, `pyproject.toml` console script와 동작 일치 검증 |

### 1.2 런타임 .md 변경 (B 층)

| 변경 부위 | 갱신 대상 |
|---|---|
| `docs/runtime-docs/protocol.md` 메시지 스키마 **필드** 변경 (필드 추가·제거·자료형 변경) | `src/schema.py`, `src/bus.py`, `tests/test_schema.py`, `docs/dev-docs/architecture.md` §5 인용 부분 |
| `docs/runtime-docs/protocol.md` 정책 단락 추가 (MUST/SHOULD 표현, example 갱신, docstring) | (mapping 외 — sync-docs 게이트 영향 X) |
| `docs/runtime-docs/protocol.md` 모드 추가 | `src/orchestrator.py` MODE_ROLES, `docs/runtime-docs/roles/<new>.md` 작성, `docs/dev-docs/architecture.md` §4, `README.md` 4 모드 표 |
| `docs/runtime-docs/roles/<role>.md` 셀프체크 형식 | `docs/runtime-docs/protocol.md` §5 4섹션 프롬프트 (셀프체크 인용 부분), `outline/01-harness-layers.md` §1.4 |
| `docs/dev-docs/validation.md` 새 결함 패턴 | 해당 패턴이 적용될 `docs/runtime-docs/roles/*.md` 셀프체크에 항목 추가 검토 |

### 1.3 개발용 .md 변경 (A 층)

| 변경 부위 | 갱신 대상 |
|---|---|
| `CLAUDE.md` / `AGENTS.md` Pre/Post Checklist 변경 | 양쪽 동기화 (둘이 어긋나면 안 됨), 해당 항목이 가리키는 .md 경로 검증 |
| `docs/dev-docs/code-conventions.md` 규칙 추가 | `.claude/skills/review-code/SKILL.md` 검사 항목, `docs/dev-docs/Checklists/review-code-checklist.md` |
| 본 파일(`Documentation-Checklist.md`) 매핑 추가 | `.claude/skills/sync-docs/SKILL.md` 동작 검증 (새 매핑이 자동 점검에 포함되는지) |

### 1.4 스킬·체크리스트 변경

| 변경 부위 | 갱신 대상 |
|---|---|
| `.claude/skills/<skill>/SKILL.md` 본문 변경 | `.claude/skills/SKILLS.md` 인덱스의 해당 항목 한 줄 설명 (어긋나지 않게) |
| `docs/dev-docs/codex-compat.md` 변경 | `AGENTS.md`/`CLAUDE.md` Codex 호환 안내, `.claude/skills/SKILLS.md` Codex 호환 원칙, `.codex/skills/<workflow>/SKILL.md` 포트 참조 |
| `.codex/skills/<workflow>/SKILL.md` 변경 | 대응 `.claude/skills/<workflow>/SKILL.md` 정본 경로와 `docs/dev-docs/codex-compat.md` override 적용 여부 검증 |
| `.codex/skills/claude-skill-compat/SKILL.md` 변경 | `docs/dev-docs/codex-compat.md`와 어댑터 책임 일치 검증, `AGENTS.md`/`CLAUDE.md` Codex 호환 레이어 안내 |
| 새 스킬 추가 | `.claude/skills/SKILLS.md` 인덱스 (Tier 분류), `CLAUDE.md`/`AGENTS.md` 스킬 사용 안내 (필요 시) |
| `.claude/skills/review-plan/SKILL.md` | `docs/dev-docs/Checklists/review-plan-checklist.md` (검사 항목 동기화) |
| `.claude/skills/review-code/SKILL.md` | `docs/dev-docs/Checklists/review-code-checklist.md` (검사 항목 동기화) |
| `.claude/skills/create-plan/SKILL.md` 형식 | `docs/dev-docs/Plans/plan-writing-guide.md` AS-IS/TO-BE 형식, 기존 `outline/` 산출물과 일관성 |

### 1.5 task·녹음 변경

| 변경 부위 | 갱신 대상 |
|---|---|
| `tasks/<task>/task.md` 추가/변경 | `README.md` 데모 task 예시, `tasks/<task>/recordings/` 갱신 (태스크 변경 시 기존 녹음은 invalid) |
| `tasks/<task>/recordings/` 추가 | `README.md` mock 데모 명령, `meta.json` 기록 |

### 1.6 인프라·배포 변경

| 변경 부위 | 갱신 대상 |
|---|---|
| `pyproject.toml` (entry points·deps) | `setup.sh` 검증, `README.md` 설치 단계 |
| `setup.sh` 변경 | `README.md` 설치 단계, `docs/dev-docs/code-conventions.md` §2 외부 의존성 검증 |
| 새 외부 의존성 추가 (예외) | `docs/dev-docs/code-conventions.md` §2 + `docs/dev-docs/architecture.md` ADR (왜 추가 필요했는지) |

### 1.7 큰 결정·아키텍처 변경

| 변경 부위 | 갱신 대상 |
|---|---|
| 새 ADR 결정 | `docs/dev-docs/architecture.md` §6 ADR 표, `outline/README.md` 결정 보드 (Q번호) |
| 모드 추가/제거 | `docs/dev-docs/architecture.md` §4 데이터 흐름, `docs/runtime-docs/protocol.md` §3, `src/orchestrator.py` MODE_ROLES, README 4 모드 표, 새 role.md 작성 (필요 시) |
| 포지션/역할/벤더 3축 변경 | `docs/dev-docs/architecture.md` §4, `docs/runtime-docs/protocol.md` §1.0, `src/cli.py` 인자 |
| interactive default 변경 (Q18) | `outline/03-ux.md` §3.1·§3.3, `outline/02-communication.md` §2.3, `outline/04-requirements-and-modes.md` §4.1·§4.5.1 |
| [CONVERGED] 마커 약속 (ADR-9) | `docs/runtime-docs/roles/{spec,plan}-reviewer.md`, `outline/02-communication.md` §2.9, `outline/01-harness-layers.md` §1.4 |
| ADR 추가 (ADR-9) | `docs/dev-docs/architecture.md` §6, `outline/README.md` §6 |

---

## 2. 사용 방법

### 변경 작업 시작 전 (Pre-Implementation)

1. 본 표에서 변경 부위에 해당하는 행 찾기
2. "갱신 대상" 모두 검토 — 어떤 .md를 함께 손볼지 사전 계획
3. 누락 가능성 0 검증

### 변경 작업 종료 후 (Post-Implementation)

1. `sync-docs` 스킬 호출 → 본 표 기준으로 자동 점검
2. 누락 발견 시 추가 commit
3. commit message에 "Update X to reflect Y change" 명시

---

## 3. 본 표 자체의 변경

본 표가 누락하는 변경 유형이 발견되면:

1. 본 파일에 행 추가
2. `.claude/skills/sync-docs/SKILL.md`가 새 매핑을 점검하는지 검증
3. commit message: "Add Documentation-Checklist mapping for X"

---

## 4. 누락 시 결과

이 표가 누락하는 매핑은 **자동 점검 사각지대**가 됨. 즉 코드와 문서의 불일치가 발견 안 된 채 누적될 수 있음. 본 표를 완전하게 유지하는 것이 4계층 중 **Protocol 계층의 핵심**.
