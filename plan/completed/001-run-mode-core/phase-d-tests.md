# Phase D · Tests + Documentation cross-check — 001-run-mode-core

## 0. 메타

- Phase ID: **D**
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: C (전체 코드 의존)
- 병렬 그룹: —
- 예상 LOC: ~165 (test 5파일 + integration 1 시나리오 + protocol.md §2/§4/§8/§10 갱신 + code-conventions.md §5 갱신(`:94`+`:114`) + architecture.md ADR-6/-9 한 줄 보강 + README 갱신 + pyproject.toml markers 1종 + .gitignore 한 줄. test 5파일 = 기존 4 + `tests/test_orchestrator_converge.py` (신규 ~25 LOC, [CONVERGED] 감지 + ADR-9 fallback warning 검증). conftest.py + 시나리오 B + `requires_anthropic_api_key` 마커 모두 제거 −30)

## 1. 목표

단위 테스트 4종 + 통합 테스트 1종 + protocol.md §10·README 갱신. ADR-6(cwd 격리)을 monkeypatch(어댑터가 cwd 전달했는지) + integration(실 호출 시 더미 마커 누수 0) 2단 검증.

## 2. 입력

- Phase A·B·C 산출물 전체.
- `docs/dev-docs/code-conventions.md` §9 (`:153-162`, 테스트 — 단위는 mock subprocess, integration은 `pytest -m integration` 별도).
- `docs/runtime-docs/protocol.md` 갱신 위치 (모아서):
  - §2 (`:52-194`) — Meta dataclass JSONC `:78` 근처 (cached_input_tokens 위치) + classDiagram **Meta 블록 `:132-145`** (Message는 :117-130 — 혼동 차단) + msg_id 예시 `:59`
  - §4 (`:212-231`) — 라이프사이클 mermaid R4 노드 `:221`
  - §8 (`:302-326`) — `meta: dict→Meta` `:310` + claude cmd_list `:320` + codex cmd_list `:319`
  - §10 (`:342-355`) — codex `--ephemeral` 추가, claude `--bare` 미사용 명시·`--append-system-prompt` 제거
- `docs/dev-docs/code-conventions.md` 갱신 위치: §5 (`:81-119`) — `:94` `meta: dict→Meta` + `:114` 본문 정정.
- `docs/dev-docs/architecture.md` ADR-6 (`:133`) 한 줄 보강.
- `docs/dev-docs/Documentation-Checklist.md` §1.1·§1.2 (sync-docs cross-check 기준).
- `outline/01-harness-layers.md` §1.3 (`:30-61`, cwd 격리 단위 테스트 명세).

## 3. 출력

### 3.1 `tests/test_schema.py` (신규, ~18 LOC)

