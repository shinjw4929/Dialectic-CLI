# Dialectic-CLI 계획 — 인덱스

> 갱신: 2026-05-07 — Q1~Q3·Q5~Q7·Q9~Q18 결정 반영, Q4·Q8 보류(결정 시점 명시).
> 파일 번호 ↔ §번호 정렬. 하네스(§1)가 첫 번째.

## 파일 구성

| 파일 | 내용 | § |
|---|---|---|
| [01-harness-layers.md](01-harness-layers.md) | A(개발용)/B(런타임용) 두 층 구분, cwd 격리, 4 role 셀프체크, dev-time 파일 명세 | §1 |
| [02-communication.md](02-communication.md) | 통신 모델, 메시지 스키마, 턴 라이프사이클, 프롬프트 빌드, 포지션·역할·벤더 매핑, 어댑터·실패 모드 | §2 |
| [03-ux.md](03-ux.md) | 실행 흐름, 화면 구성, 사용자 개입, 산출물, 관찰성 | §3 |
| [04-requirements-and-modes.md](04-requirements-and-modes.md) | 과제 요구사항 충족, 데모 task, mock 모드 + 4 모드 정의 + 모드별 구현 비용 | §4 |
| [05-timeline.md](05-timeline.md) | 4일 타임라인 (평일 회사 후 + 토요일 종일), 위험 요소, 다음 행동 | §5 |

본 README에 포함:
- §0 사전 확인 결과 (초기 가정 검증) — 환경/도구
- §6 결정 상태 보드 (Q1~Q18)

cross-reference: 본문 안의 `§2.7`, `§1.3` 등 표기는 위 매핑 표를 보고 해당 파일에서 찾는다.

---

## 0. 사전 확인 결과 (초기 가정 검증)

| 항목 | 초기 가정 | 실측 결과 | 액션 |
|---|---|---|---|
| `claude` CLI | 설치됨 가정 | v2.1.131, `~/.local/bin/claude` ✓ | 그대로 진행 |
| `codex` CLI | 설치됨 가정 | v0.128.0, `/usr/local/bin/codex` ✓ | 그대로 진행 |
| `gemini` CLI | "다른 벤더 추가 가능" 시사 | **미설치** | 2벤더로 충분, gemini는 plugin slot 인터페이스만 정의 |
| Claude 헤드리스 출력 | `stream-json` 가정 | `-p --output-format json` 단일 응답 / `stream-json` 둘 다 정상. `session_id` · `total_cost_usd` · `usage.cache_*` 다 포함 | 단일 응답이면 `json`, 진행 표시 원하면 `stream-json --include-partial-messages` |
| Codex 헤드리스 출력 | `codex exec` JSON | `codex exec --json -` 정상. **`thread_id`** (Claude는 `session_id`) | 명칭만 다르고 의미 동일. 추상화 |
| 세션 재개 플래그 | `--session-id` / `--resume` | Claude는 `--session-id <uuid>` 사전 지정 가능 / `--resume <id>`. Codex는 `thread.started` 이벤트에서 `thread_id` 캡처 후 `codex exec resume <id>` | **확정 (Q1=B)**: stateless 호출 — 세션 ID는 로그 파일명 일관성 용도만 |
| `jq` | "tail -f \| jq"로 관찰 | **미설치** | **확정 (Q3 갱신)**: 도구 자체가 `dialectic logs` 내장. 외부 명령 안내 X. raw JSONL은 사용자가 자유롭게 파이프 가능 (자명한 옵션) |
| cwd의 `CLAUDE.md`/`AGENTS.md` 자동 로드 | 미검증 | claude/codex 둘 다 cwd 진입점 .md를 자동 로드할 가능성 → 개발용 ROLE이 런타임 prompt에 누수 위험 | **확정 (Q11=B)**: §1.3 cwd 격리 (`--workdir` 또는 `tempfile.mkdtemp()`)로 원천 차단 |

스모크 테스트 (`"1+1"` 한 턴):
- Claude `-p --tools "" --output-format json`: 2.4s, $0.037, 6 토큰 출력 ✓
- Codex `exec --sandbox read-only --json`: 시작 즉시 `{thread.started, thread_id}` 이벤트, `item.completed{text:"2"}`, `turn.completed{usage}` ✓

