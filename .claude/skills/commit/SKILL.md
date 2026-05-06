---
name: commit
description: 변경 분류 → 사용자 확인 → 의미 단위 순차 커밋. 한 commit = 한 의도. WIP/fix 같은 모호한 메시지 금지.
tier: 독립
---

# commit

## 책임

작업 완료 후 변경 사항을 **의미 단위로 분류**하고, 사용자 확인 후 순차 commit.

## 호출 시점

- 작업 완료 직후
- `execute-plan` 실행 후 (plan에 따른 변경이 분류 가능한 단계)
- 수동 변경 후 사용자가 명시 호출

## 절차

### 1. 변경 사항 수집

```bash
git status
git diff --stat
```

unstaged + staged 변경 모두 파악.

### 2. 의미 단위 분류표 작성

변경된 파일들을 다음 기준으로 묶음:

| 분류 기준 | 예시 |
|---|---|
| 같은 의도 (한 기능 추가) | `src/agents/codex.py` + `tests/test_codex.py` + `docs/runtime-docs/protocol.md` 갱신 |
| 같은 부위 (한 .md 정리) | `docs/dev-docs/architecture.md` ADR 표만 갱신 |
| 같은 도메인 (인프라) | `pyproject.toml` + `setup.sh` |

분류표를 사용자에게 markdown 표로 제시. **메시지 제목 + 본문 + 파일 목록을 한 표에 모두 포함** (본문 누락 방지):

```markdown
## 변경 분류

| # | 제목 | 본문 | 포함 파일 |
|---|---|---|---|
| 1 | Add codex adapter with cwd isolation | subprocess.run에 cwd=resolved_workdir 강제.<br>--sandbox read-only로 코드 실행 차단.<br>개발용 CLAUDE.md 누수 단위 테스트 추가. | src/agents/codex.py, tests/test_codex.py |
| 2 | Document codex options in protocol | 어댑터 추가에 따른 protocol.md 옵션 표 갱신.<br>code-conventions.md §5에 keyword-only 인자 명시. | docs/runtime-docs/protocol.md, docs/dev-docs/code-conventions.md |
| 3 | Update README install steps | setup.sh 추가로 install 절차 단순화.<br>README 상단 status banner와 일관시킴. | README.md, setup.sh |
```

본문은 §"Commit 메시지 규칙" 기준으로 작성 — 1줄 fix 외에는 필수. 분류표 제시 단계에서 본문이 비어 있으면 §3 사용자 확인 단계로 넘어가지 않는다.

### 3. 사용자 확인

분류표 → 사용자에게 "이 분류로 진행할까요? 수정 의견?" 질문. 사용자가 분류·제목·본문 수정 가능. **자동 commit 금지** — 항상 확인.

### 4. 순차 commit

확인된 분류 순서대로:

```bash
git add <files for #1>
git commit -m "Add codex adapter with cwd isolation"

git add <files for #2>
git commit -m "Document codex options in protocol"

# ...
```

각 commit 후 `git log --oneline -1`로 즉시 확인.

## Commit 메시지 규칙

**구조**:
- **1줄 제목 (50자 이하)** — 무엇을 바꿨는지 간략 요약 (동사로 시작)
- **빈 줄 1개**
- **본문 (72자 wrap)** — 바꾼 의도·효과·맥락. 단순 1-line fix 외에는 필수.

**제목 규칙**:
- **동사로 시작**: Add / Refactor / Document / Update / Remove / Fix
- 명령형 ("Added"가 아닌 "Add")
- 본 도구 specific 자동 추가 라인 없음 (Claude Code 기본 동작과 충돌 회피)

**본문 규칙**:
- "왜 이 변경이 필요했나" + "이 변경으로 무엇이 가능해지나" 위주
- 코드를 읽으면 자명한 "WHAT"이 아닌 "WHY/EFFECT"
- 관련 ADR/Q번호·이전 commit 인용 (필요 시)
- 부가 효과나 결정 거부된 대안도 짧게 명시 가능

### 좋은 예

```
Add codex adapter with cwd isolation

- subprocess.run에 cwd=resolved_workdir 강제
- --sandbox read-only로 코드 실행 차단
- 개발용 CLAUDE.md 누수 단위 테스트 추가
```

### 나쁜 예

- `WIP`
- `fix`
- `update files`
- `Add codex adapter and refactor JSONL bus and update README` (한 commit에 의도 3개)

## 분류 기준의 가장자리

- **테스트는 코드와 같은 commit**: `src/agents/codex.py` + `tests/test_codex.py`는 한 commit. 분리하면 1번 commit 후 테스트 깨진 상태.
- **문서 갱신은 코드와 같은 commit이 권장이지만, .md만 따로 정리하는 큰 변경은 분리**: 예 — 어댑터 1개 추가하면서 protocol.md 관련 부분 갱신은 같은 commit. 하지만 architecture.md를 통째로 재구성하는 작업은 별도 commit.
- **포맷·lint 변경은 별도 commit**: 의미 변경과 섞으면 diff 추적 어려움.

## 안전장치

- `git add -A` 또는 `.` 사용 X — 의도하지 않은 파일 포함 위험
- `git commit -am ...` 사용 X — 분류 단위 무시
- 강제 push (`git push -f`) 절대 X
- 사용자 명시적 승인 없으면 push 안 함

## 사후

commit 모두 완료 후:

```bash
git log --oneline -5    # 결과 확인
git status              # 깨끗한지 검증
```

남은 unstaged 변경이 있다면 사용자에게 보고 — 분류에서 누락됐을 수 있음.