- `Message` round-trip — 모든 필드 채운 인스턴스 → `to_dict()` → `json.dumps` → `json.loads` → `from_dict()` 동치.
- `from` 키 ↔ `from_` 필드 변환 검증.
- `Meta` 필드 14개 모두 round-trip (`reasoning_output_tokens` + `convergence_streak` 포함).
- **`ts` 형식 정규식 검증** — 생성된 `ts` 문자열이 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$` 매치 (protocol.md §2 line 92 명세). Z 접미사 + 밀리초 3자리 강제. naive `datetime.now()` 또는 단순 `isoformat()` 사용 시 매치 실패로 catch.

### 3.2 `tests/test_bus_append.py` (신규, ~22 LOC)

- 같은 `Message` 두 번 `append` → `read_all()` len == 2.
- `Bus` 클래스에 `update`/`delete`/`truncate` 메서드 부재 검증 (`hasattr` reflection).
- 두 번째 `Bus(path)` 생성해 `append` → 기존 라인 보존 + 새 라인 추가.

### 3.3 `tests/test_cwd_isolation.py` (신규, ~30 LOC, 단위)

- `monkeypatch`로 `subprocess.run`을 캡처. 핵심: `cmd`는 positional 인자라 별도 저장:
  ```python
  def test_codex_runner_passes_workdir_not_repo_root(monkeypatch, tmp_path):
      called = {}
      def fake_run(cmd, *args, **kw):
          called["cmd"] = cmd                       # positional 첫 인자 명시 저장
          called.update(kw)                          # cwd / timeout / env / check 등
          return SimpleNamespace(
              stdout='{"type":"thread.started","thread_id":"t-x"}\n'
                     '{"type":"item.completed","item":{"type":"agent_message","text":"x"}}\n'
                     '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1,"cached_input_tokens":0,"reasoning_output_tokens":0}}\n',
              stderr="", returncode=0,
          )
      monkeypatch.setattr(subprocess, "run", fake_run)
      CodexRunner().run("p", raw_log_path=tmp_path/"r.jsonl", timeout_s=10, workdir=tmp_path)
      assert called["cwd"] == tmp_path
      assert called["cwd"] != Path.cwd()             # repo 루트가 아님
      assert called.get("shell", False) is False     # shell=True 부재
      assert "--ephemeral" in called["cmd"]          # cmd_list에 옵션 포함
      assert "--sandbox" in called["cmd"] and "read-only" in called["cmd"]
  ```
- 동일 패턴으로 `ClaudeRunner` — `--tools`/`--no-session-persistence`/`--max-budget-usd`/`--output-format json` 모두 단언. **`--append-system-prompt` 부재 단언**: `assert "--append-system-prompt" not in called["cmd"]` (4섹션 prompt를 stdin으로 전달하는 본 plan 결정과 일관 검증). **`--bare` 부재 단언**: `assert "--bare" not in called["cmd"]` (OAuth 호환 결정과 일관 검증).
- **`--workdir <repo 루트>` 차단 검증** (`test_run_session_rejects_repo_root_workdir`) — ADR-6 사용자 입력 우회 차단:
  ```python
  def test_run_session_rejects_repo_root_workdir():
      from src.orchestrator import run_session
      from types import SimpleNamespace
      repo_root = Path(__file__).resolve().parent.parent
      args = SimpleNamespace(workdir=str(repo_root), task="x",
                             driver="codex", reviewer="claude", max_turns=1, mode="run")
      with pytest.raises(SystemExit, match="ADR-6"):
          run_session(args)
  ```
  `run_session()`이 어댑터 호출 전에 검증으로 SystemExit raise — subprocess monkeypatch 불필요.

### 3.3b `tests/test_orchestrator_converge.py` (신규, ~25 LOC, 단위)

outline/02 §2.9 `[CONVERGED]` 메커니즘 + ADR-9 fallback 단위 검증. 본 plan DoD `00-plan.md §6:170` 약속 충족.

```python
# spec
def test_detect_converged_marker_alone_last_line():
    from src.orchestrator import _detect_converged
    assert _detect_converged("Some critique\n[CONVERGED]") is True
    assert _detect_converged("Some critique\n[CONVERGED]\n") is True       # trailing newline OK
    assert _detect_converged("Some critique\n[CONVERGED]  \n") is True     # trailing whitespace OK

def test_detect_converged_marker_not_alone():
    from src.orchestrator import _detect_converged
    assert _detect_converged("[CONVERGED] yes") is False                   # 마커 + 추가 텍스트
    assert _detect_converged("Some critique [CONVERGED]") is False         # 같은 줄 내 prefix
    assert _detect_converged("[CONVERGED]\nP1: ...") is False              # 마지막 줄 아님

def test_detect_converged_no_marker():
    from src.orchestrator import _detect_converged
    assert _detect_converged("") is False
    assert _detect_converged("Some critique without marker") is False

def test_run_session_adr9_fallback_warning(monkeypatch, capsys, tmp_path):
    """--max-turns 1 + --convergence-streak 2 → stderr 'K reduced to 1' 등장."""
    # subprocess.run을 mock으로 바꿔 driver/reviewer 호출은 실 호출 X (cwd 격리 단위 패턴 재사용).
    # K=2, max_turns=1 → fallback 발동.
    ...
    captured = capsys.readouterr()
    assert "K reduced to 1" in captured.err
    assert "ADR-9" in captured.err

def test_run_session_adr9_no_fallback_when_K_eq_1(monkeypatch, capsys, tmp_path):
    """--max-turns 1 + --convergence-streak 1 → fallback skip (K > 1 가드). stderr 메시지 부재."""
    ...
    captured = capsys.readouterr()
    assert "K reduced to 1" not in captured.err
