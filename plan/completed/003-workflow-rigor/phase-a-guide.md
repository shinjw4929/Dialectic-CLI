# Phase A · 가이드·체크리스트 보강 — 003-workflow-rigor

## 0. 메타

- Phase ID: A
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: —
- 예상 LOC: ~20 LOC

## 1. 목표

phase 파일 §3 출력의 코드 블록에 spec/paste 라벨 도입. 가이드 단일 진실(plan-writing-guide.md)에 라벨 규칙 + 안티패턴 명시, review-plan-checklist에 검사 행 추가.

## 2. 입력

- `docs/dev-docs/Plans/plan-writing-guide.md:113-168` §3 phase 형식 (변경 대상)
- `docs/dev-docs/Plans/plan-writing-guide.md:183-192` §5 안티패턴 표 (변경 대상)
- `docs/dev-docs/Checklists/review-plan-checklist.md:33-44` §1.3 phase 본문 검사 (변경 대상)
- 사전 검증: `plan/001-run-mode-core/phase-c-orchestrator.md`에 코드 블록 7개 — paste/spec 의도 혼재 (00-plan.md §1.1 인용)

## 3. 출력

### 3.1 `docs/dev-docs/Plans/plan-writing-guide.md` 변경

#### 3.1.1 §3 phase 형식 본문 직후, 신규 §3.1 sub-section 추가

**삽입 위치**: `plan-writing-guide.md`의 file-level §3 영역 (line 113~170). file-level §3 외부 fenced code block은 line 117~168 (` ```markdown ... ``` `). 라벨 규칙은 fence 내부의 예시 markdown spec이 아니라 **fence 외부**의 실제 file-level sub-section으로 추가:

- **fence 종료 (line 168) 직후**, **구분자 `---` (line 170) 직전**
- 신규 sub-section 헤더: `### 3.1 코드 블록 라벨 (spec / paste)`
- file-level §3 (line 113 헤더)의 첫 sub-section으로 자리잡음

⚠️ **금지**: line 138 ("## 3. 출력")은 fence 내부 예시 텍스트 — 그 직후에 삽입하면 예시 markdown 안에 본 라벨 규칙이 섞여 들어가 의도와 어긋남.

아래 내용을 본 phase 파일에서 외부 4-backtick 펜스로 감싸 표현 (내부 3-backtick fenced code block 충돌 회피, CommonMark §6.6 — 외부 펜스 길이 N이면 내부는 N-1 이하면 OK). plan-writing-guide.md 본체에 작성 시는 외부 fence 없이 일반 markdown 본문으로:

````markdown
### 3.1 코드 블록 라벨 (spec / paste)

phase 파일 §3 출력의 코드 블록은 **execute-plan subagent의 자유 해석 폭**을 결정한다. 라벨로 의도 명시:

| 라벨 | 의도 | execute-plan 동작 |
|---|---|---|
| `spec` (default) | 시그니처·docstring·예시 명세 | 의도 보존하며 자유 해석. 함수 본문·타입·docstring은 subagent가 결정. |
| `paste` | 그대로 코드에 들어가는 정의 (상수, frozen dataclass, lambda, 정확한 dict 리터럴 등) | **변형 금지**. 들여쓰기·식별자·값 그대로 복사. |

표기: 코드 펜스 직후 첫 줄에 `# <label>` 인라인 주석:

```python
# paste
MODE_ROLES = { "run": {...}, "plan": {...} }
```

```python
# spec
def _msg(turn_id: int, ...) -> Message:
    """parent_id 추적·workdir 기록·meta sentinel 채움."""
```

라벨 부재 = `spec`. dataclass·상수·MODE_ROLES 같은 정의는 `paste` 명시 권장. 라벨은 **코드 펜스 직후 첫 줄에만** 인식 — 코드 본문 안의 `# spec`/`# paste` 주석은 무관.
````

#### 3.1.2 §5 안티패턴 표에 행 추가

`docs/dev-docs/Plans/plan-writing-guide.md:183-192` 안티패턴 표에 1행 추가:

