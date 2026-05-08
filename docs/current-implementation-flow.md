# Current Implementation Flow

> 현재 구현을 한눈에 보기 위한 루트 지도 문서. 세부 동작의 정본은 아래 링크된 systems/protocol 문서다.

## 현재 범위

2026-05-08 기준 구현 표면:

| 영역 | 현재 상태 | 정본 |
|---|---|---|
| CLI 진입점 | `dialectic run`, `dialectic doctor` | [orchestrator + cli](dev-docs/systems/orchestrator.md#cli) |
| 실행 모드 | `run`만 CLI에 노출 | [run mode](runtime-docs/systems/run-mode.md) |
| 포지션 | `driver` → `reviewer` | [protocol](runtime-docs/protocol.md#10-포지션-vs-역할-vs-벤더-3축-분리) |
| 로그 | `logs/messages.jsonl` + `logs/sessions/*.jsonl` | [jsonl-bus](dev-docs/systems/jsonl-bus.md) |
| 종료 | fatal error / `[CONVERGED]` streak / `max-turns` | [run mode 종료 조건](runtime-docs/systems/run-mode.md#4-종료-조건-dod-01-plan-6--outline04-451) |

## 한눈 흐름

```mermaid
flowchart TD
    CLI["dialectic run"]
    Session["run_session"]
    Guard["workdir resolve<br/>ADR-6 repo-root 차단"]
    Logs["logs/messages.jsonl<br/>logs/sessions/"]
    Task["append task<br/>turn_id=0"]
    Loop["turn loop<br/>1..max_turns"]
    Turn["run_turn"]
    DriverPrompt["build_prompt(driver)<br/>ROLE + TASK + HISTORY"]
    Driver["driver adapter<br/>codex | claude"]
    Proposal["append proposal"]
    ReviewerPrompt["build_prompt(reviewer)<br/>proposal 포함 HISTORY"]
    Reviewer["reviewer adapter<br/>codex | claude"]
    Critique["append critique"]
    EndCheck{"종료 조건?"}
    Error["append meta<br/>auto-end error"]
    Converged["append meta<br/>auto_end_converged"]
    MaxTurns["append meta<br/>max-turns reached"]
    Next["next turn"]

    CLI --> Session --> Guard --> Logs --> Task --> Loop --> Turn
    Turn --> DriverPrompt --> Driver --> Proposal
    Proposal --> ReviewerPrompt --> Reviewer --> Critique --> EndCheck
    EndCheck -- "fatal error" --> Error
    EndCheck -- "[CONVERGED] streak >= K" --> Converged
    EndCheck -- "turn == max_turns" --> MaxTurns
    EndCheck -- "continue" --> Next --> Loop
```

## 메시지 순서

```text
task
  -> proposal
  -> critique
  -> meta
```

일반적인 한 턴 성공 로그는 다음 순서다.

| 순서 | kind | from | slot | 의미 |
|---|---|---|---|---|
| 1 | `task` | `system` | null | 사용자 task 기록 |
| 2 | `proposal` | `implementer` | `driver` | driver 제안 |
| 3 | `critique` | `spec-reviewer` | `reviewer` | reviewer 검토 |
| 4 | `meta` | `system` | null | 자동 종료 사유 |

## 읽는 순서

1. 현재 실행 흐름: [runtime-docs/systems/run-mode.md](runtime-docs/systems/run-mode.md)
2. 구현 함수 단위: [dev-docs/systems/orchestrator.md](dev-docs/systems/orchestrator.md)
3. 메시지/프로토콜 전체: [runtime-docs/protocol.md](runtime-docs/protocol.md)
4. 모듈 의존 관계: [dev-docs/systems/INDEX.md](dev-docs/systems/INDEX.md)

## 주의

- 이 문서는 요약 지도다. 코드 변경 시 상세 정본을 먼저 갱신하고, 이 문서는 흐름이 바뀐 경우에만 맞춘다.
- `runtime-docs/protocol.md`에는 예정 사양이 포함될 수 있다. 현재 CLI에 노출된 동작은 `runtime-docs/systems/run-mode.md`를 우선한다.
- patch apply 흐름은 `protocol.md`에 사양이 있으나, 현재 `src/orchestrator.py`의 `run_turn`에는 아직 연결되지 않았다.