```

### 3.4 `tests/test_cwd_isolation_integration.py` (신규, ~25 LOC, **integration**)

- `pytest.mark.integration` 마커. `pytest -q`에서는 skip, `pytest -m integration`에서만 실행.
- 본 plan은 `--bare` 미사용 결정 — cwd 격리(OS 차원) 단독 검증.
- claude만 검증 (codex 통합 가능하지만 시간·비용 효율로 claude 1회 — Max OAuth 환경 비용 0).

#### 시나리오 — cwd 격리 단독 검증 (ADR-6)

Dialectic-CLI repo 루트에 마커 작성한 상태에서 별도 임시 dir을 `workdir`로 호출 → `subprocess.run(cwd=tmp_path)`가 repo 루트가 아닌 임시 dir로 진입 → repo 루트의 마커가 prompt에 흘러들어가지 않음.

```python
@pytest.mark.integration
def test_cwd_isolation_adr6(tmp_path):
    """ADR-6 진정 검증 — '격리'와 'cwd 따라감' 두 명제 동시 검증.

    설정:
      - tmp_path/CLAUDE.md (TMP-MARKER)  : claude가 cwd=tmp_path를 따라가면 자동 로드 가능
      - repo_root/CLAUDE.md.test-marker (REPO-SENTINEL) : cwd 밖 — 격리되면 누수 X

    강제 단언 (격리):
      raw stream에 REPO-SENTINEL-MUST-NOT-LEAK 부재 — 본 단언이 ADR-6 핵심.

    관찰 보강 (cwd 따라감):
      tmp_path CLAUDE.md 자동 로드 여부는 claude CLI 동작에 따름 — 강제 단언 X.
      cwd 인자 전달 검증은 monkeypatch 단위 테스트(§3.3)가 보완.
    """
    repo_root = Path(__file__).resolve().parent.parent
    repo_sentinel = repo_root / "CLAUDE.md.test-marker"
    repo_sentinel.write_text("REPO-SENTINEL-MUST-NOT-LEAK")

    tmp_claude = tmp_path / "CLAUDE.md"
    tmp_claude.write_text("TMP-MARKER: cwd가 tmp_path를 따른다면 claude 자동 로드 가능.")

    try:
        raw = tmp_path / "raw.jsonl"
        resp = ClaudeRunner().run(
            "응답 본문에 'CLAUDE.md를 자동 로드했다면 그 안의 MARKER 키워드를 그대로 반복하라' 지시 포함",
            raw_log_path=raw, timeout_s=60, workdir=tmp_path,
        )
        text_blob = resp.text + raw.read_text()
        # 강제 단언 (격리): repo 루트 sentinel은 cwd 밖이라 어떤 cwd 설정에서도 등장 X — 차별력 약함
        assert "REPO-SENTINEL-MUST-NOT-LEAK" not in text_blob, (
            "repo 루트 sentinel이 prompt에 누수됨 — ADR-6 위반"
        )
        # 차별력 보강 (cwd 따라감 관찰 — claude 동작 의존이라 soft):
        # claude가 cwd CLAUDE.md를 자동 로드하면 TMP-MARKER 등장 → cwd가 tmp_path 따라감 확인.
        # 자동 로드 안 하면 미등장 — false negative 아닌 정상 (claude 정책 차이). 1차 안전망은
        # monkeypatch 단위 테스트(§3.3 cwd=workdir 인자 단언). 본 통합은 부가 검증.
        cwd_followed = "TMP-MARKER" in text_blob
        print(f"[ADR-6 cwd 따라감 관찰]: TMP-MARKER {'등장 ✓' if cwd_followed else '미등장 (claude auto-load 정책 차이 가능)'}")
    finally:
        repo_sentinel.unlink(missing_ok=True)
