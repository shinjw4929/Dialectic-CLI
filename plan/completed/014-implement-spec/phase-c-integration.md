# Phase C · 통합 테스트 (plan→implement chaining) — 014-implement-spec

## 0. 메타

- Phase ID: C
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: B + D (`run_session` implement 분기 + `apply_patches` 신규 파일 분기 사용)
- 병렬 그룹: —
- 예상 LOC: ~5 (코드 변경, 문서 cascade 위주) + ~25 (테스트 추가)

## 1. 목표

plan→implement chaining 통합 테스트로 wiring 일관성 검증 — plan 모드 1턴 산출 spec.md를 implement 모드 입력으로 재진입했을 때 (1) spec body가 build_prompt §2 TASK에 진입하는지 (2) `dialectic implement` alias subparser와 `dialectic run --mode implement` 동등 동작하는지 (3) 메뉴 단계 2 implement 분기 → 단계 3 spec 입력 → run_session 진입 시점에 wiring 정합성 확인 (4) **mock implementer가 신규 파일 patch fence 응답 시 workdir에 .py 파일 생성 검증** (Phase D 산출 의존). 문서 cascade 5건 동시 처리. + dijkstra 실 시연 1회 (사용자 명시 후).

## 2. 입력

- Phase A 산출 — `--spec` 인자 + `dialectic implement` alias + `_input_spec_path` 메뉴 helper + `_input_mode` implement 활성
- Phase B 산출 — `run_session` mode==implement 분기 + spec read 검증 + args.task substitution
- [`tests/test_spec_autosave.py`](../../tests/test_spec_autosave.py) — `_mock_runner` / `_patch_runners` mock 패턴 재사용 (Phase B 통합 테스트와 일관)
- [`docs/dev-docs/Documentation-Checklist.md §1.1`](../../docs/dev-docs/Documentation-Checklist.md) — `src/orchestrator.py`/`src/cli.py` 매핑 행 (sync-docs 자동 catch 대상 + 신규 매핑 행 추가)
- 사전 검증 사실: plan 모드 mock 1턴 후 `<workdir>/specs/<slug>.md` 파일 생성됨 (plan 013 산출 ✓)
- 사전 검증 사실: implement 모드 driver(implementer) 응답이 patches fence 포함하면 `extract_patches` + `apply_patches` 자동 호출 (run 모드와 동일 흐름, plan 005 산출)

## 3. 출력

### 3.1 통합 테스트 — `tests/test_implement_spec.py` 누적 (Phase A·B 위)

```python
# spec — Phase C 케이스 (≥3)
def test_plan_to_implement_chaining_with_new_file(tmp_path, monkeypatch):
    """plan 1턴 → spec.md 생성 → implement 1턴 → spec body가 §2 TASK 진입 + 신규 .py 파일 생성.

    1. mode=plan + mock planner 응답 = "Spec · add(a, b)\n\n## Signature\n..."
       → run_session 1회 → <workdir>/specs/<slug>.md 생성
    2. mode=implement + spec=<위 path> + mock implementer 응답에 신규 파일 patch fence:
          FILE: add.py
          <<<<<<< SEARCH
          =======
          def add(a, b):
              return a + b
          >>>>>>> REPLACE
       → run_session 1회 → bus 내 turn_id=0 task 메시지 content == spec body
       → workdir에 add.py 생성 + content == "def add(a, b):\n    return a + b\n"
       → bus 내 patch_applied 메시지 meta.apply_status == "ok"
       (Phase D 산출 신규 파일 분기 검증)
    """

def test_implement_alias_vs_mode_implement_equivalence(tmp_path, monkeypatch):
    """`dialectic implement --spec X` ↔ `dialectic run --mode implement --spec X` 동등.

    두 호출 path 모두 같은 args.mode/args.spec/args.task 결과 → run_session 동일 진입.
    bus 메시지 비교: turn_id=0 task content + meta.mode 동일.
    """

def test_menu_implement_branch_spec_path(tmp_path, monkeypatch):
    """메뉴 단계 2 implement 선택 → 단계 3 _input_spec_path 호출 → run_session 진입.

    monkeypatch input 시퀀스: '3' (mode=implement) → spec path → ... (단계 4 default)
    검증: run_session 호출 시 args.mode='implement' + args.spec=<input path>
    """
```

mock 패턴 — `tests/test_spec_autosave.py`의 `_mock_runner` import 또는 helper 모듈로 분리(권고 P2).

### 3.2 문서 cascade 5건

#### 3.2.1 `docs/runtime-docs/systems/INDEX.md` implement 행 갱신

