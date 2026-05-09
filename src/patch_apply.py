"""ADR-10 search-replace patch — extract + safe apply.

protocol.md §2 line 85-91 (patches/apply_status/...) + §4 line 232 R2.6 (all-or-nothing) +
§9 line 359-361 (실패 3행) 정합. orchestrator는 본 모듈의 두 공개 함수만 호출.

표준 라이브러리만 (re, pathlib.Path) — code-conventions §2.
"""

import re
import sys
from pathlib import Path

# protocol.md §2 line 86 patches dict 형식 + role implementer.md:78 마커 형식
# 마커 카운트 7-character (`<<<<<<<` / `=======` / `>>>>>>>`) + named groups
# (`file` / `search` / `replace`)는 ADR-10 명세 1:1 — 변형 금지.
# 정책: file 경로는 `\S+` (공백 포함 경로 비지원) — driver 응답 형식이 한 줄 헤더이고
# 공백 포함 파일명은 본 도구 사용 사례에 부재 (Python 코드베이스 기준).
# 주의: `FILE: my file.py`처럼 공백 포함 헤더는 패턴 자체가 매칭 실패 → 해당 블록은
# extract_patches 결과에 미포함 (silent 누락). driver 측 self-check 책임 (role implementer.md:78).
# 향후 인용 형식(`FILE: "<path>"`) + 형식 위반 명시 에러는 별도 plan으로 deferred.
_PATCH_PATTERN = re.compile(
    r"FILE:\s*(?P<file>\S+)\s*\n"
    r"<{7}\s*SEARCH\s*\n"
    r"(?P<search>.*?)"
    r"\n={7}\s*\n"
    r"(?P<replace>.*?)"
    r"\n>{7}\s*REPLACE",
    re.DOTALL,
)


class PatchApplyError(Exception):
    """내부 시그널 — apply_patches 외부에는 (status, error, files_changed) 튜플로 환원.

    path traversal / SEARCH 미일치 / SEARCH 다중 매치 / IO 실패 단일 catch 가능."""


def validate_patch_path(workdir: Path, file: str) -> Path:
    """cwd-isolation.md:55-72 §Layer 4 SSOT 정통 구현 (이전엔 spec만, 코드 부재).

    cwd-isolation.md:64 spec 1:1:
    1. Path(workdir).resolve() / Path(file) 결합 → .resolve()로 정규화
    2. 결과가 workdir.resolve()의 자손인지 .is_relative_to() 검사
    3. symlink escape도 strict=False resolve 후 동일 prefix 검사
    4. 외부면 PatchApplyError("path outside workdir: " + file)
    """
    workdir_resolved = Path(workdir).resolve()
    # strict=False — 아직 존재하지 않는 파일도 허용 (commit write 단계에서 생성될 수 있음).
    # 그러나 본 모듈은 SEARCH 매칭이 전제이므로 사실상 read 단계에서 존재해야 함.
    candidate = (workdir_resolved / Path(file)).resolve()
    if not candidate.is_relative_to(workdir_resolved):
        raise PatchApplyError("path outside workdir: " + file)
    return candidate


def extract_patches(text: str) -> list[dict[str, str]]:
    """driver 응답 텍스트에서 search-replace 블록 추출.

    반환 각 dict: {"file": str, "search": str, "replace": str}. 매칭 0개면 [].
    non-greedy + re.DOTALL — 한 응답에 여러 블록 가능.
    """
    patches: list[dict[str, str]] = []
    for match in _PATCH_PATTERN.finditer(text):
        patches.append(
            {
                "file": match.group("file"),
                "search": match.group("search"),
                "replace": match.group("replace"),
            }
        )
    return patches


