---
name: sync-docs
description: 코드/.md 변경과 새 문서 추가 → docs/dev-docs/Documentation-Checklist.md 표 기준으로 갱신 누락된 .md 점검. 자동 수정은 안 함, 보고만.
tier: 2
---

# sync-docs

## 책임

코드(또는 .md) 변경, 새 문서 추가 후 `docs/dev-docs/Documentation-Checklist.md`의 매핑 표를 조회하여 **함께 갱신해야 할 .md 중 누락된 것**을 식별하고 사용자에게 보고.

자동 수정 금지 — 누락 보고만. 실제 갱신은 사용자가 결정.

## 호출 시점

- `execute-plan` 완료 후 자동
- 수동 코드 변경 후 사용자 호출
- `commit` 직전 권장 (분류 단계에서 누락 잡기)

## 절차

### 1. 최근 변경 목록 수집

```bash
git diff --name-only HEAD~1 HEAD     # 직전 commit 기준
git diff --name-only --cached         # staged 기준
git diff --name-only                   # unstaged 기준
git ls-files --others --exclude-standard  # untracked 신규 파일 기준
```

네 종류 다 합쳐서 변경된 파일 목록 확정. 특히 새 문서는 `git diff --name-only`에 잡히지 않으므로 `git ls-files --others --exclude-standard`를 반드시 포함한다.

### 2. Documentation-Checklist 표 조회

`docs/dev-docs/Documentation-Checklist.md` §1을 읽어 각 변경 파일에 대해:

- **변경 부위 행 찾기** (예: `src/agents/codex.py` → §1.1 "src/agents/codex.py" 행)
- **갱신 대상 컬럼 추출** (예: "docs/runtime-docs/protocol.md §10, docs/dev-docs/code-conventions.md §3, **docs/dev-docs/systems/agents.md**")

### 2.1 systems/ 진리문서 매핑 강제 검사 (NEW)

`docs/{dev,runtime}-docs/systems/` 하위 진리문서는 **모듈/모드 SSOT** — 변경 영향이 직접적이라 누락 catch 우선순위 ↑:

- `src/<module>.py` 변경 → `docs/dev-docs/systems/<module>.md` 갱신 매핑 (Documentation-Checklist §1.1) 필수
- `MODE_ROLES`/`run_session`/`[CONVERGED]` 변경 → `docs/runtime-docs/systems/<mode>.md` (영향 모드) 갱신 + `INDEX.md` 매트릭스 갱신
- 새 모듈/모드 추가 → systems/ 신규 .md 신설 + 해당 INDEX.md 한 줄 + Documentation-Checklist §1 매핑 행 추가
- systems/ 변경이 Documentation-Checklist에 매핑 0이면 → 매핑 추가 권고 보고 (sync-docs 자체 진화)

### 2.2 신규 .md 문서 추가 검사

변경 목록에 새 `.md` 파일이 있으면 파일 역할을 먼저 분류한다.

| 새 문서 유형 | 필수 확인 |
|---|---|
| `docs/dev-docs/systems/*.md` 또는 `docs/runtime-docs/systems/*.md` | 해당 `INDEX.md` 한 줄 추가 + `Documentation-Checklist.md` §1 매핑 행 추가 |
| `docs/runtime-docs/roles/*.md` | `protocol.md` role/prompt 매핑 + `Documentation-Checklist.md` §1.2 매핑 확인 |
| `docs/*.md` 루트 요약/지도 문서 | 어떤 정본 문서와 동기화되는지 본문에 명시 + 흐름/CLI/종료 조건 변경 시 이 문서가 갱신 대상이 되도록 `Documentation-Checklist.md` §1에 매핑 추가 |
| `plan/*/*.md` 계획 산출물 | plan 자체 산출물이므로 일반적으로 docs 매핑 대상 아님. 단 실행 결과로 코드/프로토콜 의미가 바뀌면 기존 매핑 적용 |
| `.claude/skills/*/SKILL.md` 또는 `.codex/skills/*/SKILL.md` | `Documentation-Checklist.md` §1.4 기준으로 인덱스/정본/호환 문서 동기화 확인 |

