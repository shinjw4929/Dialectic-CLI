"""Dijkstra 최단 경로 — scenario seed (수정 시나리오 시작점).

이 파일은 driver가 그래프 시각화(visualize) 함수를 추가하는 대상.
기존 dijkstra 함수는 보존, visualize만 추가됨이 DoD.
"""

import heapq


def dijkstra(graph: dict[str, dict[str, float]], start: str) -> dict[str, float]:
    """인접 리스트 그래프에서 start로부터 모든 노드까지의 최단 거리.

    Args:
        graph: {node: {neighbor: weight}} 형식 인접 리스트
        start: 시작 노드

    Returns:
        {node: shortest_distance} dict. 도달 불가 노드는 float('inf').
    """
    distances = {node: float("inf") for node in graph}
    distances[start] = 0.0
    pq: list[tuple[float, str]] = [(0.0, start)]

    while pq:
        current_dist, current = heapq.heappop(pq)
        if current_dist > distances[current]:
            continue
        for neighbor, weight in graph[current].items():
            new_dist = current_dist + weight
            if new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                heapq.heappush(pq, (new_dist, neighbor))

    return distances


if __name__ == "__main__":
    g = {
        "A": {"B": 1, "C": 4},
        "B": {"C": 2, "D": 5},
        "C": {"D": 1},
        "D": {},
    }
    print(dijkstra(g, "A"))
