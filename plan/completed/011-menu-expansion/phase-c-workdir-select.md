# Phase C · 단계 4 workdir·max-turns 선택 (단계 4 묶음의 workdir 슬롯) — 011-menu-expansion

## 0. 메타

- Phase ID: C
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: B (mode + 매핑 wiring 완료 후 진입)
- 병렬 그룹: —
- 예상 LOC: ~25 (코드) + ~12 (테스트)
- outline 단계 매핑: outline `:172-178` 단계 4의 workdir 슬롯 + max-turns 입력 호출 정렬. Phase B와 함께 단계 4 묶음 형성

## 1. 목표

`dialectic` 단독 실행 메뉴 단계 4의 workdir 슬롯을 outline `:172-178` narrative대로 노출 — 자동 생성(orchestrator default 위임) / 직접 입력 2 분기. ADR-6 (cwd 격리) repo-root 차단은 orchestrator `:616-625` SSOT 위임 (메뉴 client-side 검증 X — 단일 진실원 보존). max-turns 입력은 기존 `_input_max_turns` 재사용 (단계 4 묶음 안에서 호출 순서만 정렬).

## 2. 입력

- [`src/cli.py:57-61`](../../src/cli.py) — `--workdir` argparse default=None (변동 없음)
- [`src/cli.py:265`](../../src/cli.py) — Namespace `workdir=None` 하드코딩 (Phase C 대상). 참고: line 번호는 plan 009 적용 후 (uncommitted)
- [`src/cli.py:183-198`](../../src/cli.py) — `_input_max_turns` 재사용 (단계 4 묶음 안에서 workdir 직후 호출)
- Phase B 산출 — `mode`, `driver`, `reviewer` 변수 존재 + `_input_confirm` 시그니처 1차 확장 완료
- [`tests/test_cwd_isolation.py`](../../tests/test_cwd_isolation.py) + [`tests/test_cwd_isolation_integration.py`](../../tests/test_cwd_isolation_integration.py) — ADR-6 repo-root 차단 회귀 2종
- [`docs/dev-docs/architecture.md`](../../docs/dev-docs/architecture.md) ADR-6 — cwd 격리 메커니즘
- [`src/orchestrator.py:616-625`](../../src/orchestrator.py) — `DIALECTIC_REPO_ROOT` 검증 + SystemExit 차단 SSOT (본 Phase가 위임할 대상)
- [`outline/03-ux.md:172-178`](../../outline/03-ux.md) — 단계 4 workdir narrative SSOT
- [`docs/dev-docs/Plans/upcoming-plans.md`](../../docs/dev-docs/Plans/upcoming-plans.md) `:243-251` — plan 010 Phase C workdir default 변경 backlog (본 Phase 무관, 안내 문구만 추상화)

## 3. 출력

### 3.1 `src/cli.py` 변경

**`_interactive_menu_body` 단계 순서 (outline `:104-179` 정확 추종)**:

```
단계 1: 환경 점검 spinner          (기존)
단계 2: mode 선택                  Phase A — _input_mode
단계 3: task 입력                  (기존 _input_task)
단계 4: 매핑 + workdir + max-turns  Phase B (_input_mapping) + Phase C (_input_workdir + 기존 _input_max_turns)
단계 5: 진행 확인 + execute        (기존 _input_confirm + run_session)
```

신규 helper `_input_workdir` (single-prompt UX — 옵션 번호 vs 경로 모호성 차단):

```python
# spec
def _input_workdir() -> str | None:
    """단계 4 workdir 선택. single-prompt UX.

    빈 입력 (Enter) → None 반환 (orchestrator 자동 생성 — tempfile.mkdtemp 또는
    plan 010 진입 후 ~/.local/share/dialectic/runs/<...>).
    그 외 입력 → 경로로 해석:
      - 존재하는 디렉토리 → resolve된 절대 경로 반환
      - 존재하는 파일 → 거부 + 재입력
      - 존재 X → 생성 확인 [Y/n]: Y/Enter → mkdir + 반환, n → 재입력

    repo-root 차단은 본 helper의 책임 X — orchestrator `:616-625`의
    `DIALECTIC_REPO_ROOT` SystemExit이 SSOT (단일 진실원 보존, P-VENDOR 회피).
    EOF/Ctrl-C → _MenuExit propagate.
    """
```

