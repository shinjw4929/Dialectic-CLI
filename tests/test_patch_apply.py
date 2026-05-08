"""tests/test_patch_apply.py — extract + apply 단위 검증.

tmp_path fixture로 workdir 격리 — 본 repo cwd 오염 0.
"""

import os
import sys
from pathlib import Path

import pytest

# repo root를 sys.path에 추가 (src/patch_apply 직접 import)
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.patch_apply import (  # noqa: E402
    PatchApplyError,
    apply_patches,
    extract_patches,
    validate_patch_path,
)


# ─── extract_patches ────────────────────────────────────────────────────────


def test_extract_single_block():
    """FILE/SEARCH/REPLACE 1 블록 추출."""
    text = (
        "여기 patch입니다.\n"
        "FILE: foo.py\n"
        "<<<<<<< SEARCH\n"
        "old_line\n"
        "=======\n"
        "new_line\n"
        ">>>>>>> REPLACE\n"
        "끝.\n"
    )
    patches = extract_patches(text)
    assert len(patches) == 1
    assert patches[0]["file"] == "foo.py"
    assert patches[0]["search"] == "old_line"
    assert patches[0]["replace"] == "new_line"


def test_extract_multiple_blocks():
    """같은 응답에 N=3 블록 — non-greedy 매칭이 첫 REPLACE에서 끊는지 검증."""
    text = (
        "FILE: a.py\n"
        "<<<<<<< SEARCH\n"
        "alpha\n"
        "=======\n"
        "ALPHA\n"
        ">>>>>>> REPLACE\n"
        "사이 narrative\n"
        "FILE: b.py\n"
        "<<<<<<< SEARCH\n"
        "beta\n"
        "=======\n"
        "BETA\n"
        ">>>>>>> REPLACE\n"
        "또 narrative\n"
        "FILE: c.py\n"
        "<<<<<<< SEARCH\n"
        "gamma\n"
        "=======\n"
        "GAMMA\n"
        ">>>>>>> REPLACE\n"
    )
    patches = extract_patches(text)
    assert len(patches) == 3
    files = [p["file"] for p in patches]
    assert files == ["a.py", "b.py", "c.py"]
    searches = [p["search"] for p in patches]
    assert searches == ["alpha", "beta", "gamma"]
    replaces = [p["replace"] for p in patches]
    assert replaces == ["ALPHA", "BETA", "GAMMA"]


def test_extract_zero_when_marker_missing():
    """======= 부재 → 매칭 X → []."""
    text = (
        "FILE: foo.py\n"
        "<<<<<<< SEARCH\n"
        "old_line\n"
        "no separator here\n"
        "new_line\n"
        ">>>>>>> REPLACE\n"
    )
    patches = extract_patches(text)
    assert patches == []


def test_extract_blank_line_in_search():
    """SEARCH 본문에 빈 줄 포함 시 정규식이 정확히 매칭 (P2-X5).

    re.DOTALL + non-greedy 결합으로 \\n\\n도 search 블록 내부에 포함.
    """
    text = (
        "FILE: foo.py\n"
        "<<<<<<< SEARCH\n"
        "line1\n"
        "\n"
        "line3\n"
        "=======\n"
        "REPLACED\n"
        ">>>>>>> REPLACE\n"
    )
    patches = extract_patches(text)
    assert len(patches) == 1
    assert patches[0]["search"] == "line1\n\nline3"
    assert patches[0]["replace"] == "REPLACED"


# ─── apply_patches ──────────────────────────────────────────────────────────


def test_apply_happy_path(tmp_path):
    """단일 파일 SEARCH/REPLACE 적용 — files_changed 반환 + 디스크 변경 검증."""
    target = tmp_path / "foo.py"
    target.write_text("def x():\n    return 1\n", encoding="utf-8")

    patches = [
        {
            "file": "foo.py",
            "search": "    return 1",
            "replace": "    return 2",
        }
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)

    assert status == "ok"
    assert error is None
    assert files_changed == ["foo.py"]
    assert target.read_text(encoding="utf-8") == "def x():\n    return 2\n"


def test_apply_path_traversal_blocked(tmp_path):
    """../etc/passwd 형태 외부 경로 차단 → status=failed, 변경 0."""
    # workdir 외부에 sentinel 작성 (변경되면 테스트 fail)
    sentinel = tmp_path.parent / "sentinel_outside.txt"
    sentinel.write_text("DO NOT TOUCH\n", encoding="utf-8")
    try:
        patches = [
            {
                "file": "../" + sentinel.name,
                "search": "DO NOT TOUCH",
                "replace": "TOUCHED",
            }
        ]
        status, error, files_changed = apply_patches(patches, workdir=tmp_path)
        assert status == "failed"
        assert error is not None and "path outside workdir" in error
        assert files_changed == []
        # sentinel 미변경 검증
        assert sentinel.read_text(encoding="utf-8") == "DO NOT TOUCH\n"
    finally:
        sentinel.unlink(missing_ok=True)