```diff
- | **implement** | (Day 3+ 추가) | implementer / spec-reviewer | run과 동일 | `<workdir>/<file>` 코드 (spec.md 입력) | 미구현 — `--spec @<path>` 입력 메커니즘 + `build_prompt` implement 분기 부재 |
+ | **implement** | INDEX 매트릭스 + `protocol.md §5 :282-284` | implementer / spec-reviewer | run과 동일 | `<workdir>/<file>` 코드 (spec.md 본문이 §2 TASK 자리에 주입, run과 동일 patch_apply 흐름) | spec read·검증·substitution **plan 014 ✓**. 메뉴 단계 2 implement 분기 active |
```

#### 3.2.2 `docs/runtime-docs/protocol.md §5 :282-284` cross-check

기존 narrative "implement 모드는 task 대신 spec.md 본문 주입" — 본 plan 산출로 wiring 충족. narrative 자체 변경 0, 단 §5 끝 또는 §3 모드별 산출물 표(plan 013 추가)에 implement 행 narrative 정합 cross-check 1줄 추가:

```python
# spec — protocol.md §3 모드별 산출물 표 implement 행 narrative 보강 (이미 존재 시 cross-check만)
```

#### 3.2.3 `docs/dev-docs/systems/orchestrator.md` `run_session` mode 분기 narrative

`run_session` 단락(현재 plan 010/013 narrative 위치)에 implement 분기 narrative 1단락 추가 — spec read 4종 검증 + args.task substitution + `_task_msg`/`build_prompt §2 TASK` 일관성.

#### 3.2.4 `docs/dev-docs/Documentation-Checklist.md §1.1` 매핑 행

```python
# spec — 신규 행
| `src/orchestrator.py::run_session` mode==implement 분기 (plan 014, spec read·검증·args.task substitution) + `src/cli.py::p_implement` alias subparser + `_input_spec_path` 메뉴 helper | **`docs/dev-docs/systems/orchestrator.md` §run_session mode 분기**, **`docs/runtime-docs/protocol.md §5 :282-284` cross-check**, **`docs/runtime-docs/systems/INDEX.md` implement 행**, `docs/runtime-docs/roles/planner.md:11` cross-check (narrative 변경 X, wiring 정합), `tests/test_implement_spec.py` ≥10건 단언, `README.md` plan→implement chaining 5초 데모 + 〈현재 동작 모드〉 1줄 |
```

#### 3.2.5 `README.md` 〈현재 동작 모드〉 + 5초 데모

```python
# spec — 〈현재 동작 모드〉 단락에 implement 활성 narrative 1줄 추가
- **Day 3+ 진행**: ... `--mode implement --spec <path>` 또는 `dialectic implement --spec <path>` wiring 활성 (plan 014). spec.md 본문이 build_prompt §2 TASK 자리에 주입, driver(implementer) ↔ reviewer(spec-reviewer) 1턴 라이프사이클 + 매 턴 patch_apply ...
```

5초 데모 단락에 chaining 1줄 추가:
```bash
# spec
dialectic plan --task "Python add(a, b)" --workdir /tmp/demo
dialectic implement --spec /tmp/demo/specs/python-add-a-b.md --workdir /tmp/demo
```

#### 3.2.6 `docs/dev-docs/Plans/upcoming-plans.md`

- mermaid `P014[plan 014<br/>implement-spec<br/>backlog]` → `<br/>completed`
- plan 014 entry 신규 단락 (plan 013 entry 직후 또는 P012 직전 위치)

## 4. 작업 단위

- [ ] (Pre-execute) `grep -n "## plan 013-spec-autosave\|P014\[" docs/dev-docs/Plans/upcoming-plans.md`로 plan 013 entry + P014 mermaid 노드 위치 재확인 (sync-docs cascade 진입점)
- [ ] `tests/test_implement_spec.py`에 Phase C 케이스 3건 추가 (Phase A·B 위 누적, 총 ≥10건)
- [ ] mock helper — `tests/test_spec_autosave.py`의 `_mock_runner` 직접 import 또는 본 파일 내 재정의
- [ ] `docs/runtime-docs/systems/INDEX.md` implement 행 갱신 (위 §3.2.1)
- [ ] `docs/runtime-docs/protocol.md §3` 모드별 산출물 표 implement 행 narrative cross-check (이미 정합이면 변경 0)
- [ ] `docs/dev-docs/systems/orchestrator.md` `run_session` 단락에 implement 분기 narrative 1단락 추가
- [ ] `docs/dev-docs/Documentation-Checklist.md §1.1`에 신규 매핑 행 추가 (위 §3.2.4)
- [ ] `README.md` 〈현재 동작 모드〉 implement 활성 narrative + 5초 데모 chaining 1줄
- [ ] `docs/dev-docs/Plans/upcoming-plans.md` P014 노드 backlog → completed + entry 신규 단락
- [ ] (DoD) `pytest -q` 전체 baseline + 신규 ≥18 케이스 (A 3 + B 5 + D 5 + C 5) pass + 회귀 0
- [ ] (DoD) **dijkstra 실 시연** (사용자 명시 후, API 비용) — `tasks/implement-dijkstra/task.md` 1차 task 본문으로 plan 모드 1턴 → spec.md 생성 → implement 모드 1턴 → workdir에 dijkstra.py 생성 + `meta.apply_status="ok"` + `meta.files_changed=["dijkstra.py"]`. critical 모드 follow-up directive(visualize 추가 등) 별도 plan
- [ ] (DoD) sync-docs 호출 → SYNC_DOCS_STATUS: OK 확인
- [ ] (DoD) review-code 호출 (서브에이전트 격리) → P0/P1 = 0 확인
- [ ] (DoD) 사용자 명시 후 실 호출 시연 1회 (plan→implement chaining, API 비용)