```markdown
| paste 의도인데 라벨 없음 | execute-plan이 spec(자유 해석)으로 해석 → MODE_ROLES 같은 정의가 변형 위험 | 정의는 `# paste` 명시 |
```

### 3.2 `docs/dev-docs/Checklists/review-plan-checklist.md` 변경

`:33-44` §1.3 phase 본문 검사 표에 1행 추가:

```markdown
| §3 코드 블록 라벨 | paste 의도인 정의(상수·dataclass)는 `# paste` 라벨 명시? | P1 (라벨 부재) |
```

`§3 출력` 행("시그니처 부재 시 P0") 바로 다음 위치.

## 4. 작업 단위

- [ ] `plan-writing-guide.md` §3에 라벨 규칙 §3.1 신규 단락 작성 (~12 LOC, 본문은 3-backtick fenced block 그대로 — plan-writing-guide.md 자체가 markdown 파일이라 fenced block 내부 nested code는 아님)
- [ ] `plan-writing-guide.md` §5 안티패턴 표에 "paste 의도인데 라벨 없음" 행 추가 (~2 LOC)
- [ ] `review-plan-checklist.md` §1.3 phase 본문 검사 표에 "§3 코드 블록 라벨" 행 추가 (~2 LOC)
- [ ] markdown 렌더링 검증 (3-backtick fenced block 정상 표시)

## 5. 검증

- `grep -n "spec / paste" docs/dev-docs/Plans/plan-writing-guide.md` → 1행 매치
- `grep -n "라벨 부재" docs/dev-docs/Plans/plan-writing-guide.md` → 매치 (안티패턴 표)
- `grep -n "코드 블록 라벨" docs/dev-docs/Checklists/review-plan-checklist.md` → 1행 매치
- markdown 표 형식 깨짐 검사: `grep -c '^|' docs/dev-docs/Plans/plan-writing-guide.md` — 변경 전 baseline 캡처(grep 1회 → wc) 후 변경 후 차이 +1 (안티패턴 행)

## 6. 엣지케이스 / 위험 (Phase 한정)

### 6.1 fenced block escape — 4-backtick 결정

본 phase 파일 §3.1.1 자체가 plan-writing-guide.md에 작성될 markdown spec을 담고 있어 nested fenced code block 발생. **결정: 본 phase 파일에서 외부 펜스를 4-backtick(``\`\`\`\``)으로 감싼다**. 내부 fenced block은 3-backtick(```` ``` ````) 그대로. CommonMark §6.6: 외부 펜스 길이 N이면 내부는 N-1 이하면 종료 영향 X → 4-backtick 외부 + 3-backtick 내부 안전.

plan-writing-guide.md 본체에는 §3.1 단락이 직접 들어가므로 nested 아님 — 3-backtick fenced block 그대로 표기.

차단: 작업 시 fenced block **균형 검사** (위치 나열만으로 부족):

```bash
# fenced block 시작·종료 짝수 검증 (3-backtick + 4-backtick 각각)
awk '/^```$|^```[a-z]+$/ { c3++ } /^````$|^````[a-z]+$/ { c4++ } END { print "3-bt:", c3, "(짝수?", c3%2==0, ") 4-bt:", c4, "(짝수?", c4%2==0, ")" }' phase-a-guide.md
```

github/gitlab markdown preview로 1회 렌더링 검증.

### 6.2 default=spec 결정의 보수성

default가 `paste`였다면 변형 위험은 낮지만 기존 `plan/001-run-mode-core/`의 모든 코드 블록이 paste로 해석되어 execute-plan이 변형 못 함 → 실제 phase 파일 (시그니처+docstring 명세인 `def _msg`)을 그대로 paste하면 함수 본문 빈 채로 들어감. **default=spec이 호환성·운영 합리성 우선**.

### 6.3 `# spec` / `# paste` 키워드 충돌

Python 코드에 `# spec`, `# paste` 주석이 진짜 의미로 쓰이는 경우 — `paste`는 일반적이지 않으나 `spec`은 흔함. 단 라벨은 코드 펜스 **직후 첫 줄**에만 인식 — 실제 코드 안의 `# spec` 주석은 무관.

차단: 가이드 §3.1에 "코드 펜스 직후 첫 줄에만 라벨 인식" 명시 (이미 §3.1.1 본문에 반영).
