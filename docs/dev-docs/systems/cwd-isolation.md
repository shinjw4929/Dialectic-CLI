# cwd-isolation — ADR-6 메커니즘 (横단)

A 층(개발용 .md) ↔ B 층(런타임 prompt) 누수 차단 — `outline/01-harness-layers.md §1.3` + `architecture.md` ADR-6.

본 문서는 **모듈 진리**가 아닌 **횡단 정책 진리**. `src/orchestrator.py run_session` + `src/agents/{codex,claude}.py subprocess.run` + `src/env_check.py _run_capture`가 본 정책의 구현 위치.

## 위협 모델

```
+-------------------------------------------------------------+
| 위험 시나리오                                                |
+-------------------------------------------------------------+
| 1. 사용자가 Dialectic-CLI repo cwd에서 dialectic run 실행   |
|    → cwd=repo_root → claude/codex가 cwd CLAUDE.md 자동      |
|    로드 → A 층 개발용 prompt가 B 층 driver/reviewer에 누수  |
|                                                              |
| 2. --workdir <dialectic_repo_root>로 명시 입력              |
|    → Path.resolve() 정규화만으로는 차단 X                    |
+-------------------------------------------------------------+
```

## 차단 메커니즘 (3 layer)

### Layer 1: subprocess `cwd=workdir` 명시 (P-CWD)

모든 subprocess.run 호출에 `cwd=` 명시 — code-conventions §3 P0 규약.

| 위치 | cwd 값 |
|---|---|
| `src/agents/codex.py` `subprocess.run` | `cwd=workdir` (run 인자) |
| `src/agents/claude.py` `subprocess.run` | `cwd=workdir` (run 인자) |
| `src/env_check.py` `_run_capture` | `cwd=cwd or Path.home()` (default home — OAuth 캐시 위치 + Dialectic-CLI cwd 아님) |

`shell=True` 절대 금지 (review-code §안전성 P0).

### Layer 2: orchestrator `run_session` workdir 정규화 + repo-root/하위 차단

```python
# _resolve_workdir(args) — 우선순위 표 SSOT (plan 010 Phase C):
#   1. --workdir CLI 인자
#   2. DIALECTIC_RUNS_DIR 환경변수
#   3. XDG_DATA_HOME/dialectic/runs/
#   4. ~/.local/share/dialectic/runs/  (default, XDG Base Directory Specification 준수)
# 폴더명 = "<YYYYMMDD-HHMMSS>-<8char>" (mkdtemp suffix가 short-id, 1초 내 collision 0)
workdir = _resolve_workdir(args)

# 모듈 top SSOT — DIALECTIC_REPO_ROOT 상수 + is_under_repo_root(path) predicate.
# cli `_input_workdir`도 동일 helper를 import해 mkdir 전 UX-level 조기 거부 (P-VENDOR 회피).
if is_under_repo_root(workdir):
    raise SystemExit(
        f"--workdir이 Dialectic-CLI repo 루트 또는 그 하위 경로({workdir})입니다 (ADR-6). "
        f"별도 경로를 지정하거나 --workdir 미지정으로 임시 dir 자동 생성을 사용하십시오."
    )

cleanup = False  # --workdir 미지정 시에도 결과 보존 (사용자 확인 통로, C-010)
# 종료 시 stderr에 workdir + messages.jsonl 경로 안내. Day 3+ `--cleanup-workdir` 토글 검토.
```

**default 경로 narrative**: `/tmp/dialectic-XXXX` (post-mkdtemp) → `~/.local/share/dialectic/runs/<...>` (plan 010 Phase C). `/tmp` 후보 기각 근거 — reboot 시 휘발 + 비-Linux WSL2/macOS에서 위치 비일관. `/mnt/c` 기각 — WSL Windows mount 권한·case-sensitivity 결함. repo 하위 기각 — ADR-6 위반 (본 §Layer 2가 차단). XDG가 4 후보 중 유일하게 안전·표준 (memory `project_plan_010_workdir_default.md`).

