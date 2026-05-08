# Summary · ADR-10 patch_apply 코드 구현

## 의도

driver 응답의 `FILE: ... <<<<<<< SEARCH / ======= / >>>>>>> REPLACE` 블록을 추출해 workdir 파일에 안전하게 적용하는 코드 인프라 구축. modify 시연(Q23=c)이 코드 측면에서 가능해짐.

## 배경 / 동기

- ADR-10 (Q22 ✅ A2): outline·protocol·systems/ 5중 결정 도장 + cascade 완수 (선행 plan 004)
- 그러나 실 코드는 0 — `src/patch_apply.py` 부재, `src/orchestrator.run_turn`은 R2 → R3 직결로 R2.6/R2.7 단계 미실현
- modify 데모 자체 불가능한 상태에서 본 plan이 코드 GAP 메움

## Phase 흐름

```
A · Schema (Meta 14→18 필드)   ─┐
                                ├─→ C · Orchestrator (R2.6/R2.7 통합)
B · Patch Apply (extract/apply) ─┘
```

A·B 병렬 (서로 import 의존 0) → C 직렬 (A의 Meta 신 필드 + B의 함수 둘 다 사용).

## 핵심 의사결정

- **Meta 4 필드 default=None** (phase-a) — 어댑터/SENTINEL_META/기존 6 테스트 회귀 0 보장
- **`validate_patch_path` 정통 코드 위치 = `src/patch_apply.py`** (phase-b) — cwd-isolation.md:55-72 SSOT는 spec만 코드 0이라 본 plan이 첫 코드 구현. 시그니처·동작 SSOT 1:1 (P1-4 fix 대응)
- **all-or-nothing 트랜잭션 + unique-match 정책** (phase-b) — SEARCH가 파일에 N>1회 나타나면 ambiguous, PatchApplyError. partial 폐기
- **patch_applied seq_in_turn=98** (phase-c) — 시간 순(turn 내 발생)은 reviewer 앞, 직렬화 순(`(turn_id, seq_in_turn)` 정렬)은 reviewer 뒤. 비대칭은 의도적 — 강조 효과 ↑. driver 오인 risk는 content prefix(`apply_status=...`)로 차단
- **Windows native 검증 deferred** (phase-b §6) — `Path.resolve()` symlink 처리 OS 차이. 본 plan은 Linux/WSL만, Windows는 별도 plan(`006-windows-native-support`) backlog

## 핵심 위험

- **Meta 필드 default=None 누락** — 어댑터·SENTINEL_META·6 테스트 모두 break. Phase A DoD에 회귀 검증 명시
- **SSOT 균열** — `cwd-isolation.md:55-72` `validate_patch_path` SSOT 시그니처와 plan 구현이 어긋나면 spec ↔ code 균열. **함수명·인자·반환 1:1 paste + SSOT 1:1 단위 테스트(`test_validate_patch_path_ssot`)로 차단** (P1-4 결정)
- **R-001 P-ENCODING** — 신규 read_text/write_text는 `encoding="utf-8"` 명시 필수 (위반 P0 review-code 차단)
- **다중 매치 모호성** — SEARCH 본문이 파일에 2회 이상 → 어느 위치 치환할지 미정. unique-match 강제로 차단 (P1-3 결정)

## DoD 요약

- [ ] (Phase A) Meta 4 필드 추가 + `pytest tests/test_schema.py -q` pass + 기존 6 파일 회귀 0
- [ ] (Phase B) `src/patch_apply.py` + `tests/test_patch_apply.py` (11 케이스) pass — `validate_patch_path`은 cwd-isolation SSOT 정통 구현 위치
- [ ] (Phase C) `run_turn` R2.6/R2.7 통합 + `tests/test_orchestrator_patch_integration.py` (2 케이스) pass + 전체 8 파일 회귀 0
- [ ] sync-docs cascade — `dev-docs/systems/jsonl-bus.md §schema` (Meta 18 필드) + `dev-docs/systems/orchestrator.md` (R2.6/R2.7 narrative) + `runtime-docs/systems/run-mode.md` (turn lifecycle 갱신) + README (지원 플랫폼 + 006-windows backlog 가시화)
- [ ] review-code P0 = 0 (R-001 encoding 포함)

→ 상세: [01-plan.md](01-plan.md), Phase별 [phase-a-schema.md](phase-a-schema.md) · [phase-b-patch-apply.md](phase-b-patch-apply.md) · [phase-c-orchestrator.md](phase-c-orchestrator.md)