→ **양쪽 다 텍스트 in/out 어댑터 작성 가능**. 둘의 출력 스키마 차이는 `src/agents/{codex,claude}.py`의 `parse()` 메서드에서 흡수.

---

## 6. 결정 상태 보드

```
✅ Q1  세션 연속성 = stateless + 풀 트랜스크립트 주입
✅ Q2  포지션 매핑(벤더) = --driver/--reviewer 자유, 두 시나리오 비교 narrative
✅ Q3  관찰 = 내장 `dialectic logs` 서브커맨드 (외부 명령 안내 X). 도구 자체가 1차 인터페이스
🟡 Q4  데모 task = Day 1 .md 끝 직후 결정 (Q13 따라 wave_difficulty 1순위)
✅ Q5  mock 모드 = 사전녹음 재생 + --record 플래그 + 인증 부재 시 자동 fallback (Q12·C)
✅ Q6  종료 조건 = b 우선 (reviewer [CONVERGED] 마커 + 연속 K=2턴 P0/P1=0 → 자동 e). 안전망: a (--max-turns), c (사용자 e/Ctrl-C). K는 --convergence-streak 조정.
✅ Q7  UI = A로 시작, Day 3에 rich 부분 도입 검토 (C는 스코프 외)
🟡 Q8  녹화 = Day 3 시점 결정 (asciinema 우선, mp4 백업)
✅ Q9  배치 = dialectic compare --parallel (별도 서브커맨드, 비대화형)
✅ Q10 1차 사용자 = 기획자 페르소나. 동선: README → docs/dev-docs/architecture → harness → 실 데모 (각 단계 자기 충족적)
✅ Q11 .md 두 층 분리 + cwd 격리 = A(dev-time)/B(runtime) 분리, `--workdir` 명시 또는 `tempfile.mkdtemp()` fallback (§1)
✅ Q12 모드 분리 = 4개 모드(run·plan·implement·compare). 모드별 role.md 자동 매핑 (§4.5)
✅ Q13 사용자 페르소나 = 기획자 (게임 룰·밸런스·메커닉 task 위주). 데모 task 기획자 톤으로 작성 (§4.3)
✅ Q14 CLI/메뉴 = 둘 다 (인자 부재 시 메뉴 fallback, 모든 인자 시 즉시 실행). compare는 인자만 (§3)
✅ Q15 폴더 명칭 = 영어 (`specs/`). 한국어 narrative는 README/UI 문구로
✅ Q16 reviewer 범위 = 기획 충실도(P0/P1) + 일반 결함(P2). 우선순위 라벨로 분리 (§4.5·§1.4)
✅ Q17 개발용 하네스 보강 = `docs/dev-docs/code-conventions.md` 신규 + `docs/dev-docs/assignment-requirements.md` 신규 + `docs/dev-docs/architecture.md`에 ADR 9개 표 인라인. 동선: README → req → arch → harness → code
✅ Q18 사용자 개입 default = critical (P0/P1 발견 시만 prompt, P2/0이면 자동 진행). --interactive {full,critical,end-only} 3단계 dial. Enter = iterate(빈 directive).
🟡 Q19 setup.sh 후 dialectic PATH 노출 = 미정 (옵션: a) launcher wrapper(`./dialectic`이 venv python 호출) / b) `pipx install -e .` / c) venv activate 안내 명시). 첫 사용자 진입 SLA에 직결. README §3.1 setup.sh 항목에서 결정 필요 — 03-ux.md:9-15
🟡 Q20 사전 의존성(Python·claude/codex CLI) 검증 책임 = 미정 (옵션: a) setup.sh가 검증 + 미설치 시 install URL 출력 / b) `dialectic` 실행 시점 환경 점검(§3.2)만 / c) 둘 다). 현재는 (b)만 있어 setup 단계에서 누락 사실을 모름 — 03-ux.md:107-122
🟡 Q21 tasks/<id>/recordings/ git commit 정책 = 미정 (옵션: a) commit 필수 — 인증 부재 mock fallback 보장 / b) .gitignore + 첫 실행 시 다운로드 / c) 별도 브랜치). Q5·C(인증 부재 자동 mock fallback)의 전제 조건. Day 4 녹음 자산이 repo에 들어가는지 04-§4.4에 못 박혀야 함 — 04-requirements-and-modes.md:111-130, 05-timeline.md:100
```