**ADR-6 차단 범위**: `--workdir` CLI + `DIALECTIC_RUNS_DIR` env + `XDG_DATA_HOME`/`~/.local/share` default 어느 경로든 repo 루트 또는 하위 경로일 때 `run_session` 진입 직후 SystemExit. base_dir 자체가 repo 하위이면 mkdtemp가 repo 하위 임시 dir을 생성한 직후 차단되므로 `cleanup` 시 leak 차단(C-008).

**UX-level 조기 거부 (cli `_input_workdir`)**: 인터랙티브 메뉴는 동일 `is_under_repo_root` predicate를 import해 mkdir 직전 + 기존 dir 분기 직전에 차단한다. 사용자가 Dialectic-CLI repo 안에서 실행 후 relative path(`2`, `test3`)를 입력하면 `Path.resolve()`가 cwd 기준으로 repo 하위로 떨어지는데, 이 경우 mkdir 후 orchestrator가 SystemExit하면 orphan dir이 잔존(+ 사용자 혼란)함. helper 공유로 mkdir 전에 거부 + ADR-6 사유 1줄 안내 + 재입력. **차단 규칙 본문은 여전히 orchestrator SSOT** — UI 거부는 미러 (P-VENDOR 회피, predicate 단일 진실원).

`Path.resolve()`로 symlink + 상대경로 해소 → `workdir`이 항상 절대 정규 경로. `meta.workdir = str(workdir)` 박힘 (재현성).

### Layer 4: 쓰기 경계 — search-replace patch FILE 경로 검증 (ADR-10)

driver 응답의 `FILE: <path>` 헤더를 search-replace 블록과 함께 추출해 orchestrator가 workdir 파일을 수정한다. driver가 `FILE: ../etc/passwd` 또는 `FILE: /tmp/foo` 같은 외부 경로를 지정하면 cwd 격리(읽기 경계)를 우회해 임의 파일에 쓰기 가능 — 이를 차단:

```python
# spec
def validate_patch_path(workdir: Path, file: str) -> Path:
    """FILE 경로를 workdir 내부로 정규화 + 외부 차단.

    1. Path(workdir).resolve() / Path(file)로 결합 후 .resolve()
    2. resolved.is_relative_to(workdir.resolve())로 prefix 검사
    3. symlink escape도 strict=False resolve 후 동일 검사
    """
```

R2.6 `apply_patches` 진입 직전 모든 patch의 FILE 경로를 본 함수로 검증. 1개라도 외부면 즉시 `apply_status=failed, apply_error="path outside workdir: <file>"` 기록 (all-or-nothing 트랜잭션). symlink escape는 `Path.resolve(strict=False)` 후 동일 prefix 검사.

**정통 코드 위치**: `src/patch_apply.py::validate_patch_path` (시그니처 1:1) — 본 spec과 일관 검증은 `tests/test_patch_apply.py::test_validate_patch_path_ssot` + `test_apply_path_traversal_blocked`. 모듈 narrative 전체는 [`patch-apply.md`](patch-apply.md).

→ `outline/02-communication.md` §2.3 R2.6 노드 텍스트, §2.8 실패 모드 표 "Patch FILE 경로 workdir 외부" 행, `protocol.md` §4 R2.6 + §9와 1:1 일치.

### Layer 3: 어댑터 옵션으로 cwd 자동 로드 보강

| 어댑터 | 옵션 | 효과 |
|---|---|---|
| codex | `--ephemeral` | 세션 디스크 저장 비활성 → cwd 격리 보강 (cwd CLAUDE.md 자동 로드는 차단 X이지만 disk artifact 0) |
| codex | `--ignore-rules` | cwd `.rules` 무시 (외부 영향 차단) |
| claude | `--bare` (미사용) | OAuth/keychain 거부 명세라 미채택. Day 4 ADR-9 후보 — `disable_bare` 토글로 API key 사용자 대상 2층 방어선 추가 검토 |
| claude | (cwd CLAUDE.md auto-load) | OS 차원 cwd 격리만 의존 |

## 검증 (2단)

### 단위 테스트 (1차 안전망 — `tests/test_cwd_isolation.py`)

