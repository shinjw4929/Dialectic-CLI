# Dialectic-CLI

> Cross-vendor multi-agent collaboration through dialectic (thesis ↔ antithesis ↔ synthesis).

기획자가 task 한 줄을 던지면, **다른 벤더의 두 AI 코딩 에이전트**가 변증법 루프로 협업하고, 사용자가 매 턴 synthesis를 수행하는 도구.

- **Driver (thesis)** — 한 벤더 (e.g., Codex CLI). 구현·계획 *생성*
- **Reviewer (antithesis)** — 다른 벤더 (e.g., Claude Code). 충실도 + 일반 결함 *비판*
- **사용자 (synthesis)** — driver thesis와 reviewer antithesis를 보고 다음 턴 directive 결정. directive는 history에 누적되어 양쪽 prompt §3 HISTORY에 노출. 개입 빈도·형식은 `--interactive` 모드 dial: `end-only`(0회) / `critical`(Ctrl+F 트리거 + 종료 직전, iterate prompt Y/c/text 또는 Y/n/text) / `full`(매 턴 강제 6지선다 a/r/m/i/e/s). 상세는 §사용자 개입

같은 모델 self-play의 self-preference bias를 깨려면 **다른 벤더**여야 한다는 thesis 위에 설계.

---

## 빠른 시작 (WSL2 기준, 빈 머신에서 끝까지)

빈 WSL2 Ubuntu에서 처음부터 끝까지. 각 step은 독립 검증 가능 — 막히면 그 step만 다시. macOS는 Homebrew, Fedora/RHEL 계열은 dnf처럼 패키지 관리자만 치환하면 동일 흐름.

### Step 0 — WSL2 환경 (Windows host)

PowerShell (관리자):
```powershell
wsl --install -d Ubuntu-22.04   # 또는 Ubuntu-24.04
```
재부팅 후 Ubuntu 첫 실행 — username/password 설정. 이후 모든 명령은 WSL 안 bash에서.

### Step 1 — 시스템 패키지 (Ubuntu apt)

```bash
sudo apt update
sudo apt install -y \
    python3 python3-venv python3-pip \
    git curl ca-certificates \
    build-essential          # Node.js native 빌드 대비 (선택)

# 선택 — messages.jsonl 분석/디버깅용
sudo apt install -y jq tree
```

| 패키지 | 용도 | 필수? |
|---|---|---|
| `python3` (>=3.10) | 본 도구 런타임 | ✓ Ubuntu 22.04 default 3.10, 24.04는 3.12 |
| `python3-venv` | `setup.sh`가 `.venv/` 생성 시 | ✓ apt 별도 패키지 (default 미설치) |
| `python3-pip` | `pip install -e .` | ✓ |
| `git` | repo clone | ✓ |
| `curl`, `ca-certificates` | nvm·Codex CLI release 다운로드 | ✓ |
| `build-essential` | npm native 모듈 빌드 fallback | ◯ 선택 |
| `jq` | `messages.jsonl` 라인 추출/필터 (CLI 디버깅) | ◯ 선택 — `dialectic logs`로 충분, 더 깊이 볼 때 |
| `tree` | `<workdir>/<session>/` 구조 한눈 확인 | ◯ 선택 |

검증:
```bash
python3 --version    # Python 3.10.x 이상
python3 -m venv --help   # 출력 있어야 함 (없으면 python3-venv 누락)
```

### Step 2 — Node.js + vendor CLI 설치

`claude`와 `codex` CLI 둘 다 필수. `claude`는 npm 글로벌 패키지로 설치하고, `codex`는 OpenAI 공식 경로인 npm/Homebrew/GitHub Release 중 하나로 설치한다. WSL2에서는 Step 2에서 이미 Node.js/npm을 준비하므로 npm 설치가 가장 단순하다.

