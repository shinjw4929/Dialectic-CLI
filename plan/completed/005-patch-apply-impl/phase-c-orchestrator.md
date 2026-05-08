# Phase C · Orchestrator R2.6/R2.7 통합 (run_turn turn loop) — 005-patch-apply-impl

## 0. 메타

- Phase ID: C
- 소속 plan: [01-plan.md](01-plan.md)
- 의존 Phase: A (Meta 4 필드 default=None) + B (`extract_patches` / `apply_patches` / `PatchApplyError`)
- 병렬 그룹: — (A·B 둘 다 완료 후 직렬)
- 예상 LOC: 코드 ~30 / 테스트 ~30 (`tests/test_orchestrator_patch_integration.py` 신규 — R2.6/R2.7 진입 단언 monkeypatch 기반 통합 테스트 2 케이스)

## 1. 목표

`src/orchestrator.py` `run_turn` driver 분기에 protocol.md §4 line 232-235 mermaid가 정의한 **R2.6 apply_patches → R2.7 patch_applied append** 단계를 통합. proposal `meta.patches`는 bus.append 시점에 `dataclasses.replace`로 채움 (P-JSONL append-only). patch 0개면 R2.6/R2.7 skip. apply 결과(성공·실패)는 별도 `kind=patch_applied` 메시지로 append, 다음 턴 driver prompt에 자연 피드백.

## 2. 입력

- Phase A 산출 — `src/schema.py` `Meta`에 patches / apply_status / apply_error / files_changed 4 필드 (default=None)
- Phase B 산출 — `src/patch_apply.py`에 `extract_patches`, `apply_patches`, `PatchApplyError`
- `docs/runtime-docs/protocol.md:226-248` — 턴 라이프사이클 mermaid (R2 → R2.6 → R2.7 → R3)
- `docs/runtime-docs/protocol.md:121` — `kind=patch_applied`의 from=`system` 명세
- `src/orchestrator.py:312-316` — proposal append 진입점 (수정 대상)
- `src/orchestrator.py:52-71` — `SENTINEL_META` 헬퍼 (재사용 + `dataclasses.replace`로 신 필드 채움)
- `src/orchestrator.py:99-100` — `_serialize_history`의 `from_=="system"` 분기 (patch_applied content 자연 시리얼라이즈 — 수정 불요)
- `src/orchestrator.py:46` — `META_SEQ_SENTINEL = 99` (patch_applied seq 결정 기준)
- 사전 검증된 사실:
  - `dataclasses.replace`은 frozen dataclass에 대해 새 인스턴스 생성 — 기존 `:350-352` convergence_streak 패턴 재사용 가능.
  - `_serialize_history`의 system 분기(`SYSTEM (kind): content`)는 patch_applied content가 사람이 읽을 수 있는 문자열이면 driver prompt에 자연 노출 — apply_error 피드백 별도 inject 불요.

## 3. 출력

### 3.1 `src/orchestrator.py` 변경 (수정)

**(1) import 추가** (`:30` 근처):

```python
# spec
from .patch_apply import apply_patches, extract_patches
```

**(2) `_patch_applied_msg` 헬퍼 신규** (`_meta_msg` 함수 바로 위 또는 아래, `:243` 부근):

```python
# spec
def _patch_applied_msg(
    turn_id: int,
    workdir: Path,
    mode: str,
    content: str,
    *,
    parent_id: str,
    apply_status: str,
    apply_error: str | None,
    files_changed: list[str],
) -> Message:
    """R2.7 patch_applied 메시지 — from=system, slot=None, seq=98 (proposal=1, reviewer=2 사이 + meta=99 직전).

    content는 호출자(run_turn)가 만든 요약 문자열 — `_serialize_history`의 system 분기(:99-100)
    `SYSTEM (patch_applied): {content}` 형태로 driver 다음 턴 R1 prompt에 자연 피드백.
    호출자가 prefix를 `apply_status=...`로 명시하여 driver의 reviewer critique 오인 risk 차단
    (01-plan §5.6 (2) mitigation).

    meta는 SENTINEL_META + dataclasses.replace로 apply_status/apply_error/files_changed 채움.
    """
```

**(3) `run_turn` driver 분기 수정** (`:312-316`):

AS-IS:
```python
proposal = _msg(
    turn_id, 1, driver_role, "driver", mode, "proposal",
    resp1.text, parent_id=last_msg_id, meta=resp1.meta,
)
bus.append(proposal)
```