**UX 설계 결정 (실 시연 결함 환원)**: 초기 버전(2-prompt: 1=auto/2=직접 입력→경로)에서 사용자가 첫 prompt에 경로 직접 입력 → invalid retry 회귀 결함 발생. single-prompt(Enter=auto, 그 외=경로)로 모호성 제거. 경로 입력 시 존재 검증 추가로 오타·존재 X 경로 사용자 의도 확인 (orchestrator 자동 mkdir과 분리 — 메뉴는 사용자 의도 확인, orchestrator는 ADR-6 차단 + sessions/ 자동 생성).

`_interactive_menu_body` 단계 4 묶음 wiring (Phase B `driver, reviewer = _input_mapping()` 직후):

```python
# spec
workdir = _input_workdir()
max_turns = _input_max_turns()  # 기존 호출 위치를 단계 4 묶음 안으로 정렬
```

`_input_confirm` 시그니처 2차 확장 (Phase B 1차 확장 위에 workdir 추가):

```python
# spec
def _input_confirm(*, max_turns: int, task: str, mode: str, driver: str, reviewer: str, workdir: str | None) -> bool:
    """진행 확인 — workdir 라벨 추가 (Phase B 1차 확장 위 2차).

    workdir is None → "workdir=auto"
    workdir is str  → f"workdir={workdir}"
    """
```

Namespace 구성 (mode/driver/reviewer/workdir 모두 동적, interactive 라인은 plan 009 산출 `"critical"` 보존):

```python
# spec
args = argparse.Namespace(
    cmd="run", task=task, workdir=workdir,
    driver=driver, reviewer=reviewer,
    max_turns=max_turns, mode=mode,
    convergence_streak=2, interactive="critical",  # plan 009 산출 보존, 본 plan 무관
)
```

### 3.2 단위 테스트 추가 — `tests/test_interactive_menu_expansion.py`

```python
# spec
def test_input_workdir_auto_default():
    """빈 입력 (Enter) → None 반환 (orchestrator default 위임)"""

def test_input_workdir_existing_dir(tmp_path):
    """기존 디렉토리 입력 → resolve된 절대 경로 반환"""

def test_input_workdir_create_confirm(tmp_path):
    """존재 X 경로 + 생성 확인 'Y' → mkdir + 반환"""

def test_input_workdir_create_default_enter(tmp_path):
    """존재 X 경로 + 생성 확인 Enter (Y default) → mkdir + 반환"""

def test_input_workdir_create_decline_then_existing(tmp_path):
    """존재 X 경로 + 'n' 거부 → 재입력 → 기존 디렉토리 → 반환"""

def test_input_workdir_file_rejected(tmp_path):
    """파일 경로 입력 → 거부 + 재입력 → 기존 디렉토리 → 반환"""

def test_input_workdir_eof():
    """EOF → _MenuExit propagate"""
```

repo-root 차단 회귀는 별도 책임 — `tests/test_cwd_isolation.py` + `tests/test_cwd_isolation_integration.py`가 orchestrator `:616-625` SystemExit SSOT를 검증. 본 Phase 단위 테스트는 메뉴 helper 분리만 검사.

## 4. 작업 단위

- [ ] `src/cli.py`에 `_input_workdir` 함수 추가 — 단순 입력 수집만 (None / 문자열 그대로 반환)
- [ ] `_interactive_menu_body` 단계 4 자리에 `workdir = _input_workdir()` 호출 삽입
- [ ] 단계 순서 정리 (env_check → mode → task → 매핑 → workdir → max-turns → confirm) — outline `:104-179` narrative 추종
- [ ] `_input_confirm` 시그니처 2차 확장 (Phase B 1차 위에 `workdir: str | None` 추가) + echo 라인에 workdir 포함
- [ ] `_input_confirm` 호출부 인자 추가
- [ ] Namespace `workdir=workdir` 동적화 (mode/driver/reviewer/workdir 모두 동적 완성)
- [ ] `_interactive_menu_body` docstring 갱신 — 5단계 모두 wiring 명시 + outline `:104-179` 인용 + ADR-6 SSOT 위임 명시 (현재 docstring `:215-228` "Day 2 한정 ... --interactive end-only 고정" 표기는 plan 009 산출과 어긋남 — plan 011이 5단계 narrative로 통합 갱신)
- [ ] 단위 테스트 4 케이스 추가
- [ ] `tests/test_cwd_isolation.py` + `tests/test_cwd_isolation_integration.py` 회귀 통과 확인

## 5. 검증

