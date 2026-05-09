# Phase C · workdir default 변경 — 010-observability

## 0. 메타

- Phase ID: C
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A·B·C 모두 의존성 0 — execute-plan 동시 분기 후보
- 예상 LOC: ~40 LOC + 테스트 ~20 LOC

## 1. 목표

workdir default를 `/tmp/dialectic-XXXX`(`tempfile.mkdtemp(prefix="dialectic-")`)에서 XDG 준수 경로(`~/.local/share/dialectic/runs/<timestamp>-<short-id>/`)로 변경. ADR-6 차단 로직(repo 루트·하위 SystemExit)은 유지. 우선순위 표는 다음과 같이 명시 — `--workdir` CLI 인자 > `DIALECTIC_RUNS_DIR` env > `XDG_DATA_HOME/dialectic/runs/` > `~/.local/share/dialectic/runs/`.

## 2. 입력

- `src/orchestrator.py:604-625` (post-009) `run_session` workdir 해소 로직 SSOT — `:606-607` workdir 해소 + `:612-625` ADR-6 차단 (plan 009 산출 후 line drift 흡수, plan 011은 orchestrator.py 본체 미수정)
- `src/cli.py:57-61` — `--workdir` argparse help (default 변경 시 동기화). 011 진행 후 line drift 가능 — execute 진입 시 grep 재확인
- `src/cli.py:_interactive_menu_body` 단계 4 + `_input_workdir` helper (plan 011 산출, 010 진입 시점 활성) — 010 default 경로 변경 후 narrative cascade 점검 대상
- `docs/dev-docs/architecture.md:133` ADR-6 — cwd 격리 결정 SSOT
- `docs/dev-docs/systems/cwd-isolation.md` — ADR-6 detail SSOT
- `tests/test_cwd_isolation.py` + `tests/test_cwd_isolation_integration.py` — repo-root 차단 회귀 SSOT
- `docs/dev-docs/validation.md §3 C-010` — workdir cleanup default 정책 (이미 적재, 본 plan은 default 경로 결정만 갱신. 신규 §3 후보 환원은 commit 시점 결정)
- 사전 검증된 사실: XDG Base Directory Specification — `XDG_DATA_HOME` default = `~/.local/share`
- 사전 검증된 사실: `tempfile.mkdtemp(prefix=..., dir=base_dir)`는 `base_dir`이 미존재 시 FileNotFoundError → base_dir 사전 mkdir 필요

## 3. 출력

### 3.1 변경 파일

- `src/orchestrator.py:604-625` (post-009, 011 후 추가 drift 가능) — workdir 해소 분리:
  ```python
  # spec
  def _resolve_workdir(args: argparse.Namespace) -> Path:
      """우선순위: --workdir CLI > DIALECTIC_RUNS_DIR env > XDG_DATA_HOME/dialectic/runs > ~/.local/share/dialectic/runs.
      base_dir은 mkdir(parents=True, exist_ok=True). 폴더명 = <YYYYMMDD-HHMMSS>-<short-id>.
      반환은 절대 경로 (Path.resolve()). ADR-6 차단은 호출자(run_session) 책임 유지.
      """
      if args.workdir:
          return Path(args.workdir).resolve()
      runs_env = os.environ.get("DIALECTIC_RUNS_DIR")
      xdg = os.environ.get("XDG_DATA_HOME")
      if runs_env:
          base_dir = Path(runs_env)
      elif xdg:
          base_dir = Path(xdg) / "dialectic" / "runs"
      else:
          base_dir = Path.home() / ".local" / "share" / "dialectic" / "runs"
      base_dir.mkdir(parents=True, exist_ok=True)
      timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
      # mkdtemp suffix(8자 random)가 short-id 역할 — 폴더명 = "<timestamp>-<8char>"
      # (예: 20260509-120000-Ab3CdEfG). suffix 자체로 충돌 0 보장.
      return Path(tempfile.mkdtemp(prefix=f"{timestamp}-", dir=str(base_dir))).resolve()
  ```
- `run_session` (현재 `:606-607`) — 위 헬퍼 호출로 교체:
  ```python
  # spec
  workdir = _resolve_workdir(args)
  ```
- `src/cli.py:57-61` — `--workdir` help 텍스트 갱신:
  ```
  "작업 디렉토리. 미지정 시 ~/.local/share/dialectic/runs/<timestamp-id>/ 자동 생성. "
  "DIALECTIC_RUNS_DIR / XDG_DATA_HOME 환경변수로 base_dir 변경 가능. "
  "Dialectic-CLI repo 루트는 ADR-6에 의해 사용 불가."
  ```

### 3.2 신규 테스트

- `tests/test_workdir_default.py` (신규, ~20 LOC)
  - default(env 미설정) 시 workdir parent = `~/.local/share/dialectic/runs/`
  - `DIALECTIC_RUNS_DIR=/tmp/custom_dialectic_runs` 시 workdir parent = `/tmp/custom_dialectic_runs/`
  - `XDG_DATA_HOME=/tmp/xdg` 시 workdir parent = `/tmp/xdg/dialectic/runs/` (DIALECTIC_RUNS_DIR 미설정 케이스)
  - `--workdir <abs>` 명시 시 위 우선순위 모두 무시
  - `DIALECTIC_RUNS_DIR=<repo>/runs` 시 ADR-6 SystemExit (회귀 차단 — 기존 `test_cwd_isolation.py`는 repo-root 직접 지정만 cover)