**Node.js** (LTS, nvm 권장 — 시스템 npm 권한 충돌 회피):
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.nvm/nvm.sh
nvm install --lts
node --version       # v20.x 이상
```

**`claude` CLI**:
```bash
npm install -g @anthropic-ai/claude-code
claude --version     # v2.1+ 기대
```

**`codex` CLI** — [OpenAI Codex CLI 공식 repo](https://github.com/openai/codex)의 install 절차 참조 (npm 기본, Homebrew 또는 GitHub Release binary 대안). WSL2 npm 경로:
```bash
npm install -g @openai/codex
codex --version      # codex-cli x.y.z 형식 출력
```

본 도구 자체는 **외부 의존성 0** (표준 라이브러리만, dev: pytest). vendor CLI 둘 다 설치·인증 필수 — mock fallback 없음.

### Step 3 — 본 도구 설치

```bash
git clone <this-repo-url> Dialectic-CLI
cd Dialectic-CLI
./setup.sh
```

`setup.sh`가 수행:
- Python 3.10+ 확인
- `.venv/` 생성 + `pip install -e .` (editable)
- `~/.local/bin/{dialectic,dialectic-skill}` symlink (디렉토리 자동 생성) — 어디서나 호출, venv activate 불필요. PATH 미포함 시 안내만 출력
- vendor CLI 설치 여부 안내

`~/.local/bin`이 PATH에 없으면:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```
또는 repo 루트에서 `./dialectic` 직접 호출.

### Step 4 — 환경 점검

```bash
dialectic doctor
```

**기대 출력**:
```
[claude]
  version  OK   2.1.x ...
  auth     OK   ... (또는 FAIL — 인증 누락)
[codex]
  version  OK   codex-cli x.y.z ...
  login    OK   Logged in using ChatGPT ... (또는 FAIL — 인증 누락)
```

`auth`/`login`이 FAIL이면:
- claude → `claude /login` (Pro/Max 구독 OAuth) 또는 `ANTHROPIC_API_KEY` env (Console API key). Bedrock/Vertex 경로는 별도 설정
- codex → `codex` 또는 `codex login`으로 ChatGPT 계정 OAuth 로그인 후 `codex login status` 확인. API key 경로는 `OPENAI_API_KEY` env 사용

### Step 5 — 첫 run (1턴, 결과 확인까지)

```bash
dialectic run --task "Reply with single digit: 1+1=?" --max-turns 1
```

**기대**:
- stderr에 spinner `[구현자: Codex CLI] running... ⠋` → `[코드 검토자: Claude Code] running... ⠋` (역할 한국어 라벨, `src/ui.py:56-61` `ROLE_LABEL_KO` SSOT)
- stdout에 driver(`proposal`)·reviewer(`critique`) 두 응답 본문 (구분선 + 헤더 + 본문)
- 종료 시 stderr 안내 (run_session finally):
  ```
  [run_session] session 보존: /home/<user>/.local/share/dialectic/runs/<UTC ts>-<8char>/<UTC ts>
    messages.jsonl: .../messages.jsonl
    raw streams:    .../sessions/
    reason:         auto-end (max-turns reached)   # 또는 auto_end_converged / auto_end_user
  ```
  + implement 모드는 `files_changed:` 단락 추가 (apply_status="ok" 산출 파일 list)

**결과 검증**:
```bash
dialectic logs --tail 10
```
turn=0 task → turn=1 proposal → turn=1 critique → turn=1 meta(auto-end) 4 라인+ 보이면 성공.

(선택) `jq` 설치된 경우 raw 검사:
```bash
SESSION=$(ls -dt ~/.local/share/dialectic/runs/*/*/ | head -1)
jq -c '{turn:.turn_id, kind, from:.from}' "$SESSION/messages.jsonl"
```

---

## 사용 — 4 모드

빠른 시작 검증 후, 시나리오별 명령:

### `run` — 한 줄 task → 1턴+ 대화

```bash
dialectic run \
  --task "Python으로 이진 탐색 트리 구현" \
  --max-turns 5 \
  --interactive critical
```