Checklist에 없는 새 문서 유형이면 "신규 매핑 필요"로 보고한다. 새 문서가 단순 요약이라도, 미래 코드 변경 시 같이 갱신돼야 하는 문서라면 Checklist 매핑을 추가해야 한다.

### 3. 갱신 대상 vs 실제 변경 비교

각 갱신 대상 파일이 변경 목록에 포함되어 있는가? 새 문서 추가의 경우 §2.2에서 요구한 인덱스/Checklist 매핑 파일도 실제 변경 목록에 포함되어 있는가?

| 변경 파일 | 갱신 대상 | 실제 갱신됨? |
|---|---|---|
| `src/agents/codex.py` | `docs/runtime-docs/protocol.md` §10 | ✓ |
| `src/agents/codex.py` | `docs/dev-docs/code-conventions.md` §3 | ✗ **누락** |
| `src/orchestrator.py` (MODE_ROLES) | `docs/dev-docs/architecture.md` §4 | ✗ **누락** |

### 4. 누락 보고

사용자에게 markdown 표로:

```markdown
## sync-docs 누락 보고

다음 .md를 함께 갱신해야 합니다:

| 변경 부위 | 갱신 누락 대상 | Checklist 근거 |
|---|---|---|
| src/agents/codex.py | docs/dev-docs/code-conventions.md §3 | §1.1 |
| src/orchestrator.py MODE_ROLES | docs/dev-docs/architecture.md §4 | §1.2 |

이 항목들을 갱신한 뒤 `commit` 실행을 권장합니다.
```

### 4.1 차단 신호

누락 항목이 1+ 존재하면 보고 끝에 마지막 줄에:

`SYNC_DOCS_STATUS: BLOCKED (n missing)`

누락 0이면:

`SYNC_DOCS_STATUS: OK`

`commit` 스킬이 본 신호를 점검 — `BLOCKED` 시 분류표 작성 진입 차단.

### 5. 사용자 결정

사용자가:
- (a) 누락 .md 갱신 후 다시 sync-docs 호출 (재검증)
- (b) 의도적 누락이면 Checklist 표 자체를 수정 (매핑이 잘못된 경우)
- (c) 해당 변경이 Checklist에 안 잡힌 새 유형이면 §1에 행 추가

## 안전장치

- 자동 .md 수정 금지 — 사용자 의도 모르는 채로 .md 변경 위험
- Checklist에 없는 변경 부위는 "신규 매핑 필요" 보고 — 잠재 누락 가능성을 사용자에게 알림
- untracked 신규 파일을 반드시 포함 — 새 문서 추가가 sync-docs 사각지대가 되는 것을 차단
- "전체 OK" 응답 시에도 표 형식으로 명시 — 자동화 환경에서 검증 가능
- **pytest/compileall 등 코드 회귀 검증 금지** — 본 스킬은 문서 매핑만 검증. 코드 회귀는 `review-code` 또는 `execute-plan` 책임. narrative만 갱신한 호출에서 pytest 실행은 토큰·시간 낭비 + 절차 분리 위반

## 한계

- Checklist 표가 빠뜨린 매핑은 본 스킬도 못 잡음 → 본 스킬과 Checklist 표는 함께 진화해야 함
- 의미적 정합성(예: protocol.md 본문이 실제로 코드 변경을 정확히 반영하는가)은 본 스킬 범위 X — `review-code` 스킬이 별도 검사

## 본 스킬 자체의 변경

본 스킬 동작 변경 시:

- `docs/dev-docs/Documentation-Checklist.md` §1.3 (개발용 .md 변경)에 매핑 추가
- `.claude/skills/SKILLS.md` 인덱스의 한 줄 설명 갱신