```

> **시나리오 차별력 narrative**: 본 시나리오의 강제 단언(`REPO-SENTINEL not in`)은 repo 루트 sentinel이 어떤 cwd에서도 자동 로드 대상 아니라 cwd 위반 catch 능력 약함 (직전 review-plan 지적). 진정한 ADR-6 위반(repo 루트 = cwd) catch는 (a) repo의 실제 CLAUDE.md에 sentinel 임시 주입(유지보수자 워킹트리 invasive — 본 plan 미채택) 또는 (b) cwd 따라감 직접 단언(claude `--bare` 미사용 + cwd CLAUDE.md auto-load 의존, false positive 위험)이 필요. **Day 2는 monkeypatch 단위 테스트(§3.3 `cwd=workdir` 인자 단언 + `test_run_session_rejects_repo_root_workdir`)를 1차 안전망으로 채택, 통합은 부가 관찰만**. Day 3+ mock 어댑터 도입 시 사전 녹음 JSONL에 marker 포함시켜 deterministic 검증 가능 + Day 4 ADR-9(`disable_bare` 토글)로 2층 방어선 검증.

### 3.5 `docs/runtime-docs/protocol.md` 갱신 (3 부분 — Documentation-Checklist §1.1 어댑터 변경 sync)

> **명명 컨벤션 — letter suffix vs sub-numbering 혼재 해석**: 본 §3.x는 두 형식이 혼재 (sub-numbering `§3.5.1~§3.5.4` + letter suffix `§3.3b`/`§3.5b`/`§3.5c`). 의미상 동일 — 모두 부모 §의 sub-section. 작성 과정에서 점진적 추가된 흔적 (review-plan 라운드별 보강). 향후 plan 작성 시 sub-numbering 단일화 권장.

#### 3.5.1 §10 (호출 옵션) 갱신

- claude: 기존 `--tools "" --no-session-persistence --max-budget-usd 1.0` 그대로 + **`--append-system-prompt` 제거** — 4섹션 prompt 전체를 stdin으로 전달 (protocol.md §5와 일관). **`--bare` 미사용** 명시 한 줄 — OAuth/keychain 거부 명세 + Max 구독 무료 호출 우선, Day 4 ADR-9(`disable_bare` 토글) 후보로 deferred.
- codex: 기존 `--sandbox read-only --skip-git-repo-check --ignore-rules` + **`--ephemeral`** 추가 ("세션 디스크 저장 비활성, claude `--no-session-persistence` 대응").

#### 3.5.2 §8 (어댑터 인터페이스) 갱신 — `meta` 강타입화 + cmd_list 동기화

- `:310` `meta: dict` → `meta: Meta` (frozen dataclass, schema.Meta 재사용 — phase-a §3.3과 1:1).
- `:320` claude cmd_list 예시 갱신 — `--append-system-prompt` 제거 → `claude -p --tools "" --no-session-persistence --max-budget-usd 1.0 --output-format json` (`--bare` 미사용).
- `:319` codex cmd_list 예시 갱신 — `--ephemeral` 추가 → `codex exec --json --sandbox read-only --skip-git-repo-check --ignore-rules --ephemeral -`.

#### 3.5.3 §2 (메시지 스키마) 갱신 — `Meta` 필드 + 예시 + classDiagram 동기화

- **dataclass JSONC** (line 78 근처, `cached_input_tokens` 위치): `cached_input_tokens` 다음에 `"reasoning_output_tokens": 13` 한 줄 추가. 의미: codex turn.completed.usage 보고 값 보존, claude·mock은 0. **추가로 `workdir` 다음에 `"convergence_streak": null` 한 줄 (outline/02 §2.9) — reviewer [CONVERGED] streak 카운터, auto_end_converged 시 K, 그 외 null. default null이라 기존 메시지 영향 X.**
- **`msg_id` 예시 동기화** (line 59): `"t1-implementer"` → `"019dfd43-7a67-4a69-9d4b-..."`(uuid4 hex). plan schema가 `uuid.uuid4()`이므로 sequence 형식 예시 잔존 시 외부 독자 오해. `parent_id` 예시도 동일하게 uuid 형식으로 갱신.
- **classDiagram Meta 블록** (line **132-145** — line 117-130은 `class Message` 블록이라 오삽입 위험): 현재 protocol.md 12 필드 → 본 plan에서 `+2 → 14 필드`로 확장. `+int reasoning_output_tokens` 한 줄 추가 (line 140 `+int cached_input_tokens` 다음) + `+int? convergence_streak` 한 줄 추가 (`+string workdir` 다음, default null).

#### 3.5.4 §4 (한 턴 라이프사이클 mermaid) 갱신 — claude cmd_list 동기화

- line **221** `R4["**4.** subprocess: claude -p<br/>--append-system-prompt &lt;reviewer role.md&gt;<br/>..."]` → `R4["**4.** subprocess: claude -p<br/>(stdin: 4섹션 prompt)<br/>cwd = resolved_workdir<br/>..."]`로 갱신. `--append-system-prompt` 메커니즘 제거 (4섹션 prompt를 stdin 통째로 전달)에 따른 라이프사이클 다이어그램 동기화. `--bare` 미사용이라 mermaid에 추가 X.

### 3.5b `docs/dev-docs/code-conventions.md` §5 갱신 (어댑터 인터페이스) — `meta` 강타입화

- `:94` `AgentResponse.meta: dict` → `AgentResponse.meta: Meta` (frozen, schema.Meta 재사용).
- **`:114` 본문 정정** — `"AgentResponse.meta["error"]에 담아 반환"` → `"AgentResponse.text=""로 반환하고 raw stream에 stderr 보존. orchestrator가 if not resp.text 분기에서 _error_msg로 환원"`. `Meta` frozen dataclass에는 `error` 필드 없음 → 인덱싱 자체 불가능. 빈 응답·parse failure 책임은 어댑터에서 orchestrator로 이전 (phase-c §3.1 빈 응답 분기와 정합).
- 위반 사례에 "Meta dataclass 미사용 시 정직성·타입 안전성 손상" 한 줄 추가 (선택).

### 3.5c `docs/dev-docs/architecture.md` ADR-6 본문 보강 (한 줄)

- `:133` ADR-6 행에 보강 한 줄 — codex `--ephemeral`(세션 디스크 비활성)이 cwd 격리(OS 차원)와 함께 작동하는 보조 안전망임을 명시. claude `--bare`는 OAuth/keychain 거부 명세로 본 plan 미사용 — Day 4 ADR-9 후보로 `disable_bare` 토글 + API key 사용자 대상 2층 방어선 검증 deferred.

### 3.6 `README.md` 갱신

- status banner: "Day 1 — .md 하네스 28+ 파일 완료, 코드 미구현" → "Day 2 — run 모드 한 턴 E2E 동작".
- 5초 데모 명령:
  ```bash
  source .venv/bin/activate
  dialectic doctor                                     # 환경 점검
  dialectic run --task "Reply with single digit: 1+1=?" \
      --workdir /tmp/dialectic-demo --driver codex --reviewer claude --max-turns 1
  cat /tmp/dialectic-demo/logs/messages.jsonl          # 4 라인+
  ```
- 환경설정 섹션 신설/갱신 — `dialectic doctor` 실행 시 인증 누락 항목 안내, `claude auth` / `codex login` 링크. **`--workdir` 안내 한 줄** — "미지정 시 임시 dir 자동 생성. Dialectic-CLI repo 루트는 ADR-6에 의해 사용 불가" (사용자가 `--help`만 보고 시도→SystemExit 메시지에서야 발견하는 사용자 경험 차단).
- "현재 동작 모드" 섹션 한 줄 — "Day 2: `run` 모드만 정식 검증. `plan`/`implement`는 코드 활성이지만 인터랙티브 UI 부재 (Day 3 추가 후 데모)".

### 3.7 `pyproject.toml` (markers 1종)

- `[tool.pytest.ini_options]`에 추가:
  ```toml
  markers = ["integration: 실 API 호출 — 수동 'pytest -m integration'"]
  addopts = "-m 'not integration'"     # default skip — pytest -q 시 자동 제외
  ```
- 시나리오 A는 `@pytest.mark.integration` 부착. **`addopts = -m 'not integration'`로 default skip — `pytest -q` 시 unintended 실 호출(비용 발생) 차단**. 수동 호출 `pytest -m integration`은 marker filter를 override (pytest 표준 동작). claude OAuth 환경에서 정상 호출 가능 (Max 구독 무료 호출). `requires_anthropic_api_key` 마커·conftest skip 메커니즘은 본 plan 미사용 — `--bare` 미사용 결정으로 OAuth 호환성 확보됨.

### 3.8 `.gitignore` 한 줄 (sentinel 누수 차단)

- 시나리오 A는 repo 루트에 `CLAUDE.md.test-marker`를 일시 작성·즉시 unlink. test 도중 git status에 노출 또는 시그날 실패 시 잔존 가능 → `.gitignore`에 `CLAUDE.md.test-marker` 추가하여 사용자 워킹트리 깨끗 보장.

## 4. 작업 단위

- [ ] `tests/__init__.py` (빈 파일).
- [ ] `tests/test_schema.py` 작성 — `Message` round-trip + `from`↔`from_` 변환 검증.
- [ ] `tests/test_bus_append.py` 작성 — 두 번 append 라인 2개 + 수정 메서드 부재 reflection.
- [ ] `tests/test_cwd_isolation.py` 작성 (단위, monkeypatch) — codex/claude 둘 다, `cwd=workdir` 인자·`shell=False` 단언 + codex `--ephemeral` 포함 단언 + claude `--bare`/`--append-system-prompt` **부재** 단언 + **`test_run_session_rejects_repo_root_workdir`** (ADR-6 사용자 입력 우회 차단 검증).
- [ ] **`tests/test_orchestrator_converge.py` 작성** (단위, monkeypatch) — `_detect_converged()` 4 케이스(마커 단독 마지막 줄 / 마커 부재 / 마커 비단독 / 빈 문자열) + `run_session` ADR-9 fallback 2 케이스 (K=2·max-turns=1 → stderr `K reduced to 1` 단언, K=1·max-turns=1 → stderr 메시지 부재 단언). DoD `00-plan §6:170` 약속 충족.
- [ ] `tests/test_cwd_isolation_integration.py` 작성 (`@pytest.mark.integration`) — **시나리오 A** (`test_cwd_isolation_adr6`: repo 루트에 마커, workdir=tmp_path, cwd 격리 단독 검증). claude OAuth 환경에서 무료 호출.
- [ ] `pyproject.toml` `markers` 1종 + `addopts = -m 'not integration'` 추가 — `pytest -q` default skip + `pytest -m integration`으로 수동 override.
- [ ] `.gitignore`에 `CLAUDE.md.test-marker` 한 줄 추가 (시나리오 A sentinel 누수 차단).
- [ ] `docs/runtime-docs/protocol.md` §10 갱신 — claude `--append-system-prompt` 제거 + `--bare` 미사용 명시(Day 4 ADR-9 후보 deferred), codex `--ephemeral` 추가.
- [ ] `docs/runtime-docs/protocol.md` §8 갱신 — `meta: dict` → `meta: Meta` 강타입화, claude/codex cmd_list 예시 동기화.
- [ ] `docs/runtime-docs/protocol.md` §2 갱신 — `Meta` 필드 `reasoning_output_tokens: int` 추가 (dataclass JSONC + classDiagram 둘 다) + **`convergence_streak: int | None = None` 추가 (outline/02 §2.9, dataclass JSONC + classDiagram 둘 다)** + `msg_id`/`parent_id` 예시를 sequence("t1-implementer") → uuid4 hex로 갱신.
- [ ] `docs/runtime-docs/protocol.md` §4 라이프사이클 mermaid 갱신 — R4 노드 `--append-system-prompt` 제거 (4섹션 prompt를 stdin 통째 전달).
- [ ] `docs/dev-docs/code-conventions.md` §5 갱신 — `AgentResponse.meta: dict` → `meta: Meta` 강타입화 + `:114` 본문 정정 (`meta["error"]` 인덱싱 → `text=""` + orchestrator 분기 패턴).
- [ ] `docs/dev-docs/architecture.md` ADR-6 본문 한 줄 보강 — codex `--ephemeral`이 cwd 격리(OS 차원) 보조 안전망 명시. claude `--bare`는 OAuth 거부 명세로 본 plan 미사용 + Day 4 ADR-9 후보 한 줄.
- [ ] `README.md` 갱신 — status banner + 데모 명령 + `dialectic doctor` 안내 (환경설정 섹션).
- [ ] `pytest -q` 통과 (3 단위 테스트 + integration 1개는 skip — 합쳐도 모두 OK).
- [ ] `pytest -m integration` 통과 — 시나리오 A 1회 (수동). Max OAuth 환경 비용 $0.
- [ ] **Documentation-Checklist §1.1 매핑 cross-check** — 본 plan 변경 유형(`README.md` 환경설정 섹션, `pyproject.toml` `markers`+`addopts`, `.gitignore` sentinel 한 줄, `outline/05-timeline.md` Day 2 narrative)이 `docs/dev-docs/Documentation-Checklist.md` §1.1 매핑 표에 행으로 등재되어 있는지 grep 확인. 부재 시 행 추가 권고 — sync-docs 1차 catch.

## 5. 검증

- `pytest -q tests/test_schema.py tests/test_bus_append.py tests/test_cwd_isolation.py tests/test_orchestrator_converge.py` — 모두 pass.
- `pytest -q` (전체) — integration skip + 다른 테스트 모두 pass.
- `pytest -m integration` — `test_cwd_isolation_adr6` pass.
- `grep -E "(--ephemeral)" docs/runtime-docs/protocol.md` — §10에 추가된 codex 옵션 검출. claude `--bare` 미사용 명시 한 줄도 §10에 등장 검증.
- **schema ↔ protocol.md §2 1:1 grep 일치** — Phase D §3.5.3에서 protocol.md §2를 갱신한 뒤(`reasoning_output_tokens` + `convergence_streak` 추가), Message 12 필드(`from`/`to`/`msg_id`/`parent_id`/`turn_id`/`seq_in_turn`/`slot`/`mode`/`kind`/`content`/`directive`/`meta`) + Meta 14 필드(`vendor`/`agent_cli`/`model`/`session_id`/`thread_id`/`input_tokens`/`output_tokens`/`cached_input_tokens`/`reasoning_output_tokens`/`cost_usd`/`latency_ms`/`is_mock`/`workdir`/`convergence_streak`) 모두 양쪽에 정확히 등장 검증 (Phase A는 schema 단독 round-trip만, 1:1 검증은 본 phase 책임 — 의존 그래프 정합).
- `grep "Day 2" README.md` — status banner 갱신 검증.
- `grep -E "Day 2.*(E2E|run 모드|한 턴)" outline/05-timeline.md` — Day 2 narrative 갱신 검증 (DoD `00-plan.md §6` outline 항목). 갱신 X 결정 시 본 grep skip + commit message에 사유 명시 후 통과.
- `sync-docs` 호출 → Documentation-Checklist §1.1(`src/agents/codex.py` ↔ protocol.md §10, `src/agents/claude.py` ↔ §10, `src/orchestrator.py` ↔ §3·§4, `src/bus.py` ↔ §2, `src/schema.py` ↔ §2, `src/cli.py` ↔ README) 매핑 누락 0.
- `review-code` 호출 → 안전성·인터페이스·컨벤션 P0 = 0.

## 6. 엣지케이스 / 위험 (Phase 한정)

1. **monkeypatch 한계** — `subprocess.run`을 mock하면 어댑터가 cmd_list에 옵션을 박았는지·cwd를 전달했는지만 검증. 실제 CLI가 그 옵션을 따르는지는 미검증 → integration 테스트가 보완 (실 호출로 raw stream에 마커 부재 검증).
2. **integration 테스트 비용·인증 의존** — `ANTHROPIC_API_KEY` 또는 OAuth 인증 필요. CI에서는 skip (`pytest -q`만 실행), 로컬에서만 수동 `pytest -m integration`. `markers` 명시로 skip 자동화.
3. **OAuth 호환 결정** (P-VENDOR) — phase-b2-claude.md §6.1 참조. 본 plan은 `--bare` 미사용으로 Max OAuth 환경 무료 호출 보장. ANTHROPIC_API_KEY 의존성 부재. Day 4 ADR-9(`disable_bare` 토글) 후보 — API key 사용자 대상 추가 검증 deferred.
4. **마커 문자열 충돌** — sentinel 명명 통일: 파일명은 `CLAUDE.md.test-marker` (`.gitignore`에 등재 + 시나리오 A 작성/unlink), 본문 마커 문자열은 `REPO-SENTINEL-MUST-NOT-LEAK` (raw stream 부재 단언 대상). 사용자 환경 어디에도 등장하지 않는 unique sentinel — 충돌 0.
5. **`dialectic doctor` 첫 실행이 인증 안 된 환경에서 실패** — 정상. `_run_capture`가 non-zero 반환 캡처해서 사용자에게 안내. 본 phase 검증 시 인증 완료 환경 가정.
6. **README 갱신 cross-reference 깨짐** — `dialectic doctor` 등 새 명령 추가 시 README 다른 섹션의 링크·예시도 cross-check (sync-docs가 catch).