def test_apply_search_not_found_rollback(tmp_path):
    """SEARCH count==0 → status=failed, 다른 파일도 미변경 (all-or-nothing)."""
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("alpha\n", encoding="utf-8")
    b.write_text("beta\n", encoding="utf-8")

    patches = [
        {"file": "a.py", "search": "alpha", "replace": "ALPHA"},
        {"file": "b.py", "search": "DOES_NOT_EXIST", "replace": "X"},
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)
    assert status == "failed"
    assert error is not None and "search not found in b.py" in error
    assert files_changed == []
    # a.py 미변경 (dry-run에서 차단되어 write 진입 X)
    assert a.read_text(encoding="utf-8") == "alpha\n"
    assert b.read_text(encoding="utf-8") == "beta\n"


def test_apply_search_ambiguous_blocked(tmp_path):
    """SEARCH가 N>1회 매칭 → status=failed, error에 N 포함, 변경 0."""
    target = tmp_path / "dup.py"
    target.write_text("foo\nfoo\nfoo\n", encoding="utf-8")

    patches = [
        {"file": "dup.py", "search": "foo", "replace": "BAR"},
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)
    assert status == "failed"
    assert error is not None
    assert "ambiguous match" in error
    assert "3 times" in error
    assert "dup.py" in error
    assert files_changed == []
    assert target.read_text(encoding="utf-8") == "foo\nfoo\nfoo\n"


def test_apply_empty_search_blocked(tmp_path):
    """search="" → status=failed, error=empty SEARCH not allowed (P1-X4)."""
    target = tmp_path / "foo.py"
    target.write_text("content\n", encoding="utf-8")

    patches = [
        {"file": "foo.py", "search": "", "replace": "INSERT"},
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)
    assert status == "failed"
    assert error is not None and "empty SEARCH not allowed" in error
    assert "foo.py" in error
    assert files_changed == []
    assert target.read_text(encoding="utf-8") == "content\n"


def test_apply_multi_file_all_or_nothing(tmp_path):
    """2 파일 patch — 두번째 SEARCH 미일치 시 첫번째 파일도 미변경 (디스크 기준)."""
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("hello\n", encoding="utf-8")
    b.write_text("world\n", encoding="utf-8")

    patches = [
        {"file": "a.py", "search": "hello", "replace": "HELLO"},
        {"file": "b.py", "search": "MISSING", "replace": "X"},
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)
    assert status == "failed"
    assert error is not None
    assert files_changed == []
    # 첫번째 파일이 디스크에 미반영 — dry-run 단계에서 차단되어 write 진입 0
    assert a.read_text(encoding="utf-8") == "hello\n"
    assert b.read_text(encoding="utf-8") == "world\n"


def test_validate_patch_path_ssot(tmp_path):
    """cwd-isolation §Layer 4 SSOT 시그니처 1:1 — symlink escape + 절대경로 차단."""
    # 1. workdir 내부 파일 — OK
    inside = tmp_path / "inside.py"
    inside.write_text("ok\n", encoding="utf-8")
    resolved = validate_patch_path(tmp_path, "inside.py")
    assert resolved == inside.resolve()

    # 2. ../ 외부 traversal — PatchApplyError
    with pytest.raises(PatchApplyError) as exc_info:
        validate_patch_path(tmp_path, "../outside.txt")
    assert "path outside workdir" in str(exc_info.value)

    # 3. 절대 경로 외부 — PatchApplyError
    abs_outside = "/etc/passwd"
    with pytest.raises(PatchApplyError) as exc_info:
        validate_patch_path(tmp_path, abs_outside)
    assert "path outside workdir" in str(exc_info.value)

    # 4. symlink escape — Path.resolve()이 symlink 해소 후 검사
    if hasattr(os, "symlink"):
        outside_target = tmp_path.parent / "symlink_target.txt"
        outside_target.write_text("OUTSIDE\n", encoding="utf-8")
        link = tmp_path / "evil_link"
        try:
            os.symlink(outside_target, link)
            with pytest.raises(PatchApplyError) as exc_info:
                validate_patch_path(tmp_path, "evil_link")
            assert "path outside workdir" in str(exc_info.value)
        finally:
            link.unlink(missing_ok=True)
            outside_target.unlink(missing_ok=True)