TO-BE:
```python
# spec
patches = extract_patches(resp1.text)
proposal_meta = dataclasses.replace(resp1.meta, patches=patches or None)
proposal = _msg(
    turn_id, 1, driver_role, "driver", mode, "proposal",
    resp1.text, parent_id=last_msg_id, meta=proposal_meta,
)
bus.append(proposal)

if patches:  # patch 0이면 R2.6/R2.7 skip — 노이즈 차단
    status, error, files_changed = apply_patches(patches, workdir)
    summary = (
        f"apply_status={status}, files_changed={files_changed}"
        if status == "ok"
        else f"apply_status=failed, apply_error={error}"
    )
    bus.append(_patch_applied_msg(
        turn_id, workdir, mode, summary,
        parent_id=proposal.msg_id,
        apply_status=status,
        apply_error=error,
        files_changed=files_changed,
    ))
```

`summary` 변수가 `content` 위치 인자로 전달됨 — helper는 `Message(content=content, ...)`로 그대로 박음. driver prompt에서 의미적으로 자연 읽힘 (`SYSTEM (patch_applied): apply_status=failed, apply_error=search not found in wave_difficulty.py`). prefix `apply_status=...`로 reviewer critique 오인 차단 (01-plan §5.6 (2) mitigation). 별도 prompt build 변경 0.

**(4) seq_in_turn 결정**: `_patch_applied_msg` 내부에서 `seq_in_turn=META_SEQ_SENTINEL - 1` (=98). proposal=1 / patch_applied=98 / reviewer=2 — turn 내 시간 순은 proposal → patch_applied → reviewer지만 seq_in_turn은 정렬 단조성 X. `_serialize_history`(`:91`)는 `(turn_id, seq_in_turn)` 정렬 — 이 경우 proposal(1) → reviewer(2) → patch_applied(98) 순서로 직렬화됨. 시간 순서와 직렬화 순서 차이.

**대안 검토**:
- (a) reviewer를 seq=3으로 옮기고 patch_applied=2 — 기존 테스트는 reviewer.seq_in_turn 단언 0이라 회귀 미감지. 본 plan 신규 통합 테스트에서 `critique.seq_in_turn == 2`가 회귀 가드 (01-plan §5.6 (1)).
- (b) patch_applied seq=98 (현 안) — 직렬화 순서가 시간 순과 어긋나지만 driver 다음 턴 prompt에서 system 메시지로 직렬화 끝부분에 노출 → 마지막에 강조되어 driver가 더 잘 캐치 가능. 위 (a) 대비 회귀 위험 0.
- 채택: (b). 회귀 0 우선. 작업 단위에 reviewer seq 검증 테스트가 깨지지 않음을 명시.

### 3.2 테스트 — 회귀 검증 + 신규 통합 테스트 (P1-X2 fix)

- **신규 통합 테스트 필수**: `tests/test_orchestrator_patch_integration.py` (~30 LOC). monkeypatch로 `_resolve_runner`를 가짜 runner로 교체 — driver 응답 텍스트에 search-replace 블록 포함, reviewer는 빈 critique. `run_turn(...)` 호출 후 단언:
  - bus 라인 3개 (proposal seq=1, patch_applied seq=98, critique seq=2) — **`assert critique.seq_in_turn == 2` + `assert patch_applied.seq_in_turn == 98`** 명시 단언으로 01-plan §5.6 (1) mitigation 회귀 가드 역할 (reviewer seq 변경 시 즉시 fail)
  - **`assert patch_applied.content.startswith("apply_status=")`** 명시 단언 — 01-plan §5.6 (2) mitigation (driver 오인 차단 prefix) 검증 가드. helper가 prefix 없이 content 채우면 즉시 fail
  - workdir 대상 파일 내용이 REPLACE로 치환됨
  - proposal.meta.patches가 1 dict + patch_applied.meta.apply_status="ok" + files_changed 1 entry
  - failure 케이스 (FILE 외부 경로): apply_status="failed", workdir 파일 미변경
- 회귀: 기존 6 테스트 + Phase B의 test_patch_apply.py + 본 통합 테스트 = `tests/` 전체 8 파일 pass.

## 4. 작업 단위