def apply_patches(
    patches: list[dict[str, str]], *, workdir: Path
) -> tuple[str, str | None, list[str]]:
    """all-or-nothing 트랜잭션으로 patches를 workdir에 적용.

    반환: (status, error, files_changed)
    - status="ok" / error=None / files_changed=[변경된 상대 경로]
    - status="failed" / error=사유 / files_changed=[]

    절차 (phase-b §4 작업 단위 (1)~(4)):
    1) path validation — validate_patch_path SSOT
    2) 빈 SEARCH 차단 — 파일 존재 시. 파일 부재 시 신규 파일 의도로 (3)에 위임 (plan 014 Phase D)
    3) dry-run — 한 번 read + in-memory 누적 치환 + count==0/count>1 검사
                 신규 파일 (resolved.exists() == False)은 originals="" 등록 + new_files set 추적
    4) commit — write_text. 신규 파일은 parent mkdir 후 write.
                IO 실패 시 originals 백업으로 best-effort 복원 (신규 파일은 unlink)
    """
    try:
        # (1) path validation — 모든 patch에 대해 먼저 검증
        resolved_paths: list[Path] = []
        for patch in patches:
            resolved_paths.append(validate_patch_path(workdir, patch["file"]))

        # (2) 빈 SEARCH 차단 (파일 존재 시) — 부재 시 신규 파일 의도로 (3) 위임
        for patch, resolved in zip(patches, resolved_paths):
            if not patch["search"] and resolved.exists():
                raise PatchApplyError(
                    "empty SEARCH not allowed in " + patch["file"]
                )

        # (3) dry-run — 각 파일 한 번 read, in-memory 누적 치환
        originals: dict[Path, str] = {}
        mutated: dict[Path, str] = {}
        new_files: set[Path] = set()  # rollback unlink 식별용 (plan 014 Phase D)
        # 입력 순서대로 patch 처리 (multi-patch same-file 순서 의존 가시화)
        for patch, resolved in zip(patches, resolved_paths):
            if resolved not in originals:
                if resolved.exists():
                    # 기존 파일 — R-001 P-ENCODING (encoding="utf-8" 명시 필수)
                    original_text = resolved.read_text(encoding="utf-8")
                    originals[resolved] = original_text
                    mutated[resolved] = original_text
                else:
                    # 신규 파일 의도 — SEARCH=""인 patch만 도달 (위 (2) 정합)
                    originals[resolved] = ""
                    mutated[resolved] = ""
                    new_files.add(resolved)

            search = patch["search"]
            current = mutated[resolved]
            if not search:
                # 신규 파일 + SEARCH="" — REPLACE 본문을 mutated에 등록
                mutated[resolved] = patch["replace"]
                continue
            count = current.count(search)
            if count == 0:
                raise PatchApplyError(
                    "search not found in " + patch["file"]
                )
            if count > 1:
                raise PatchApplyError(
                    "ambiguous match: search appears "
                    + str(count)
                    + " times in "
                    + patch["file"]
                )
            mutated[resolved] = current.replace(search, patch["replace"], 1)

        # (4) commit — write 누적 결과. IO 실패 시 originals 백업으로 복원
        written: list[Path] = []
        files_changed: list[str] = []
        try:
            # 변경된 파일만 write (in-memory 결과가 원본과 다른 경우)
            for resolved in originals:
                if mutated[resolved] != originals[resolved]:
                    if resolved in new_files:
                        # 신규 파일 — parent dir 보장 (plan 014 Phase D)
                        resolved.parent.mkdir(parents=True, exist_ok=True)
                    # R-001 P-ENCODING
                    resolved.write_text(mutated[resolved], encoding="utf-8")
                    written.append(resolved)
                    # workdir 기준 상대 경로 보고
                    workdir_resolved = Path(workdir).resolve()
                    try:
                        rel = resolved.relative_to(workdir_resolved)
                        files_changed.append(str(rel))
                    except ValueError:
                        files_changed.append(str(resolved))
        except OSError as exc:
            # best-effort 롤백 — 신규 파일은 unlink, 기존 파일은 originals 복원
            rollback_failures: list[str] = []
            for resolved in written:
                try:
                    if resolved in new_files:
                        resolved.unlink()
                    else:
                        resolved.write_text(originals[resolved], encoding="utf-8")
                except OSError as restore_exc:
                    rollback_failures.append(
                        str(resolved) + ": " + str(restore_exc)
                    )
            failed_file = next(
                (
                    p["file"]
                    for p, r in zip(patches, resolved_paths)
                    if r not in written
                ),
                patches[0]["file"] if patches else "<unknown>",
            )
            msg = "io error on " + failed_file + ": " + str(exc)
            if rollback_failures:
                # stderr 경고 (best-effort 신호)
                sys.stderr.write(
                    "patch_apply: rollback failed for "
                    + ", ".join(rollback_failures)
                    + "\n"
                )
                msg += " (rollback also failed: " + "; ".join(rollback_failures) + ")"
            raise PatchApplyError(msg) from exc

        return ("ok", None, files_changed)

    except PatchApplyError as exc:
        return ("failed", str(exc), [])
