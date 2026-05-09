# Task — Dijkstra 코드 수정 시나리오 (existing code modification)

> ADR-10 search-replace 메커니즘 시연. driver가 **기존 코드를 보존하면서 수정/추가**하는 흐름.
> seed 파일을 workdir로 복사 후 실행 — 빈 workdir에서 짓는 implement 시나리오와 대비.

## 사전 준비

seed 코드를 workdir로 복사:

```bash
WORKDIR=~/.local/share/dialectic/runs/scenario-modify-$(date +%Y%m%d-%H%M%S)
mkdir -p "$WORKDIR"
cp tasks/modify-dijkstra-add-graph/seed/dijkstra.py "$WORKDIR/"
```

(plan 010 진입 후 `~/.local/share/dialectic/runs/`가 default base_dir. 진입 전이면 `/tmp/scenario-modify/` 등으로 대체)

## task

```
이 workdir에 이미 dijkstra.py가 있습니다 (인접 리스트 기반 dijkstra 함수 1개).
다음을 추가해주세요:

1. visualize(graph, distances) 함수 — matplotlib으로 그래프 시각화.
   노드는 원, 간선은 화살표.
2. 기존 dijkstra 함수는 변경 X — 추가만.
3. 파일 끝의 __main__ 블록에 visualize 호출 1줄 추가.

결과 파일 1개 (dijkstra.py)에 모두 포함.
```

## 실행 명령

```bash
dialectic run \
  --workdir "$WORKDIR" \
  --task "$(cat tasks/modify-dijkstra-add-graph/task.md | sed -n '/## task/,/## 실행/p' | sed '1d;$d')" \
  --max-turns 2
```

(`--interactive end-only` default — 1턴 자동 + 종료 prompt 1회. 다중 턴 directive 시연은 implement-dijkstra 시나리오 책임)

## 검증 (DoD)

- [ ] `$WORKDIR/dijkstra.py`에 기존 `dijkstra` 함수 1:1 보존 (시그니처·body 변경 0)
- [ ] 같은 파일에 `visualize(graph, distances)` 함수 추가
- [ ] `__main__` 블록 끝에 `visualize(g, dijkstra(g, "A"))` 같은 호출 1줄 추가
- [ ] `dialectic logs --kind patch_applied` 결과: `meta.apply_status = "ok"` + `meta.files_changed = ["dijkstra.py"]`
- [ ] `dialectic logs --kind proposal --full` driver raw 응답에 ADR-10 마커 포함:
  ```
  FILE: dijkstra.py
  <<<<<<< SEARCH
  ...
  =======
  ...
  >>>>>>> REPLACE
  ```

## 시나리오 의도

- ADR-10 search-replace 메커니즘 실 시연 (line number 의존 0)
- driver가 기존 코드 변경 X 명세를 따르는지 (충실도 검증)
- patch_apply.py가 search 마커 정확 매칭 + replace 적용 (P-PATCH 회귀 차단)
- 본 도구가 scratch 구현뿐 아니라 **기존 코드 진화** 통로로 작동함을 입증

## 회귀 / 한계

- driver가 search 마커 형식 어긋나게 출력 시 `apply_status = "error"` — 평가 시연 시 1~2회 retry 가능성 명시
- workdir에 기존 파일이 있어도 driver가 그 파일을 prompt에서 못 읽으면 의미 없음 (codex/claude CLI는 cwd 자동 인식 — 본 도구 ADR-6 cwd 격리로 workdir 한정)
