# Execution Log · 005-patch-apply-impl

## Phase A · Schema (Meta 4 필드 확장) — 병렬 with B

- 입력 phase 파일: `phase-a-schema.md`
- 산출물:
  - `src/schema.py` (+5 LOC: 주석 1 + Meta 4 필드 default=None)
  - `tests/test_schema.py` (+139 LOC: 4 신규 함수 + 헬퍼)
- Meta 필드: 14 → 18 (`patches` / `apply_status` / `apply_error` / `files_changed` 추가, insertion order 마지막)
- 검증:
  - `python -c "from src.schema import Meta; ..."` smoke OK (18 필드 확인)
  - `pytest tests/test_schema.py -q` 7 passed (기존 3 + 신규 4)
  - `pytest tests/ -q` 21 passed + 1 deselected (회귀 0)
- 라벨 준수: §3.1 paste 4 필드 1:1 / §3.2 테스트 함수명 paste / 본문 spec
- 발견 이슈: 없음

## Phase B · Patch Apply 모듈 — 병렬 with A

- 입력 phase 파일: `phase-b-patch-apply.md`
- 산출물:
  - `src/patch_apply.py` (신규, 176 LOC — 추정 ~70 대비 보강: best-effort 롤백 + stderr 경고 + relative path 환원)
  - `tests/test_patch_apply.py` (신규, 267 LOC — 11 케이스)
- 공개 인터페이스: `validate_patch_path` / `extract_patches` / `apply_patches` / `PatchApplyError`
- 검증:
  - `python -c "from src.patch_apply import ..."` smoke OK
  - `pytest tests/test_patch_apply.py -q` 11 passed
  - `pytest tests/ -q` 32 passed + 1 deselected (Phase A까지 누적, 회귀 0)
- 검증 매트릭스 (phase-b §6 엣지케이스 모두 케이스 매핑):
  - traversal `../etc/passwd` / 절대경로 / symlink escape (Linux/WSL)
  - SEARCH count==0 / count>1 (ambiguous) / 빈 SEARCH 차단
  - multi-file all-or-nothing 롤백
  - validate_patch_path SSOT 시그니처 1:1 (cwd-isolation.md:55-72)
  - 정규식 non-greedy 다중 블록 / SEARCH 본문 빈 줄 / 마커 부재
- R-001 P-ENCODING 준수: `read_text` / `write_text` 4 호출 위치 모두 `encoding="utf-8"` 명시
- 라벨 준수: paste 영역(정규식 마커 카운트·named group·`\S+`·SSOT 시그니처) 1:1, 함수 본문 spec 자유 구현
- 발견 이슈: 없음 (공백 포함 파일 경로는 §6 정책대로 비지원, `\S+` 매칭 실패 → "search not found" 환원 자연 처리)

## Phase C · Orchestrator R2.6/R2.7 통합 — 직렬 (A·B 의존)

- 입력 phase 파일: `phase-c-orchestrator.md`
- 산출물:
  - `src/orchestrator.py` (수정, +62 LOC, 458 → 520):
    - `:30` import 추가 (`from .patch_apply import apply_patches, extract_patches`)
    - `:246-289` `_patch_applied_msg` 헬퍼 신규 (44 LOC, seq=98, SENTINEL_META + dataclasses.replace)
    - `:354-376` `run_turn` driver 분기 — `extract_patches` → `dataclasses.replace`로 proposal_meta에 patches → `if patches:` 분기에서 `apply_patches` + summary + `_patch_applied_msg` append. summary prefix `apply_status=` 명시
  - `tests/test_orchestrator_patch_integration.py` (신규, 165 LOC, 2 케이스):
    - case 1 (happy): proposal/patch_applied/critique 3 메시지 + §5.6 (1)(2) 가드 단언
    - case 2 (traversal failure): `FILE: ../etc/passwd` → apply_status=failed + workdir 미변경
- 검증:
  - import smoke OK
  - `pytest tests/test_orchestrator_patch_integration.py -q` 2 passed
  - `pytest tests/ -q` 8 파일 34 passed + 1 deselected (회귀 0 — 특히 `test_orchestrator_converge.py` 5 함수 모두 pass)
- §5.6 mitigation 가드 단언:
  - (1) seq 회귀: `critique.seq_in_turn == 2` + `patch_applied.seq_in_turn == 98`
  - (2) driver 오인: `patch_applied.content.startswith("apply_status=")` (양 분기)
- 발견 이슈:
  - `python` 미존재 → `.venv/bin/pytest` 사용 (CI/사용자 동일 path 권장)
  - 가짜 AgentRunner 주입을 monkeypatch 대신 `run_turn` keyword-only 인자(`driver_runner`/`reviewer_runner`)로 직접 주입 — 더 간결, monkeypatch leak 0

## DoD 체크 (01-plan §6)

| 항목 | 상태 |
|---|---|
| (Phase A) Meta 4 필드 default=None | ✓ |
| (Phase A) test_schema.py 4 함수 추가 | ✓ |
| (Phase A) pytest pass + 회귀 0 | ✓ |
| (Phase B) src/patch_apply.py 4 인터페이스 | ✓ |
| (Phase B) test_patch_apply.py 11 케이스 | ✓ |
| (Phase B) pytest pass | ✓ |
| (Phase C) run_turn R2.6/R2.7 통합 | ✓ |
| (Phase C) proposal meta.patches dataclasses.replace | ✓ |
| (Phase C) _patch_applied_msg + content 인자 | ✓ |
| (Phase C) pytest 8 파일 pass | ✓ |
| (전체) Q22 ↔ ADR-10 ↔ protocol.md ↔ 코드 5중 일관 | ✓ |
| (전체) systems/jsonl-bus.md §schema 갱신 | ⏳ 후속 sync-docs |
| (전체) systems/orchestrator.md 갱신 | ⏳ 후속 sync-docs |
| (전체) runtime-docs/systems/run-mode.md 갱신 | ⏳ 후속 sync-docs |
| (전체) README 지원 플랫폼 갱신 | ⏳ 후속 sync-docs |
| (전체) sync-docs 호출 | ⏳ 본 단계 |
| (전체) validation.md §3 후보 검토 | ⏳ 사용자 판단 |
| (전체) review-code P0=0 | ⏳ 사용자 판단 |
| (전체) review-plan P0=0 | ✓ (5 라운드 통과) |