## 5. 검증

- `pytest -q tests/test_implement_spec.py` Phase A·B·C 누적 ≥10 케이스 pass
- `pytest -q` 전체 회귀 0
- `dialectic implement --help` 출력 정합 (subparser + `--spec` required + 다른 인자 default 정합)
- 실 호출 시연 (사용자 명시 후, API 비용 발생):
  ```bash
  dialectic run --task "Python add(a, b) 함수 작성" --mode plan --max-turns 1
  # → ~/.local/share/dialectic/runs/<ts-id>/specs/python-add-a-b-함수-작성.md 생성
  WORKDIR=$(ls -td ~/.local/share/dialectic/runs/*/ | head -1)
  SPEC="$WORKDIR/specs/python-add-a-b-함수-작성.md"
  dialectic implement --spec "$SPEC" --max-turns 1
  # → workdir에 add.py 생성 (search-replace patch)
  ```

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **mock helper 재사용 vs 재정의**
   - `tests/test_spec_autosave.py`의 `_mock_runner`/`_patch_runners`를 import하면 양 테스트 파일 결합도 ↑ (한쪽 시그니처 변경 시 타쪽 fail)
   - 재정의하면 DRY 위반
   - **mitigation**: `tests/_mock_runners.py` (또는 `conftest.py` fixture) 추출 권고 (P2). 본 plan 1차는 import 채택 + 추출 별도 plan

2. **plan→implement chaining mock 시나리오 — 진짜 driver 응답 vs 사용자 수동 spec.md 편집**
   - 본 통합 테스트는 mock driver가 미리 정의된 spec body 응답 → spec.md write → implement 모드 진입
   - 실제 사용 시나리오: 사용자가 plan 모드 산출 spec.md를 편집 후 implement에 입력 — 본 테스트는 그 시나리오 cover 0 (사용자 편집은 외부 행위)
   - **mitigation**: 통합 테스트는 wiring 정합성만 검증, 실 사용은 §5 시연

3. **`dialectic implement` alias subparser와 `--mode implement` 인자 default 차이**
   - `p_run`은 `--mode` choices `["run", "plan", "implement"]` default `"run"`
   - `p_implement`는 `set_defaults(mode="implement", task="")`
   - `--task`/`--mode` 인자 노출 vs 자동 default 차이 — argparse 호출 시 사용자 인자 차이로 회귀 가능성
   - 차단: Phase A §3.2 spec 그대로 작성 + Phase C §3.1 `test_implement_alias_vs_mode_implement_equivalence`로 cross-check

4. **post-014 메뉴 5단계 narrative — `outline/03-ux.md §3.2` 갱신 여부**
   - `outline/03-ux.md` line 104-252는 plan 011 산출 시점 narrative — implement 분기 deferred로 적혀있을 가능성
   - sync-docs cascade 시 catch — 본 plan §3.2 cascade 외 발견 시 추가 갱신
   - 본 phase §4 작업 단위에 없지만 sync-docs 보고 시 발견 시 처리

5. **review-code P2 누적 가능성**
   - plan 013 review-code에서 P2 5건 누적됨 (`max_len` 미사용 / spec write OSError / fallback-of-fallback / test import 위치 / mock workdir 하드코딩)
   - 본 plan에서 같은 패턴 반복 가능 — 특히 `_mock_runner` 재사용 시 `Meta.workdir="/tmp/mock"` 하드코딩 답습
   - **mitigation**: Phase C §3.1 mock 작성 시 `str(tmp_path)` 패턴 채택 (review-code 권고 정합)

6. **sync-docs `SYNC_DOCS_STATUS: BLOCKED` 시 commit 차단**
   - 본 plan은 5건 cascade 동시 처리 — 누락 시 commit 진입 차단
   - **mitigation**: Phase C §4 작업 단위에 5건 모두 명시 + DoD 체크박스 sync-docs OK 명시
