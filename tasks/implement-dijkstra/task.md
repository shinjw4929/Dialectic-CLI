# Task — Dijkstra 구현 시나리오 (scratch + 다중 턴 user synthesis)

> 본 도구 thesis "사용자 = synthesis 생성자"를 다중 턴 user synthesis directive로 시연.
> 빈 workdir에서 시작 → driver가 처음부터 작성 → 사용자가 턴마다 후속 directive 주입.

## 1차 task (Turn 1)

```
Python으로 dijkstra 최단 경로 알고리즘을 구현해주세요.
- 인접 리스트 기반 그래프 (dict[str, dict[str, float]])
- heapq 우선순위 큐 사용
- 함수 시그니처: dijkstra(graph, start) -> dict[str, float]
- 도달 불가 노드는 float('inf') 반환
```

## 후속 user synthesis directive (Turn 2+)

critical 모드에서 매 턴 끝 prompt에 다음 directive를 순차 주입 (사용자가 직접 타이핑):

| Turn | directive |
|---|---|
| 2 | `결과를 matplotlib으로 시각화하는 visualize(graph, distances) 함수를 추가해주세요. 노드는 원, 간선은 화살표, 최단 경로 간선은 굵게.` |
| 3 | `노드 색을 최단 거리에 따라 그라데이션 — 가까운 노드는 초록, 먼 노드는 빨강. matplotlib colormap 활용.` |

(원하면 Turn 4 directive로 "테스트 코드도 추가해주세요" 등 추가 가능)

## 실행 명령

```bash
# CLI 직접 호출
dialectic run \
  --task "$(cat tasks/implement-dijkstra/task.md | sed -n '/## 1차 task/,/## 후속/p' | sed '1d;$d')" \
  --interactive critical \
  --max-turns 5

# 또는 메뉴 진입 (default critical)
dialectic
# → 1차 task 본문 paste
# → Turn 2/3 끝 prompt에서 directive 직접 입력
```

## 검증 (DoD)

- [ ] Turn 3 종료 시 workdir 산출에 `dijkstra` + `visualize` + 색 그라데이션 모두 포함
- [ ] `dialectic logs --tail 20`에 turn 1·2·3 각각의 user synthesis decision 메시지 보임 (`kind=decision, from=user`)
- [ ] `patch_applied` 메시지 ≥ 3건 (turn별 1회 이상)
- [ ] 직전 턴 critique이 다음 턴 driver prompt history에 포함 (자동 흡수)

## 시나리오 의도

- user synthesis 다중 턴 wiring (plan 009 산출) 실 시연
- driver의 점진적 enhancement (한 번에 풀 스펙 X, 사용자 피드백으로 진화)
- reviewer가 "충실도(P0/P1) + 일반 결함(P2)" 분리 검출하는지 (ADR-8)