- `python -c "from src.cli import _input_workdir; print(_input_workdir.__doc__)"` 성공
- `pytest -q tests/test_interactive_menu_expansion.py` Phase A·B·C 누적 14 케이스 pass (A 6 + B 4 + C 4)
- `pytest -q tests/test_cwd_isolation.py tests/test_cwd_isolation_integration.py` ADR-6 회귀 2종 통과
- `pytest -q` 전체 회귀 0
- 실 호출 시연 1: `dialectic` 실행 → 단계 1~5 모두 통과 → 자동 workdir → 1턴 실 호출
- 실 호출 시연 2: `dialectic` 실행 → workdir 직접 입력 (`/tmp/dialectic-manual-test`) → 1턴 실 호출 → JSONL이 해당 경로에 생성
- 실 호출 시연 3: `dialectic` 실행 → workdir 직접 입력에 repo-root(예: 본 repo 절대경로) 입력 → orchestrator 진입 직후 SystemExit 메시지 출력 + exit code != 0
- sync-docs 호출 결과: `docs/dev-docs/Documentation-Checklist.md` §1.1 `src/cli.py` 행 매핑된 .md(README, code-conventions §6, architecture §4, systems/orchestrator.md §cli, runtime systems/<mode>.md, current-implementation-flow.md) 누락 0

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **plan 010 workdir default 변경 후행**
   - plan 010 Phase C가 orchestrator의 자동 workdir default를 `tempfile.mkdtemp` → `~/.local/share/dialectic/runs/<...>`로 바꿈
   - 본 Phase의 `_input_workdir` "자동 생성" 분기는 단지 None을 반환 — orchestrator가 default 처리
   - plan 010 진입 시 본 Phase 코드 무변경, 단지 안내 문구 "자동 생성된 임시 디렉토리"가 더 이상 임시 아닐 수 있음 → "자동 생성된 작업 디렉토리"로 추상화 권장

2. **repo-root 차단 SSOT 위임 — UX 트레이드오프**
   - 본 Phase는 client-side 검증 0 — orchestrator `:616-625` `DIALECTIC_REPO_ROOT` SystemExit이 SSOT (단일 진실원 보존, P-VENDOR 회피)
   - 사용자가 repo-root 입력 시 단계 5 confirm 통과 후 orchestrator 진입 직후 SystemExit으로 차단 → 5단계 모두 채운 뒤 차단되는 UX 비효율
   - 트레이드오프 채택 이유: orchestrator의 ADR-6 차단 메커니즘이 함수 로컬(`run_session` `:616`) — module-level lift는 orchestrator 변경 동반 (scope creep). 본 plan은 UI 한정 scope 유지
   - 향후 개선: orchestrator의 `DIALECTIC_REPO_ROOT` + 검증 로직을 module-level util로 lift → cli.py가 import해서 client-side fail-fast — 별도 plan으로 분리

3. **존재하지 않는 경로 입력 정책 (UX 결함 환원 적용)**
   - 본 Phase는 메뉴 단계에서 사전 mkdir 확인 prompt 제공 — 사용자가 오타·존재 X 경로 입력 시 의도 확인 (Y → mkdir, n → 재입력)
   - orchestrator는 그 후 `Path(args.workdir).resolve()` (`:606`) + `sessions_dir.mkdir(parents=True, exist_ok=True)` (자동 생성, 본 Phase 책임 외)
   - 초기 결정("단순 통과")이 실 시연에서 사용자 경로 검증 부재 결함 발생 → mkdir 확인 분기 추가로 환원. 단 ADR-6 차단은 여전히 orchestrator SSOT (단일 진실원 보존, P-VENDOR 회피 정책 그대로)

4. **단계 4 묶음 순서**
   - 매핑(Phase B) → workdir(본 Phase) → max-turns(`_input_max_turns` 재사용) 3개 호출 연속
   - 사용자가 매핑·workdir·max-turns 중 하나에서 거부(예: confirm 'n')하면 어디로 back할지 정책 필요
   - 본 Phase 정책: confirm 'n' 시 task 재입력으로 back (기존 outer while 루프 유지) — 매핑·workdir·max-turns도 함께 재선택 (단순화)
   - 향후 개선: 단계별 back 메뉴 — 별도 plan

5. **outline 단계 번호 정확 추종**
   - outline은 단계 3 = task / 단계 4 = 매핑+workdir 순서
   - 본 plan은 outline 정확 추종 — 단계 3 task 입력은 기존 `_input_task` 그대로 유지, 단계 4가 매핑+workdir+max-turns 묶음
   - sync-docs가 outline `:104-179`와 어긋남 catch — outline narrative SSOT 보존
