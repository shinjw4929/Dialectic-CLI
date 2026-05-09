# Phase A · `dialectic logs` 서브커맨드 — 010-observability

## 0. 메타

- Phase ID: A
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A·B·C 모두 의존성 0 — execute-plan 동시 분기 후보
- 예상 LOC: ~60 LOC + 테스트 ~30 LOC

## 1. 목표

`dialectic logs` 서브커맨드를 신설해 `<workdir>/<UTC-ts>/messages.jsonl`(plan 011 Bug 2 fix 산출 구조)을 도구 1차 인터페이스로 노출. 사용자가 `cat | jq` 직접 호출 없이 turn/seq/kind 1줄 요약 + 본문 펼침을 지원받음. 같은 workdir 내 N session 자동/명시 선택.

## 2. 입력

- `outline/03-ux.md §3.4` (line 290-336) — 종료 시 산출물 구조 SSOT (`<workdir>/<UTC-ts>/messages.jsonl` + sessions/* + SYNTHESIS.md). plan 011 Bug 2 fix 반영 완료
- `outline/03-ux.md §3.5` (line 339-376) — Q3 narrative SSOT (color·kind label·flag 명세)
- `docs/runtime-docs/protocol.md §2` — 메시지 스키마 (`turn_id / seq_in_turn / kind / from / slot / content / meta`)
- `src/orchestrator.py:662-666` — session_dir 생성 SSOT (`session_ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")` + `Bus(session_dir / "messages.jsonl")`)
- `src/schema.py:Message` — dataclass 필드 정본
- `src/bus.py:Bus.read_all()` — JSONL 읽기 패턴 (malformed line skip 정책)
- `src/cli.py` argparse main() (현재 `:50-90`, plan 011 진행 후 추가 drift 가능 — execute 진입 시 `grep -n "subs.add_parser" src/cli.py`로 재확인)
- 사전 검증된 사실: 본 plan 시점 `src/cli.py`에 `logs` subparser 0건 (`grep -n "logs" src/cli.py` 0)
- 본 plan 1차 범위 = 6 flag(`--workdir / --session / --tail / --follow / --kind / --full`). `--turn / --since / --summary / --run`은 후속 plan deferred

## 3. 출력

### 3.1 신규 파일

- `src/logs.py` (신규, ~50 LOC)
  ```python
  # spec
  _SESSION_TS_PATTERN = r"^\d{8}T\d{6}Z$"  # %Y%m%dT%H%M%SZ

  def find_latest_session_dir() -> Path | None:
      """2-tier 자동 탐색: base_dir → 최신 workdir → 최신 session.

      base_dir 결정 우선순위 (phase-c §1 표 SSOT 인용):
        DIALECTIC_RUNS_DIR env > XDG_DATA_HOME/dialectic/runs >
        ~/.local/share/dialectic/runs.
      **첫 매칭 base_dir 한 곳**만 검사 (합집합 X).

      탐색 절차:
        1. base_dir 미존재/빈 → None
        2. base_dir 직속 자식 폴더 mtime 최대 → workdir_dir
        3. workdir_dir 직속 자식 중 _SESSION_TS_PATTERN 매칭 폴더 mtime 최대 → session_dir
        4. session_dir/messages.jsonl 존재 시 session_dir 반환, 아니면 None
      반환: <base>/<workdir-id>/<UTC-ts>/ 폴더 (messages.jsonl 포함).
      """

  def resolve_session_dir(user_workdir: Path) -> Path | None:
      """사용자 명시 --workdir 인자 해석 — workdir level 또는 session_dir 직접 지정 둘 다 수용.

      절차:
        1. user_workdir/messages.jsonl 존재 시 user_workdir 자체가 session_dir → 그대로 반환
        2. 없으면 user_workdir 직속 자식 중 _SESSION_TS_PATTERN 매칭 폴더 mtime 최대 → session_dir
        3. 매칭 폴더 0 → None (사용자에게 stderr 안내)
      """

  def format_summary(msg: dict) -> str:
      """1줄 요약: [turn=N seq=M] kind=... from=... slot=...
      slot=None은 'slot=-' 출력. content는 포함 X.
      """

  def format_full(msg: dict) -> str:
      """본문 펼침: format_summary(msg) + '\\n' + msg['content']. 끝에 '---' 구분자 1줄.
      content가 멀티라인이면 그대로 출력 (truncate X).
      """

  def render_logs(*, session_dir: Path, tail: int | None, follow: bool,
                  kind_filter: str | None, full: bool) -> int:
      """session_dir/messages.jsonl(`outline/03-ux.md §3.4 SSOT`)에서 JSONL 한 줄씩 읽어 stdout 출력.
      - kind_filter 지정 시 msg.kind != filter는 skip.
      - tail N 지정 시 마지막 N개만 출력 (line 수 < N도 안전).
      - full=True면 format_full, 아니면 format_summary 사용.
      - follow=True면 EOF 도달 후 0.5s 폴링하며 새 line append 시 추가 출력.
        KeyboardInterrupt 시 stdout flush 후 return 0.
      - malformed JSONL line은 stderr 1줄 경고 (`bus.py:Bus.read_all` 정책 정합) + skip.
      - session_dir/messages.jsonl 미존재 시 stderr 경고 + return 1.
      반환: exit code (0 = 정상, 1 = 파일 미발견 또는 읽기 실패).
      """
  ```

### 3.2 변경 파일

- `src/cli.py` argparse main()(현재 `:50-90`, 011 후 추가 drift) — `logs` subparser 추가 (`p_run`, `p_doc` 패턴 일관)
  - `--workdir <path>` (default = None → 호출 시 `find_latest_session_dir()` 위임). path는 workdir level 또는 session_dir 직접 지정 둘 다 수용
  - `--session <ts>` (str, default = None → `--workdir`가 workdir level일 때만 의미. 명시 시 `<workdir>/<ts>/`로 직접 지정. session_ts 형식 `%Y%m%dT%H%M%SZ`)
  - `--tail N` (`type=int`, default = None → 전체)
  - `--follow` (`action="store_true"`)
  - `--kind <name>` (str, dest=`kind`, default = None → 전체)
  - `--full` (`action="store_true"`, default = False → 1줄 요약)
  - argparse Namespace → `render_logs` kwarg 매핑 (`set_defaults(func=...)`):
    ```python
    # spec
    def _logs_entry(args: argparse.Namespace) -> int:
        if args.workdir is None:
            session_dir = find_latest_session_dir()
            if session_dir is None:
                sys.stderr.write("[logs] 마지막 세션 미발견 — --workdir로 지정\n")
                return 1
        else:
            user_path = Path(args.workdir).resolve()
            if args.session:
                session_dir = user_path / args.session
                if not (session_dir / "messages.jsonl").exists():
                    sys.stderr.write(f"[logs] {session_dir}/messages.jsonl 미존재\n")
                    return 1
            else:
                session_dir = resolve_session_dir(user_path)
                if session_dir is None:
                    sys.stderr.write(f"[logs] {user_path} 하위 session 미발견 (workdir 자체에 messages.jsonl 없음)\n")
                    return 1
        return render_logs(
            session_dir=session_dir, tail=args.tail, follow=args.follow,
            kind_filter=args.kind, full=args.full,
        )
    p_logs.set_defaults(func=_logs_entry)
    ```

### 3.3 신규 테스트

- `tests/test_logs.py` (신규, ~30 LOC)
  - `format_summary` 정상 + `slot=None` (`slot=-` 표기) 케이스
  - `format_full` — 본문 멀티라인 보존 + 구분자 출력
  - `render_logs(--tail 3)` — 마지막 3 line만 출력
  - `render_logs(--kind critique --full)` — kind 필터 + 본문 펼침
  - malformed JSONL skip + stderr 경고 단언
  - `find_latest_session_dir` — 2-tier 탐색 (`tmp_path` mock에 `<base>/<workdir-id>/<UTC-ts>/messages.jsonl` 구조 모사 + `DIALECTIC_RUNS_DIR` override 우선)
  - `resolve_session_dir` — workdir level 입력 시 자식 session 자동 선택 / session_dir 직접 입력 시 그대로 반환 / 자식 0 시 None
  - `_logs_entry --workdir <wd> --session <ts>` 명시 지정 분기 + 미존재 ts exit 1 단언
  - `_logs_entry workdir 미존재` exit 1 단언

## 4. 작업 단위

- [ ] `src/logs.py` 생성, 위 5 함수(`find_latest_session_dir`/`resolve_session_dir`/`format_summary`/`format_full`/`render_logs`) 구현 (R-001 encoding 명시, `_SESSION_TS_PATTERN` 상수 정의)
- [ ] `src/cli.py`에 `logs` subparser 등록 + `_logs_entry` Namespace→kwarg 매핑 + `set_defaults(func=_logs_entry)`
- [ ] `tests/test_logs.py` 신규 테스트 9건 작성 (위 §3.3 sub-checkbox 그대로)
- [ ] `README.md` "사용 예시" 섹션에만 `dialectic logs --tail 10` + `dialectic logs --workdir <path> --session <UTC-ts>` 2줄 추가 (Phase C는 "결과 위치" 섹션 — 분담)
- [ ] `docs/dev-docs/Documentation-Checklist.md` §1.1 표에 `src/logs.py` → `outline/03-ux.md §3.4 + §3.5` 매핑 추가
- [ ] `outline/03-ux.md §3.5` 본 plan 1차 범위(6 flag) 명시 + 후속 deferred 한 줄

## 5. 검증

- `python -c "from src.logs import find_latest_session_dir, resolve_session_dir, format_summary, format_full, render_logs"` 성공
- `pytest tests/test_logs.py -q` pass
- 실 호출: `dialectic logs --tail 5` (자동 탐색) → exit 0
- 실 호출: `dialectic logs --workdir <wd>` (workdir level — 자식 session 자동 선택) → exit 0
- 실 호출: `dialectic logs --workdir <wd> --session 20260509T071838Z --full --kind critique` → 명시 session의 critique 본문 펼침
- 실 호출: `dialectic logs --workdir <wd>/<UTC-ts>` (session_dir 직접 지정) → exit 0

## 6. 엣지케이스 / 위험 (Phase 한정)

- **session_dir/messages.jsonl 미존재**: workdir은 있는데 자식 session 폴더 0 또는 빈 경우 → `_logs_entry`가 1 exit + stderr 안내 (workdir/session_ts 차이 명확화)
- **`--follow` 종료 신호**: KeyboardInterrupt 시 깔끔히 stdout flush + return 0. `try/except KeyboardInterrupt` 명시
- **`--tail N`이 line 수보다 큼**: 전체 출력 (음수 인덱스 자연 처리)
- **session_ts 1초 정밀도 collision**: 동일 workdir에서 1초 내 두 세션 시작 시 폴더명 동일 가능 — `src/orchestrator.py:662-666`이 mkdtemp 아닌 단순 `strftime` → 두 번째 호출이 이미 존재하는 폴더 사용 시 messages.jsonl 누적. 본 phase는 read 책임 — 누적 시 사용자 가시. plan 011 Bug 2 fix 시점 결정 (`mkdir(parents=True, exist_ok=True)`) 그대로 따름. 문서 narrative만 명시
- **base_dir 결정 알고리즘 = 첫 매칭 한 곳만**: `DIALECTIC_RUNS_DIR` 일시 set 후 unset → 이전 set 동안 만든 세션은 다음 호출에서 안 보임. 의도된 동작 — 합집합 검색은 사용자 혼란 ↑. 사용자가 명시 `--workdir` 직접 지정 권장
- **메뉴 단계 4 임의 입력 workdir 미커버 (plan 011 후행)**: 011 진행 후 `_interactive_menu_body` 단계 4에서 사용자가 base_dir 외 임의 경로(`/tmp/myproj` 등) 직접 입력 가능. 본 phase의 `find_latest_session_dir`은 base_dir 우선순위 한정 → 임의 입력 미발견. 사용자가 `dialectic logs --workdir <path>` 명시 지정 → `resolve_session_dir`이 자식 session 자동 선택. README 사용 예시에 cascade
- **malformed JSONL line**: `src/bus.py:Bus.read_all()` 동일 정책(skip + 경고) 따름. test_logs.py 단언
- **plan 011 메뉴 단계 5 후보 wiring**: 현재 plan 010 외. 본 plan은 CLI 노출까지
- **`--workdir <path>` 의미 중의성**: workdir level vs session_dir 둘 다 수용 — `messages.jsonl` 존재 여부로 자동 분기 (`resolve_session_dir`). 사용자가 의도한 layer를 명확히 알면 `--session` 명시 권장