- `--max-turns 5` — 최대 5턴 (`[CONVERGED]` 2턴 누적 시 조기 종료)
- `--interactive critical` — 매 턴 자동 진행, 종료 직전 1회 iterate prompt + 턴 도중 **Ctrl+F**로 다음 턴 끝 iterate prompt 트리거 (Y/c/text)

매 턴 흐름:
```
driver 응답 (구현) → reviewer 응답 (비판/CONVERGED) → [critical: Ctrl+F 트리거 시] iterate prompt
                                                  → 다음 턴 history에 누적
```

### `plan` — spec.md 자동 저장

```bash
dialectic run --mode plan \
  --task "그래프 라이브러리 spec 작성" \
  --max-turns 3
```

- driver = `planner`, reviewer = `plan-reviewer` 역할로 자동 매핑
- 매 턴 driver 응답이 `<workdir>/specs/<slug>.md` top-level에 자동 저장 (충돌 시 `<slug>-<session_ts>.md` fallback)
- session 경로는 stderr 안내 — `<workdir>` 자체에 `specs/` 폴더 위치 (session 격리 X)

저장 위치 확인:
```bash
ls ~/.local/share/dialectic/runs/<UTC ts>-<8char>/specs/
```

### `implement` — spec.md 입력 → 패치 적용

`plan` 산출 spec.md를 그대로 다음 단계 입력으로 재진입 (chaining):

```bash
# Step 1: plan 산출 경로 확인
SPEC=$(ls -t ~/.local/share/dialectic/runs/*/specs/*.md | head -1)
echo "$SPEC"
WORKDIR=$(dirname "$(dirname "$SPEC")")

# Step 2: implement 진입 + 같은 workdir에 패치 적용
dialectic implement \
  --spec "$SPEC" \
  --workdir "$WORKDIR" \
  --max-turns 5
```

매 턴:
- spec.md 본문 → driver(implementer) prompt §2 TASK 자리 주입
- driver 응답에서 SEARCH/REPLACE 마커 추출 → `apply_patches`가 workdir에 반영 (신규 파일 생성 포함, all-or-nothing rollback)
- reviewer(spec-reviewer)가 spec 충실도 검토

`dialectic implement`는 `dialectic run --mode implement --spec <path>`의 alias.

### `compare` — 미구현 (후속 plan)

여러 벤더 매핑 batch 실행 + 결과 비교. argparse subparser 미등록, 메뉴 단계 2에서 안내 + retry.

---

## 메뉴 진입 (인터랙티브)

CLI 인자 없이 단독 호출 시 5단계 wizard:

```bash
dialectic
```

```
Step 1 — 환경 점검 (spinner)
Step 2 — 모드 선택 (1=run / 2=plan / 3=implement / 4=compare[미구현])
Step 3 — task 입력 (또는 implement 모드 시 spec.md 경로)
Step 4 — 매핑 (codex→claude / claude→codex) + workdir + max-turns
Step 5 — 진행 확인 [Y/n] → run_session
```

메뉴 진입 default `--interactive critical` (CLI 직접 호출은 `end-only`).

> **한글 입력 결함**: terminal IME 조립 단계에서 일부 char가 buffer에 누락될 수 있음 (실측: 28→21 char). Step 5의 task echo back으로 시각 검증, 정확 입력 필요 시 `dialectic run --task "..."` CLI 인자로 우회. 상세: `docs/dev-docs/validation.md §3 C-011`.

---

## 도움말

```bash
dialectic --help            # 서브커맨드 list (run/implement/doctor/logs)
dialectic run --help        # run 옵션 전체 (--task/--workdir/--driver/...)
dialectic implement --help  # implement alias 옵션
dialectic doctor --help
dialectic logs --help       # --tail/--follow/--kind/--full 등
```

**메뉴 진입 도움말 키**:
- task / spec 경로 입력 단계에서 `?` 입력 → 그 단계 도움말 1줄 출력 후 재입력 prompt
- 모든 입력 단계에서 `Ctrl-C` / `Ctrl-D` → "종료하시겠습니까? (Enter=종료, n=계속)" 확인 prompt

---

## 트러블슈팅