- [ ] `src/orchestrator.py` import 영역에 `from .patch_apply import apply_patches, extract_patches` 추가
- [ ] `_patch_applied_msg` 헬퍼 함수 신규 — `_meta_msg`(`:219-243`) 직후에 배치
- [ ] 헬퍼 내부에서 `SENTINEL_META(workdir)` → `dataclasses.replace(meta, apply_status=..., apply_error=..., files_changed=...)` 패턴으로 4 필드 중 3개 채움 (patches는 proposal 측 책임이라 None 유지)
- [ ] `run_turn` (`:312-316`) — proposal 생성 직전에 `extract_patches` 호출 + `dataclasses.replace`로 proposal_meta에 patches 채움
- [ ] proposal `bus.append` 직후 `if patches:` 분기 — `apply_patches` 호출 + `_patch_applied_msg` 생성 + `bus.append`
- [ ] content summary 문자열 — apply_status=ok 시 `f"apply_status=ok, files_changed={files_changed}"` (prefix `apply_status=` 명시 — driver의 reviewer critique 오인 차단), failed 시 `f"apply_status=failed, apply_error={error}"` (driver 자연 피드백). `_patch_applied_msg` 시그니처에 `content` 위치 인자 4번째로 전달
- [ ] reviewer 분기(`:318-`) 변경 0 — workdir 파일이 이미 변경된 상태이므로 reviewer prompt build는 변경된 파일 내용을 자연 인지 (driver 응답이 SEARCH/REPLACE 블록을 직접 포함하므로 prompt에도 노출됨 — 이중 인지)
- [ ] **`tests/test_orchestrator_patch_integration.py` 신규 작성** — monkeypatch로 가짜 runner 주입, run_turn 호출 후 (a) bus 3 라인 + **`critique.seq_in_turn == 2` / `patch_applied.seq_in_turn == 98` 단언 (§5.6 (1) 회귀 가드)** + **`patch_applied.content.startswith("apply_status=")` 단언 (§5.6 (2) prefix 가드)** (b) workdir 파일 변경 (c) meta.patches·apply_status 단언. 2 케이스 (happy + traversal failure)
- [ ] `pytest tests/ -q` 전체 8 파일 (기존 6 + test_patch_apply.py + test_orchestrator_patch_integration.py) pass

## 5. 검증

- `python -c "from src.orchestrator import run_turn, _patch_applied_msg; from src.patch_apply import extract_patches, apply_patches, validate_patch_path"` import smoke 성공.
- `pytest tests/test_orchestrator_patch_integration.py -q` 2 케이스 pass — R2.6/R2.7 진입 단언 (monkeypatch 기반 단위 테스트로 mock 어댑터 부재 우회).
- `pytest tests/ -q` 8 파일 모두 pass — 본 plan 신규 `test_orchestrator_patch_integration.py`의 `assert critique.seq_in_turn == 2` 단언이 reviewer seq 변경에 대한 유일한 회귀 가드 (01-plan §5.6 (1) mitigation). 기존 `test_orchestrator_converge.py`(5 함수: `test_detect_converged_*` ×3 + `test_run_session_adr9_*` ×2)는 reviewer.seq_in_turn 단언 0건.
- `dialectic run --task "..." --max-turns 1 --workdir /tmp/test_005` 실행 시 (driver 응답에 patch 블록이 없으면) `messages.jsonl`에 patch_applied 라인 0 — 노이즈 차단 확인.

## 6. 엣지케이스 / 위험 (Phase 한정)

- **patch 0개 vs proposal.meta.patches**: `patches or None` — 빈 리스트 → None. JSONL 라인에 `"patches": null` 명시. 일관성 유지 (01-plan.md §5.4 결정).
- **same-turn에 driver가 patches + reviewer 응답 동시 평가**: reviewer가 변경된 파일을 보고 critique 작성 — 이미 변경 후 상태이므로 reviewer가 "이전 상태"를 reference하지 못함. 의도된 동작 (protocol.md §4 line 236 "변경된 파일 내용 재주입"). reviewer가 원본을 알아야 한다면 driver가 응답 텍스트에 SEARCH 블록을 명시했으므로 prompt에 이미 들어감.
- **dataclasses.replace + slots**: orchestrator.py:350-352에서 이미 사용 중인 패턴 — frozen+slots dataclass 호환성 확인 완료. 재사용 안전.
- **patch_applied 메시지의 token 메타**: SENTINEL_META는 token 4종 0, cost None — 정직성. apply는 subprocess 호출 0이라 token 0 자연. is_mock=False (orchestrator system 메시지 — mock 라벨 부적절). meta.workdir 채움.
- **directive 누락**: patch_applied가 directive=None — system 메시지라 자연. `_serialize_history`(`:99-100`)에서 directive 무시 분기 사용.
- **seq_in_turn=98 직렬화 순서 부작용**: §3.1 (4)에서 채택한 안. `_serialize_history`가 patch_applied를 reviewer 뒤에 직렬화 — driver의 다음 턴 prompt에서 patch_applied가 그 turn 마지막 메시지로 노출되어 강조됨. 의도된 효과 (driver의 apply_error 피드백 캐치 ↑). 본 효과를 §3.1에 명시 채택 근거로 둠.
- **error 분기와 patch 처리 순서**: driver 응답이 빈 문자열이거나 except로 catch될 때(`:286-296`, `:298-310`)는 `_error_msg` append 후 즉시 return — patches 처리 진입 0. 이미 안전.
- **workdir 외부 patch 처리**: apply_patches 내부에서 PatchApplyError → status="failed" 환원 → `_patch_applied_msg`에 apply_error 채움. orchestrator 측에서 별도 가드 불요 (B Phase가 책임 흡수).