```python
def test_codex_runner_passes_workdir_not_repo_root(monkeypatch, tmp_path):
    # subprocess.run mock하여 cmd_list + cwd 인자 단언
    # called["cwd"] == tmp_path
    # called["cwd"] != Path.cwd()
    # called.get("shell", False) is False
    # "--ephemeral" in called["cmd"]

def test_claude_runner_passes_workdir(...):
    # 동일 패턴 + "--bare" not in cmd, "--append-system-prompt" not in cmd

def test_run_session_rejects_repo_root_workdir():
    # workdir = repo_root → SystemExit(match="ADR-6")
```

### 통합 테스트 (보강 — `tests/test_cwd_isolation_integration.py`)

`@pytest.mark.integration` 마커 (default skip — `pytest -q` 시 자동 제외).

```python
@pytest.mark.integration
def test_cwd_isolation_adr6(tmp_path):
    repo_sentinel = repo_root / "CLAUDE.md.test-marker"
    repo_sentinel.write_text("REPO-SENTINEL-MUST-NOT-LEAK", encoding="utf-8")  # R-001
    tmp_claude = tmp_path / "CLAUDE.md"
    tmp_claude.write_text("TMP-MARKER: ...", encoding="utf-8")  # R-001
    try:
        resp = ClaudeRunner().run("...", workdir=tmp_path, ...)
        text_blob = resp.text + raw.read_text(encoding="utf-8")  # R-001
        assert "REPO-SENTINEL-MUST-NOT-LEAK" not in text_blob   # 강제 단언
        # TMP-MARKER 등장은 soft 관찰 (claude auto-load 정책 의존)
    finally:
        repo_sentinel.unlink(missing_ok=True)
```

**시나리오 차별력 narrative**: repo 루트 sentinel은 cwd 밖이라 strict 단언이 catch 능력 약함 — 단위 테스트가 1차 안전망. Day 3+ mock 어댑터 도입 시 사전 녹음 JSONL에 marker 포함시켜 deterministic 검증 가능.

`.gitignore`에 `CLAUDE.md.test-marker` 등재 — 시나리오 도중 잔존 시 워킹트리 깨끗 보장.

## 변경 시 갱신 영향

| 코드 변경 | 갱신 대상 |
|---|---|
| 새 어댑터 추가 (mock 등) | 본 §Layer 1 표 + 본 §Layer 3 옵션 표 + `tests/test_cwd_isolation.py` 신규 어댑터 단언 |
| `run_session` workdir 검증 변경 | 본 §Layer 2 + `orchestrator.md` §run_session + `tests/test_cwd_isolation.py::test_run_session_rejects_repo_root_workdir` |
| `is_under_repo_root` predicate 변경 (모듈 top SSOT) | 본 §Layer 2 + `orchestrator.md` 헬퍼 표 + `cli.py::_input_workdir` 거부 분기 + `tests/test_interactive_menu_expansion.py::test_input_workdir_*_rejected` 4건 |
| `_resolve_workdir` 우선순위 표 변경 (env 키, default 경로) | 본 §Layer 2 우선순위 박스 + `orchestrator.md` `_resolve_workdir` + `runtime-docs/systems/run-mode.md §1 --workdir 행` + `tests/test_workdir_default.py` 5건 단언 + `README.md` 5초 데모·CLI 옵션 표 |
| ADR-9 `disable_bare` 토글 도입 (Day 4) | 본 §Layer 3 claude 행 + `agents.md` ClaudeRunner cmd_list + `architecture.md` ADR-9 |
| 통합 시나리오 강화 (Day 3+ mock 활용) | 본 §검증 + `phase-d-tests.md` (또는 후속 plan) |

## 관련 문서

- `architecture.md` ADR-6 (cwd 격리 결정)
- `outline/01-harness-layers.md §1.3` (두 층 분리 narrative)
- `protocol.md §7` (cwd 격리 mermaid)
- `agents.md` (어댑터 cmd_list + cwd= 명시)
- `orchestrator.md` (run_session repo-root 차단)
- `validation.md` P-CWD / P-LEAK
