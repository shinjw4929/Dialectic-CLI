# Dialectic-CLI

> Cross-vendor multi-agent collaboration through dialectic (thesis ↔ antithesis ↔ synthesis).

기획자가 task 한 줄을 던지면, **다른 벤더의 두 AI 코딩 에이전트**가 변증법 루프로 협업하고, 사용자가 매 턴 synthesis를 수행하는 도구.

- **Driver (thesis)** — 한 벤더 (e.g., Codex CLI). 구현·계획 *생성*
- **Reviewer (antithesis)** — 다른 벤더 (e.g., Claude Code). 충실도 + 일반 결함 *비판*
- **사용자 (synthesis)** — 매 턴 결정 (accept/replace/iterate/etc) + 자유 directive → 다음 턴 양쪽 prompt에 주입

같은 모델 self-play의 self-preference bias를 깨려면 **다른 벤더**여야 한다는 thesis 위에 설계.

---

## 빠른 시작 (WSL2 기준, 빈 머신에서 끝까지)

빈 WSL2 Ubuntu에서 처음부터 끝까지. 각 step은 독립 검증 가능 — 막히면 그 step만 다시. macOS는 brew·dnf로 패키지 관리자만 치환하면 동일 흐름.

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
| `curl`, `ca-certificates` | Node.js·codex CLI 다운로드 | ✓ |
| `build-essential` | npm native 모듈 빌드 fallback | ◯ 선택 |
| `jq` | `messages.jsonl` 라인 추출/필터 (CLI 디버깅) | ◯ 선택 — `dialectic logs`로 충분, 더 깊이 볼 때 |
| `tree` | `<workdir>/<session>/` 구조 한눈 확인 | ◯ 선택 |

검증:
```bash
python3 --version    # Python 3.10.x 이상
python3 -m venv --help   # 출력 있어야 함 (없으면 python3-venv 누락)
```

### Step 2 — Node.js + vendor CLI 설치

`claude` CLI는 npm 글로벌 패키지, `codex` CLI는 별도 binary. 둘 다 필수.

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

**`codex` CLI** — [OpenAI 공식 문서](https://github.com/openai/codex)의 install 절차 참조 (npm 또는 binary). 설치 후:
```bash
codex --version      # v0.128+ 기대
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
- `~/.local/bin/{dialectic,dialectic-skill}` symlink (PATH 포함 시) — 어디서나 호출, venv activate 불필요
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
  version  OK   0.128.x ...
  login    OK   ... (또는 FAIL — 인증 누락)
```

`auth`/`login`이 FAIL이면:
- claude → `claude /login` (Pro/Max 구독 OAuth) 또는 `ANTHROPIC_API_KEY` env (Console API key). Bedrock/Vertex 경로는 별도 설정
- codex → `codex login` (ChatGPT 구독 OAuth) 또는 `OPENAI_API_KEY` env

### Step 5 — 첫 run (1턴, 결과 확인까지)

```bash
dialectic run --task "Reply with single digit: 1+1=?" --max-turns 1
```

**기대**:
- stderr에 spinner `[driver: codex] running... ⠋` → `[reviewer: claude] running... ⠋`
- stdout에 driver(`proposal`)·reviewer(`critique`) 두 응답 본문
- 종료 시 stderr에 session 경로 안내:
  ```
  session_dir: /home/<user>/.local/share/dialectic/runs/<UTC ts>-<8char>/<UTC ts>/
  messages.jsonl: .../messages.jsonl
  ```

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
- `--interactive critical` — 매 턴 자동 진행, 종료 직전 1회 prompt + 턴 도중 **Ctrl+F**로 다음 턴 끝 개입

매 턴 흐름:
```
driver 응답 (구현) → reviewer 응답 (비판/CONVERGED) → [critical: Ctrl+F 트리거 시] 6지선다 prompt
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

# Step 2: implement 진입 + 같은 workdir에 패치 적용
dialectic implement \
  --spec "$SPEC" \
  --workdir "$(dirname $(dirname $SPEC))" \
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

## 흐름 관찰 (`dialectic logs`)

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

---

## 사용자 개입 (synthesis) — `--interactive` 모드

본 도구의 thesis "사용자 = synthesis 생성자" 핵심 wiring.

| 모드 | 매 턴 끝 | 종료 직전 | 트리거 |
|---|---|---|---|
| `end-only` (CLI default) | — | — | 자동, prompt 0 (CI 친화) |
| `critical` (메뉴 default) | Ctrl+F 누른 턴만 6지선다 | `[CONVERGED]` streak 또는 max-turns 도달 시 `prompt_end_or_iterate` (Y/n/text) | Ctrl+F 비동기 |
| `full` | 매 턴 강제 6지선다 (a/r/m/i/e/s) | `critical`과 동일 | 자동 |

**6지선다** (full / critical 트리거 분기):
- `a` — accept driver 응답, reviewer 무시
- `r` — replace 사용자 직권 코드/응답
- `m` — modify directive 추가
- `i` — iterate 한 턴 더 (max-turns += 1)
- `e` — end 즉시 종료
- `s` — skip reviewer (다음 턴 driver만)

`MAX_TURNS_HARD_CAP=20` 절대 상한 (i 분기 무한 누적 차단).

---

## CLI 옵션 (`dialectic run`)

| 옵션 | default | 설명 |
|---|---|---|
| `--task <text>` | (필수) | task 한 줄. driver/reviewer prompt §2 TASK 주입 |
| `--workdir <path>` | XDG default | 작업 디렉토리. 미지정 시 `~/.local/share/dialectic/runs/<UTC ts>-<8char>/` 자동 생성. 매 호출마다 `<workdir>/<UTC ts>/` session 폴더 격리 |
| `--driver {codex,claude}` | `codex` | thesis 발화 위치 |
| `--reviewer {codex,claude}` | `claude` | antithesis 발화 위치 |
| `--max-turns N` | `1` | 최대 turn (양수). 도달 시 `auto-end (max-turns reached)` |
| `--mode {run,plan,implement}` | `run` | compare는 별도 subcommand (미구현) |
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
- `docs/dev-docs/architecture.md` — 왜 dialectic, 4계층 매핑, ADR 8개+
- `docs/dev-docs/systems/INDEX.md` — 모듈별 SSOT (orchestrator/agents/jsonl-bus/cwd-isolation/env-check/ui/patch-apply)
- `docs/dev-docs/code-conventions.md` — Python 규칙
- `docs/dev-docs/Documentation-Checklist.md` — 변경 → .md 매핑
- `docs/dev-docs/validation.md` — 결함 → 규칙 환원 (P-id 표)
- `outline/` — 결정 흐름 (Q1~Q17)

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

---

## 라이선스

MIT (예정)
