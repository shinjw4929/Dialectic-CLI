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
| `src/orchestrator.py` 턴 라이프사이클 (`run_turn`/`run_session` 시그니처 확장 포함 — `_serialize_history(*, exclude_reviewer)`/`build_prompt(*, exclude_reviewer)`/`run_turn(*, skip_reviewer, exclude_reviewer_history)` keyword-only 추가, `_decision_msg`/`_last_critique_msg_id`/`_last_proposal_msg_id`/`_setup_sigint_handler` helper 추가, `MAX_TURNS_HARD_CAP`/`META_DECISION_SEQ` 모듈 상수 추가) | `docs/runtime-docs/protocol.md` §4 turn lifecycle + §2 kind 표 (decision narrative), **`docs/dev-docs/systems/orchestrator.md`** (모듈 상수 표 + helper 표 + `run_session` mode 분기 narrative), **`docs/dev-docs/systems/jsonl-bus.md`** (decision meta 정직성), **`docs/runtime-docs/systems/<mode>.md` (영향 받는 모드)**, **`docs/current-implementation-flow.md` (한눈 흐름 변경 시)** |
| `src/orchestrator.py::_resolve_workdir` (workdir 우선순위 표 — `--workdir` > `DIALECTIC_RUNS_DIR` > `XDG_DATA_HOME` > `~/.local/share/dialectic/runs/`) | **`docs/dev-docs/systems/orchestrator.md` §_resolve_workdir 표**, **`docs/dev-docs/systems/cwd-isolation.md` §Layer 2** (default 경로 narrative + ADR-6 차단 범위), `docs/runtime-docs/systems/run-mode.md` §1 `--workdir` 행 + §3 메시지 흐름 경로 + §7 검증 명령, `tests/test_workdir_default.py` 5건 단언, `README.md` 5초 데모·CLI 옵션 표·workdir 안내 단락 |
| `src/orchestrator.py::_task_to_slug` / `_resolve_spec_path` (plan 013, plan 모드 spec.md 자동 저장 — `<workdir>/specs/<slug>.md` top-level + 충돌 시 `<slug>-<session_ts>.md` fallback) + `run_turn`·`_run_session_*` 3종 시그니처에 `*, spec_path: Path \| None = None` 추가 | **`docs/dev-docs/systems/orchestrator.md`** (`_task_to_slug` / `_resolve_spec_path` helper narrative + `run_turn` spec_path wiring 단락), **`docs/runtime-docs/protocol.md` §3 모드별 산출물 표**, `docs/runtime-docs/roles/planner.md` `:11`/`:139` cross-check (narrative 변경 X, wiring 정합), `tests/test_spec_autosave.py` 17건 단언, `README.md` plan 모드 산출 1줄 |
| `src/orchestrator.py::run_session` mode==implement 분기 (plan 014, spec read·검증 5종 SystemExit·`args.task` substitution + finally `entered_turn_loop` guard + `files_changed=0` SystemExit + `reason:` stderr 안내) + `src/cli.py::p_implement` alias subparser + `_input_spec_path` 메뉴 helper + `_input_mode` implement 활성 + `_input_confirm` spec echo + 단계 3 안내문 mode-aware 분기 (task vs spec) | **`docs/dev-docs/systems/orchestrator.md` §run_session implement 모드 wiring 단락 + finally 4 항목**, **`docs/runtime-docs/protocol.md §5 :282-284` cross-check** (narrative 변경 X — wiring 충족), **`docs/runtime-docs/systems/INDEX.md`** implement 행 갱신, `docs/runtime-docs/roles/planner.md:11` cross-check (narrative 변경 X — wiring 정합), `src/patch_apply.py` 신규 파일 분기 (`SEARCH=""` + not exists → write_text + parent mkdir + rollback unlink) + 정규식 빈 SEARCH alternation + markdown fence wrapping 1단 허용 → **`docs/dev-docs/systems/patch-apply.md`** narrative + `docs/runtime-docs/roles/implementer.md:78-83` 셀프체크 강화, `src/ui.py:58` `ROLE_LABEL_KO["spec-reviewer"]` "코드 검토자" rename (plan-reviewer "계획 검토자"와 의미 구분, plan 014 시연 catch), `tests/test_implement_spec.py` ≥18건 단언 + `tests/test_patch_apply_new_file.py` ≥6건 + `tests/test_patch_apply.py::test_extract_new_file_empty_search` (Phase A·B·C·D 누적 + 사후 fix 보강), `README.md` plan→implement chaining 5초 데모 + 〈현재 동작 모드〉 1줄, `docs/dev-docs/architecture.md §4 :103` `dialectic implement` alias narrative, `docs/current-implementation-flow.md :11-12` implement wiring 활성 |
| `src/orchestrator.py` MODE_ROLES dict | `docs/runtime-docs/protocol.md` §3 모드↔role 매핑, `docs/dev-docs/architecture.md` §4, **`docs/dev-docs/systems/orchestrator.md`**, **`docs/runtime-docs/systems/INDEX.md`** 4 모드 매트릭스 |
| `src/bus.py` (JSONL writer·flush 정책) | `docs/runtime-docs/protocol.md` §2, `docs/dev-docs/code-conventions.md` §4, **`docs/dev-docs/systems/jsonl-bus.md`** |
| `src/schema.py` (메시지 dataclass 필드 또는 `kind`/`vendor` enum docstring) | `docs/runtime-docs/protocol.md` §2 메시지 스키마 + §2 kind 표 + classDiagram Kind enum + vendor 주석 (필드/enum 1:1 일치 검증), **`docs/dev-docs/systems/jsonl-bus.md` §schema** (Message kind 행 + Meta vendor/agent_cli 행) |
| `src/patch_apply.py` (ADR-10 search-replace 모듈) | `docs/runtime-docs/protocol.md` §2 (`meta.patches`/`apply_status`/`apply_error`/`files_changed`), §4 R2.6/R2.7 mermaid, §9 실패 모드 3행, **`docs/dev-docs/systems/patch-apply.md`**, `docs/dev-docs/systems/cwd-isolation.md` §Layer 4 (`validate_patch_path` SSOT 1:1), `docs/runtime-docs/roles/implementer.md:78` 마커 형식 |
| `src/env_check.py` (`dialectic doctor` 점검 항목) | **`docs/dev-docs/systems/env-check.md`**, README §환경설정 / §`dialectic doctor` 안내, `src/env_check.py:1` 모듈 docstring (점검 항목 narrative 동기화) |
| `src/cli.py` (서브커맨드·인자) | `README.md` 사용 예시, `docs/dev-docs/code-conventions.md` §6, `docs/dev-docs/architecture.md` §4 모드별 명령, **`docs/dev-docs/systems/orchestrator.md` §cli**, **`docs/runtime-docs/systems/<mode>.md` §1**, **`docs/current-implementation-flow.md` (명령 표면 변경 시)** |
| `src/logs.py` (`dialectic logs` 흐름 관찰 — find_latest_session_dir / resolve_session_dir / format_summary / format_full / render_logs) | `outline/03-ux.md` §3.4 (산출물 구조 SSOT) + §3.5 (Q3 관찰성 — flag 명세·1차 범위·deferred), `README.md` "사용 예시" (`dialectic logs` 1줄 시연), `src/cli.py` `_logs_entry` Namespace 매핑 (subparser 인자 1:1 동기) |
| subprocess `cwd=` 또는 ADR-6 차단 메커니즘 (横단) | **`docs/dev-docs/systems/cwd-isolation.md`**, `docs/dev-docs/architecture.md` ADR-6, `outline/01-harness-layers.md` §1.3 |
| `src/ui.py` (사용자 개입 UI — `TriggerListener`/`prompt_decision`/`prompt_end_or_iterate`/`Spinner`/`stdin_canonical_off`/`stdin_utf8_mode`/`flush_stdin`/`print_message` 등 raw mode 자산) | **`docs/dev-docs/systems/ui.md`** (모듈 SSOT — §2 핵심 함수·클래스 표·§4 P-RAW 통로), `outline/03-ux.md` §3.1·§3.2·§3.3 (5 위치 cascade), `docs/dev-docs/code-conventions.md` §7 (TriggerListener 패턴), `docs/dev-docs/validation.md` P-RAW (raw mode 결함 패턴) |
| `src/dev_skill_cli.py` (dev-time 스킬 wrapper) | `README.md` 개발 / 기여, `setup.sh` 설치 후 안내, `AGENTS.md`/`CLAUDE.md` Skills §5, `docs/dev-docs/codex-compat.md` Command Wrapper, `.codex/skills/<workflow>/SKILL.md` 존재 검증 |
| `dialectic-skill` repo-root wrapper | `README.md` 개발 / 기여, `setup.sh` 설치 후 안내, `pyproject.toml` console script와 동작 일치 검증 |
| `dialectic` repo-root wrapper (shim) | `README.md` 5초 데모, `setup.sh` 설치 후 안내·`~/.local/bin` symlink 등록, `pyproject.toml` console script와 동작 일치 검증 (venv activate 없이도 동작 — `python3 -m src.cli`) |

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
| `docs/current-implementation-flow.md` 변경 | 본 문서는 루트 요약 지도. 세부 정본 변경 없이 요약만 갱신한 경우 추가 대상 없음. 흐름·CLI·종료 조건 의미 변경이면 해당 systems/protocol 정본 문서가 먼저 갱신됐는지 검증 |

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
| `docs/dev-docs/Plans/upcoming-plans.md` 변경 (backlog plan 추가/제거) | 본 파일이 backlog SSOT — plan 신규 작성 시점에 `plan/<work-id>/01-plan.md §0 메타` 또는 `§7 참조`에서 인용. 진입 후 plan 폴더 본문이 정본 (본 파일은 backlog 메모) — 진입 plan은 본 파일에서 entry 제거 (active만 남기는 패턴) |

### 1.5 task·녹음 변경

| 변경 부위 | 갱신 대상 |
|---|---|
| `tasks/<task>/task.md` 추가/변경 | `README.md` 데모 task 예시, `tasks/<task>/recordings/` 갱신 (태스크 변경 시 기존 녹음은 invalid) |
| `tasks/<task>/recordings/` 추가 | `README.md` mock 데모 명령, `meta.json` 기록 |
| `tools/repro_listener.py` (테스트 도구, src/ui.py:TriggerListener 변경 시 시연 검증) | `docs/dev-docs/systems/ui.md` TriggerListener 표 narrative + `docs/dev-docs/validation.md` C-015 (plan 015 부분 fix narrative, R-NNN 환원 보류) |

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
