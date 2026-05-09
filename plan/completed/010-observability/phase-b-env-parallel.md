# Phase B · env_check 병렬화 — 010-observability

## 0. 메타

- Phase ID: B
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: A·B·C 모두 의존성 0 — execute-plan 동시 분기 후보
- 예상 LOC: ~30 LOC + 테스트 ~15 LOC

## 1. 목표

`check_env`의 4개 sub-check sequential 호출을 `concurrent.futures.ThreadPoolExecutor`로 병렬화 — 메뉴 진입 spinner wall clock을 직렬 합(worst 30s)에서 max(개별 timeout)(worst 10s) 수준으로 축소. 결과 dict 구조·출력 순서는 변경 X (사용자 표 안정성).

## 2. 입력

- `src/env_check.py:40-62` — `check_env` AS-IS (4 sub-check sequential dict 구성)
- `src/env_check.py:64-86` — `_run_capture` AS-IS (subprocess wrapper, 시그니처 변경 X)
- `src/env_check.py:1-8` — `claude doctor` 영구 제외 narrative (validation.md §4.4 P-VENDOR)
- `docs/dev-docs/systems/env-check.md` — env-check SSOT (Phase 갱신 대상)
- `docs/dev-docs/code-conventions.md §3` (`:31-58`) — subprocess `cwd=` 명시 + 화이트리스트 규약
- 사전 검증된 사실: `concurrent.futures` 표준 라이브러리 (외부 의존성 0)
- 사전 검증된 사실: 본 plan 시점 sub-check 4개 (claude × {version, auth} + codex × {version, login}) — `claude doctor` 제외됨

## 3. 출력

### 3.1 변경 파일

- `src/env_check.py:40-62` `check_env` — 병렬 호출로 재작성:
  ```python
  # spec
  def check_env() -> dict[str, dict[str, dict[str, Any]]]:
      """4개 sub-check 병렬. 결과 dict는 원래 insertion 순서로 재조립.
      외부 의존성 0 — concurrent.futures.ThreadPoolExecutor 사용.
      _safe_env()는 함수 진입 시 1회 계산하여 4 future에 공유 (thread-safety: 읽기 전용
      dict 전달이라 race 없음). 4 future 각각 _run_capture 호출.
      """
      # 1. env_pass = _safe_env()  — 1회 계산, 4 future 공유
      # 2. (tool, sub, cmd, timeout) 4튜플 list 정의 — 순서 = 출력 순서
      # 3. with ThreadPoolExecutor(max_workers=4) as ex:
      #        results = list(ex.map(lambda t: _run_capture(t.cmd, env_pass, t.timeout), specs))
      #    executor.map은 입력 순서로 결과 산출 — 별도 재정렬 불필요
      # 4. zip(specs, results)로 {tool: {sub: result}} dict 재조립
      #    (claude/codex 그룹화, dict insertion 순서 = 입력 순서)
  ```
- `_run_capture` 시그니처 변경 X — 호출만 병렬화

### 3.2 신규 테스트

- `tests/test_env_check_parallel.py` (신규, ~15 LOC)
  - `unittest.mock.patch("src.env_check._run_capture")`로 sleep 1s + ok=True 반환 stub 주입 → 4 sub-check 직렬 합 4s 대비 병렬 wall clock ≤ 1.5s 단언
  - 결과 dict key 순서 = `["claude", "codex"]`, 각 그룹 sub key 순서 (claude={version,auth}, codex={version,login}) 단언
  - `_run_capture` stub이 1개 sub-check만 timeout 결과 반환 시 다른 3개 정상 반환 단언 (병렬 독립성)

## 4. 작업 단위

- [ ] `src/env_check.py:check_env` 병렬 재작성 (4 튜플 list + ThreadPoolExecutor + 재정렬 + 그룹화)
- [ ] `_safe_env` / `_run_capture` 변경 X (호출자만 변경)
- [ ] `tests/test_env_check_parallel.py` 신규 단언 3건
- [ ] `docs/dev-docs/systems/env-check.md` "병렬 호출 narrative" 단락 추가 + 측정 결과 인용
- [ ] `src/env_check.py:1-8` 모듈 docstring에 "병렬 호출" 한 줄 추가 (sync-docs cascade)

## 5. 검증

- `pytest tests/test_env_check_parallel.py -q` pass
- 실측: `time python -c "from src.env_check import check_env; print(check_env())"` wall clock ≤ 12s (이전 직렬 worst 30s 대비)
- 실측: `check_env()` 반환 dict의 sub-check 4건 insertion 순서 = claude/version → claude/auth → codex/version → codex/login (`dialectic doctor`의 stdout은 tool 헤더 2줄 + sub 4줄 = 6줄, 단언 대상은 dict 순서)

## 6. 엣지케이스 / 위험 (Phase 한정)

- **결과 순서 보존**: `executor.map`은 입력 순서로 yield하므로 별도 재정렬 불필요. `as_completed` 사용 시는 완료 순서가 비결정 → 입력 인덱스 매핑 필수. spec은 `executor.map` 채택
- **ThreadPoolExecutor 컨텍스트 매니저 누락**: `with` 사용해 자원 누수 차단
- **subprocess timeout 동시성**: 4개 동시에 timeout 도달해도 각 future 독립 — 중첩 영향 X (subprocess는 process-level)
- **stdout/stderr 절단 길이 _OUTPUT_TRUNCATE_CHARS=200 유지**: dict 결과 형식 동일 (사용자 가시 변경 X)
- **macOS·WSL 차이**: ThreadPoolExecutor는 표준 라이브러리, OS 영향 없음. 본 도구 가정 환경 (WSL/Linux) 정합
- **claude doctor 재추가 유혹**: validation.md §4.4 P-VENDOR 결정 유지 — 본 plan 범위 외