## 4. 작업 단위

- [ ] `src/orchestrator.py`에 `_resolve_workdir` 헬퍼 추가 (`datetime`, `os` import 필요 시 추가)
- [ ] `run_session` (post-009 `:606-607`, 011 후 추가 drift 가능 — execute 진입 시 grep `tempfile.mkdtemp.*dialectic`로 재확정) 호출 교체
- [ ] `src/cli.py:57-61` (post-009, 011 후 drift 가능) help 텍스트 갱신
- [ ] `tests/test_workdir_default.py` 5건 신규 단언
- [ ] `docs/dev-docs/systems/orchestrator.md` workdir 해소 narrative 갱신 (우선순위 표 SSOT)
- [ ] `docs/runtime-docs/systems/run-mode.md` "결과 위치" 단락 갱신 (`/tmp/...` → `~/.local/share/dialectic/runs/...`)
- [ ] `docs/dev-docs/systems/cwd-isolation.md` "default 경로" 단락 추가 + ADR-6 차단이 base_dir이 repo 하위인 경우도 cover함을 명시
- [ ] `README.md` "결과 위치" 섹션에만 default 경로 + `DIALECTIC_RUNS_DIR`/`XDG_DATA_HOME` 안내 갱신 (Phase A는 "사용 예시" 섹션 — README 수정 영역 분담, 01-plan §5 참조)
- [ ] `docs/dev-docs/Documentation-Checklist.md` §1.1 표에 `src/orchestrator.py:_resolve_workdir` → `docs/dev-docs/systems/orchestrator.md` + `docs/dev-docs/systems/cwd-isolation.md` 매핑 보강 (workdir 해소 책임 추가)
- [ ] (plan 011 cascade) `src/cli.py` 메뉴 단계 4 narrative + `_input_workdir` helper docstring 점검 — "자동 생성(orchestrator default)" 라벨이 변경된 default 경로(`~/.local/share/dialectic/runs/`)와 일관한지 확인. 011이 추상 표현 사용 시 갱신 0, 구체 경로 박힘 시 정정
- [ ] (메모) Phase C 종료 시점에 default 경로 결정 narrative(4 후보 `/tmp` / `/mnt/c` / repo 하위 / XDG 비교)를 commit 메시지 또는 sync-docs 산출에 보존 — `validation.md §3` 신규 후보 환원 여부·P-id는 commit 시점에 §3 최신 ID로 결정 (본 작업 단위는 메모만, 환원 자체는 작업 단위 외)

## 5. 검증

- `pytest tests/test_workdir_default.py tests/test_cwd_isolation.py tests/test_cwd_isolation_integration.py -q` 모두 pass (회귀 0)
- 단위 호출 (1차 — 인증·token 비용 0): `python -c "from src.orchestrator import _resolve_workdir; import argparse; print(_resolve_workdir(argparse.Namespace(workdir=None)))"` → `~/.local/share/dialectic/runs/<...>` 경로 출력
- 단위 호출: `DIALECTIC_RUNS_DIR=/tmp/test_runs python -c "..."` → `/tmp/test_runs/` 하위 경로
- 단위 호출: `DIALECTIC_RUNS_DIR=<repo-root>/runs dialectic run --task "test"` → SystemExit (ADR-6 차단). 실 호출 형태로 ADR-6 SystemExit가 호출자 책임에서 발생함을 검증
- 실 호출 (선택, 인증 + token 비용 발생): `dialectic run --task "test" --max-turns 1` (default 매핑 codex→claude) 후 stderr "workdir 보존: ~/.local/share/dialectic/runs/..." 확인

## 6. 엣지케이스 / 위험 (Phase 한정)

- **base_dir 미존재**: `mkdir(parents=True, exist_ok=True)`로 사전 생성 필수. 미생성 시 `tempfile.mkdtemp(dir=...)` FileNotFoundError
- **`DIALECTIC_RUNS_DIR` 빈 문자열 vs 미설정**: `os.environ.get("DIALECTIC_RUNS_DIR")` 빈 문자열은 falsy → 자연 fallback. 명시적 빈 값을 ignore함을 docstring에 명시
- **`/mnt/c` (WSL Windows mount) 후보 기각 근거 명시**: 본 plan 결정 (memory `project_plan_010_workdir_default.md`) — `/mnt/c`는 권한·case-sensitivity 결함, repo 하위는 ADR-6, `/tmp`는 접근성. XDG가 4 후보 중 유일하게 안전·표준
- **timestamp collision**: 1초 내 두 세션 시작 시 `tempfile.mkdtemp` suffix(short-id)가 unique 보장
- **windows native path**: 본 도구 WSL/Linux 가정 (CLAUDE.md). Windows native 미지원 — 별도 branch로 deferred
- **workdir auto-cleanup 정책**: 변경 X (validation.md §3 C-010 적재됨 — `cleanup=False` default). 누적 정리는 사용자 책임 (workdir 안내 stderr 메시지 그대로)
- **logs 자동 탐색(Phase A)과 base_dir 동기화**: Phase A `find_latest_session_dir`이 같은 우선순위 표(§1) 인용 — base_dir 위치 변경 시 두 phase 동시 수정. 본 plan §5 횡단 위험에도 명시