빠른 시작 따라가다 막히는 흔한 케이스 + 해결.

### `dialectic doctor` FAIL

| FAIL 행 | 의미 | 해결 |
|---|---|---|
| `claude / version FAIL` | claude CLI 미설치 또는 PATH 부재 | `npm install -g @anthropic-ai/claude-code` 후 `which claude` 확인. nvm 사용 시 새 shell에서 `nvm use --lts` 먼저 |
| `claude / auth FAIL` | claude 인증 누락 | `claude /login` (OAuth) 또는 `export ANTHROPIC_API_KEY=sk-ant-...` |
| `codex / version FAIL` | codex CLI 미설치 | `npm install -g @openai/codex` 또는 [공식 repo](https://github.com/openai/codex) 안내 |
| `codex / login FAIL` | codex 인증 누락 | `codex login` (ChatGPT OAuth) 또는 `export OPENAI_API_KEY=sk-...` |

### `dialectic run` 진입 시 SystemExit (ADR-6 차단)

```
[ADR-6] workdir(/home/<user>/Dialectic-CLI/...)이 Dialectic-CLI repo 하위 — 사용 불가
```

**원인**: claude/codex가 cwd부터 부모 dir까지 `CLAUDE.md`/`AGENTS.md` auto-discovery → 본 repo의 개발용 .md가 런타임 prompt에 누수.

**해결**: `--workdir`에 repo 밖 절대 경로 지정, 또는 인자 생략 시 자동 XDG default(`~/.local/share/dialectic/runs/...`) 사용.

### 1턴만 돌고 즉시 종료 (`auto_end_converged`)

driver 응답 끝에 우연히 `[CONVERGED]` 형태 텍스트 포함 → reviewer가 그 streak를 누적 → 사용자가 의도한 multi-turn dialectic 안 됨.

**해결**:
- `--convergence-streak 3` 으로 K 상향 (default 2 → 3턴 누적 필요)
- `--interactive critical` 로 종료 직전 iterate prompt 노출 (`n` 입력 시 종료 차단 + 추가 턴)
- task 본문에 "응답 끝에 `[CONVERGED]` 마커 사용 금지" 명시 (driver/reviewer ROLE 정합)

### subprocess timeout (응답 5분 초과)

`DEFAULT_TIMEOUT_S=300` 상한. 초과 시 `kind=error` 메시지 append + 다음 턴 진행 차단. 증상:
```
[error] subprocess.TimeoutExpired (300s) — codex/claude 응답 지연
```

**해결**: task를 더 작은 단위로 분할 (예: "전체 라이브러리 구현" → "함수 시그니처만 먼저"). vendor CLI 자체가 hang 시 `dialectic doctor` 재실행으로 인증 상태 확인.

### `apply_patches` failed (`patch_applied` meta.apply_status = "failed")

`messages.jsonl`에서 `kind=patch_applied` 라인 + `meta.apply_error` 확인:
```bash
jq -c 'select(.kind == "patch_applied") | {turn:.turn_id, status:.meta.apply_status, error:.meta.apply_error}' "$SESSION/messages.jsonl"
```

흔한 원인: SEARCH 본문이 파일에 unique match 없음 / 빈 SEARCH인데 파일 이미 존재 / path validation 실패 (workdir 밖 경로). all-or-nothing rollback이라 **부분 적용 0** — 그냥 다음 턴에서 다시 시도하면 됨.

### session_dir 디스크 누적

매 호출마다 `~/.local/share/dialectic/runs/` 하위 폴더 생성, cleanup X (결과 보존이 의도). 주기 정리:
```bash
# 7일 이상 된 session 폴더 삭제 (예시 — 본인 책임)
find ~/.local/share/dialectic/runs/ -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +
```

---

## 흐름 관찰

### 추상 명령 — `dialectic logs`

```bash
# 자동 — 마지막 session 탐색 (base_dir 우선순위)
dialectic logs --tail 10

# kind 필터 + 본문 펼침
dialectic logs --kind critique --full

# 명시 session + 실시간 follow
dialectic logs --workdir <path> --session <UTC ts> --follow
```

base_dir 우선순위: `--workdir` CLI > `DIALECTIC_RUNS_DIR` env > `XDG_DATA_HOME/dialectic/runs/` > `~/.local/share/dialectic/runs/`.

각 라인 default = 1줄 요약 (`turn/seq/kind/from`). `--full`로 본문 펼침. `--kind`로 (proposal/critique/decision/error/meta/task/patch_applied 등) 필터.

### 실 파일 경로 (직접 cat / jq)

`run_session` 종료 시 stderr에 `session_dir`/`messages.jsonl` 절대 경로 안내. 그대로 cat/jq 가능.

**경로 결정 규칙**:
- `--workdir <path>` 명시 시 → `<path>/<UTC ts>/`
- 미명시 시 → `~/.local/share/dialectic/runs/<UTC ts>-<8char>/<UTC ts>/` (XDG default)

**session_dir 구조**:
```
<workdir>/<UTC ts>/                  # session_dir (run_session마다 격리)
├── messages.jsonl                   # turn 라이프사이클 정본 (append-only, JSONL)
└── sessions/                        # 어댑터 raw 응답 (디버깅용)
    ├── <turn>-driver-<msg_id8>.jsonl
    └── <turn>-reviewer-<msg_id8>.jsonl

<workdir>/specs/                     # plan 모드 산출 (session 격리 X, top-level)
└── <slug>.md                        # planner 응답 본문 자동 저장
```

**직접 검사 예시**:
```bash
# 사용자 명시 workdir인 경우
cat /tmp/my-workdir/<UTC ts>/messages.jsonl | jq -c '{turn:.turn_id, kind, from:.from}'

# 자동 생성 XDG default 경우 — 최신 session
SESSION=$(ls -dt ~/.local/share/dialectic/runs/*/*/ | head -1)
cat "$SESSION/messages.jsonl" | jq -c '{turn:.turn_id, kind, from:.from}'

# 어댑터 raw 응답 (driver 1턴) — token 사용량·session_id·model 등 meta 보존
cat "$SESSION/sessions/1-driver-"*.jsonl | jq .

# patch_applied 메시지만 (apply_status·files_changed 확인)
jq -c 'select(.kind == "patch_applied") | {turn:.turn_id, status:.meta.apply_status, files:.meta.files_changed}' "$SESSION/messages.jsonl"
```

`messages.jsonl`은 append-only — 기존 라인 절대 수정 X (정정은 새 메시지로). 스키마 정본은 `docs/runtime-docs/protocol.md §2`.

---

## 사용자 개입 (synthesis) — `--interactive` 모드

본 도구의 thesis "사용자 = synthesis 생성자" 핵심 wiring.

진입로별 default가 다름:
- **CLI 직접 호출** (`dialectic run --task ...`) → `end-only` (자동 진행, CI·스크립트 친화)
- **메뉴 진입** (`dialectic` 단독) → `critical` (기획자 페르소나 개입 의도 ↑)

| 모드 | 매 턴 끝 | 종료 직전 | 트리거 |
|---|---|---|---|
| `end-only` | — | — | 자동, prompt 0 |
| `critical` | Ctrl+F 누른 턴만 **iterate prompt** (Y/c/text) | `[CONVERGED]` streak 또는 max-turns 도달 시 **iterate prompt** (Y/n/text) | Ctrl+F 비동기 |
| `full` | 매 턴 강제 **6지선다** (a/r/m/i/e/s) | `critical`과 동일 — iterate prompt | 자동 |

두 prompt 형식이 다름 — `prompt_decision`(6지선다)은 `full` 전용, `critical`은 `prompt_end_or_iterate`(iterate prompt)만 사용.

**`full` 모드 6지선다** (`prompt_decision`, `src/ui.py`):
- `a` — accept driver 응답, reviewer 무시
- `r` — replace 사용자 직권 코드/응답
- `m` — modify directive 추가
- `i` — iterate 한 턴 더 (max-turns += 1)
- `e` — end 즉시 종료
- `s` — skip reviewer (다음 턴 driver만)

**`critical` / `full` iterate prompt** (`prompt_end_or_iterate`, 종료 직전 공통):
- `Y` (Enter) — 그대로 진행/종료 (default)
- `n` — 종료 차단 (CONVERGED/max-turns 도달 시만 노출)
- `c` — Ctrl+F 실수 트리거 취소 (trigger 단독 분기만)
- 자유 텍스트 — directive로 누적, max-turns += 1

`MAX_TURNS_HARD_CAP=20` 절대 상한 (i / iterate 분기 무한 누적 차단).

---

## CLI 옵션 (`dialectic run`)

| 옵션 | default | 설명 |
|---|---|---|
| `--task <text>` | (필수) | task 한 줄. driver/reviewer prompt §2 TASK 주입 |
| `--workdir <path>` | XDG default | 작업 디렉토리. 미지정 시 `~/.local/share/dialectic/runs/<UTC ts>-<8char>/` 자동 생성. 매 호출마다 `<workdir>/<UTC ts>/` session 폴더 격리 |
| `--driver {codex,claude}` | `codex` | thesis 발화 위치 |
| `--reviewer {codex,claude}` | `claude` | antithesis 발화 위치 |
| `--max-turns N` | `1` | 최대 turn (양수). 도달 시 `auto-end (max-turns reached)` |
| `--mode {run,plan,implement}` | `run` | compare는 아직 CLI에 등록되지 않은 후속 모드 |
| `--convergence-streak K` | `2` | reviewer `[CONVERGED]` 누적 K턴 → `auto_end_converged`. `--max-turns < K+1` 시 K=1 fallback (ADR-9) |
| `--interactive {end-only,critical,full}` | CLI: `end-only` / 메뉴: `critical` | 위 §사용자 개입 표 참조 |
| `--spec <path>` | — | `--mode implement` 시 필수 |

`dialectic implement --spec <path>` = `dialectic run --mode implement --spec <path>` alias.

`dialectic doctor` 인자 없음 — claude/codex `--version` + auth status. `claude doctor`는 영구 제외 (codex 동등 부재 + capture_output 30s+ hang, P-VENDOR 환원).

---

## 데모 시나리오

`tasks/implement-dijkstra/task.md` — 빈 workdir에서 dijkstra 구현 + 매 턴 user synthesis directive로 visualize → 색 그라데이션 점진적 enhancement (critical 모드 시연):

```bash
# 1차 task 본문을 task.md에서 paste, 또는 메뉴 진입 후 직접 입력
dialectic run \
  --task "$(sed -n '/```$/,/```/p' tasks/implement-dijkstra/task.md | sed '1d;$d' | head -20)" \
  --interactive critical \
  --max-turns 5

# Turn 2/3 끝 prompt에서 task.md "후속 user synthesis directive" 표의 directive 직접 입력
```

`tasks/modify-dijkstra-add-graph/` — seed 코드 수정 흐름 시연 (구현 vs 수정 분리).

---

## workdir 격리 (ADR-6)

claude/codex가 cwd부터 부모 dir까지 `CLAUDE.md`/`AGENTS.md` auto-discovery → **Dialectic-CLI repo 루트·하위는 workdir로 사용 불가** (개발용 .md가 런타임 prompt에 누수). `run_session` 진입 시 SystemExit, 메뉴는 mkdir 전 조기 거부 (`is_under_repo_root` SSOT, `src/orchestrator.py:87`).

`base_dir` 자체가 repo 하위인 env 설정도 차단됨.

자동 생성 default: `~/.local/share/dialectic/runs/<UTC ts>-<8char>/` (XDG Base Directory Specification 준수). cleanup X — 결과 확인 통로 보존, 사용자가 주기 정리.

---

## 구현 상태

### 동작

| 영역 | 위치 |
|---|---|
| `pyproject.toml` + `dialectic`/`dialectic-skill` entry point | `pyproject.toml` |
| 메시지 스키마·JSONL bus | `src/schema.py`, `src/bus.py` |
| 어댑터 (codex/claude) + cwd 격리 | `src/agents/{base,codex,claude}.py`, `src/orchestrator.py:87` |
| Orchestrator 1턴+ 라이프사이클 (`run`/`plan`/`implement`) | `src/orchestrator.py` |
| `[CONVERGED]` streak 자동 종료 (ADR-9) | `src/orchestrator.py:_detect_converged` |
| 사용자 6지선다 UI (a/r/m/i/e/s) + Ctrl+F 비동기 트리거 | `src/ui.py:prompt_decision`, `TriggerListener` |
| 5단계 메뉴 진입 + IUTF8 한글 입력 | `src/cli.py:_interactive_menu` |
| `--interactive {end-only,critical,full}` | `src/cli.py:p_run` |
| `dialectic implement --spec` (alias) + spec→TASK substitution | `src/cli.py:p_implement` |
| `apply_patches` SEARCH/REPLACE + 신규 파일 생성 | `src/patch_apply.py` |
| `plan` 모드 spec.md 자동 저장 | `src/orchestrator.py:_resolve_spec_path` |
| `dialectic logs` 흐름 관찰 (tail/follow/kind/full) | `src/logs.py` |
| `dialectic doctor` 환경 점검 (벤더 대칭) | `src/env_check.py` |
| `setup.sh` (venv + editable install + `~/.local/bin` shim) | `setup.sh` |
| 데모 시나리오 (구현·수정) | `tasks/{implement-dijkstra,modify-dijkstra-add-graph}/` |

### 미구현 / deferred

| 항목 | 상태 |
|---|---|
| `compare` subcommand + `--parallel` | 후속 plan |
| Mock 어댑터 (`--driver mock`) | 영구 deferred (실 codex/claude 호출만 신뢰) |
| 데모 영상 (asciinema/mp4) | 후속 |
| Windows native | deferred (`Path.resolve()` symlink + drive letter 별도 검증) |

---

## 더 읽기

런타임 사양 (B 층):
- `docs/runtime-docs/protocol.md` — 메시지 스키마, 턴 라이프사이클, 모드↔role 매핑, 실패 모드
- `docs/runtime-docs/roles/*.md` — 4 role 정의 (implementer / spec-reviewer / planner / plan-reviewer)
- `docs/runtime-docs/systems/INDEX.md` — 모드별 SSOT (run/plan/implement/compare)

개발 사양 (A 층):
- `docs/dev-docs/architecture.md` — 왜 dialectic, 4계층 매핑, ADR 10개
- `docs/dev-docs/systems/INDEX.md` — 모듈별 SSOT (orchestrator/agents/jsonl-bus/cwd-isolation/env-check/ui/patch-apply)
- `docs/dev-docs/code-conventions.md` — Python 규칙
- `docs/dev-docs/Documentation-Checklist.md` — 변경 → .md 매핑
- `docs/dev-docs/validation.md` — 결함 → 규칙 환원 (R-001~R-003 정식 + P-id 표)
- `outline/` — 결정 흐름 (Q1~Q23)

---

## 개발 / 기여

`CLAUDE.md` (Claude Code) 또는 `AGENTS.md` (Codex CLI)가 개발용 진입점. 본 repo 자체가 Claude Code + Codex CLI 페어 프로그래밍으로 작성됨.

Codex에서 `.claude/skills/*` 워크플로우를 명시 호출:

```bash
./dialectic-skill sync-docs                 # `$sync-docs` 호출 문구 출력
dialectic-skill review-plan plan/001-run-mode-core
dialectic-skill --show review-code          # SKILL.md 본문 출력
```

`dialectic-skill <workflow>`는 `docs/dev-docs/codex-compat.md` 정책의 `$<workflow>` 명시 호출 문구를 출력. 출력을 Codex 대화에 주입하면 canonical `.claude/skills/<workflow>/SKILL.md` 절차가 Codex 방식으로 적용된다.
