"""tests/test_patch_apply_new_file.py — apply_patches 신규 파일 분기 (plan 014 Phase D).

ADR-10 narrative "신규 파일·기존 파일 둘 다 동일 흐름" wiring 검증.

케이스:
1. basic 신규 파일 (SEARCH="" + 부재)
2. subdir 신규 파일 (parent mkdir 검증)
3. mixed (신규+기존 동시)
4. existing-file SEARCH="" 거부 (정책 보존)
5. rollback unlink (신규 파일 commit 후 후속 OSError → unlink)
"""

import sys
from pathlib import Path

import pytest

# repo root를 sys.path에 추가 (src/patch_apply 직접 import)
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.patch_apply import apply_patches  # noqa: E402


# ─── 신규 파일 분기 ─────────────────────────────────────────────────────────


def test_apply_patches_new_file_basic(tmp_path):
    """SEARCH="" + 파일 부재 → REPLACE를 신규 파일로 write."""
    patches = [
        {"file": "new.py", "search": "", "replace": "def f(): pass\n"}
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)

    assert status == "ok"
    assert error is None
    assert files_changed == ["new.py"]
    assert (tmp_path / "new.py").read_text(encoding="utf-8") == "def f(): pass\n"


def test_apply_patches_new_file_with_subdir(tmp_path):
    """SEARCH="" + 중첩 path → parent dir mkdir(parents=True) + write."""
    patches = [
        {"file": "pkg/sub/mod.py", "search": "", "replace": "x = 1\n"}
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)

    assert status == "ok"
    assert error is None
    assert (tmp_path / "pkg" / "sub" / "mod.py").exists()
    assert (tmp_path / "pkg" / "sub" / "mod.py").read_text(encoding="utf-8") == "x = 1\n"
    assert "pkg/sub/mod.py" in files_changed or str(Path("pkg/sub/mod.py")) in files_changed


def test_apply_patches_new_and_existing_mixed(tmp_path):
    """한 응답에 신규 파일 + 기존 파일 patch 혼합 — 둘 다 ok."""
    (tmp_path / "old.py").write_text("def old(): return 1\n", encoding="utf-8")
    patches = [
        {"file": "new.py", "search": "", "replace": "def new(): pass\n"},
        {"file": "old.py", "search": "return 1", "replace": "return 2"},
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)

    assert status == "ok"
    assert error is None
    assert set(files_changed) == {"new.py", "old.py"}
    assert (tmp_path / "new.py").read_text(encoding="utf-8") == "def new(): pass\n"
    assert (tmp_path / "old.py").read_text(encoding="utf-8") == "def old(): return 2\n"


def test_apply_patches_existing_file_empty_search_rejected(tmp_path):
    """기존 정책 보존 — 파일 존재 + SEARCH="" → PatchApplyError."""
    target = tmp_path / "x.py"
    target.write_text("body\n", encoding="utf-8")
    patches = [
        {"file": "x.py", "search": "", "replace": "new body\n"}
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)

    assert status == "failed"
    assert error is not None and "empty SEARCH not allowed" in error
    assert "x.py" in error
    assert files_changed == []
    # 기존 파일 미변경
    assert target.read_text(encoding="utf-8") == "body\n"


def test_apply_patches_new_file_rollback_unlink(tmp_path, monkeypatch):
    """신규 파일 commit 후 후속 write OSError → 신규 파일 unlink (rollback 정합).

    write_text를 monkeypatch — 첫 호출 정상, 두 번째 호출 OSError.
    검증: status="failed", 첫 신규 파일이 disk에 남아있지 않음.
    """
    patches = [
        {"file": "new1.py", "search": "", "replace": "first\n"},
        {"file": "new2.py", "search": "", "replace": "second\n"},
    ]

    # write_text 호출을 추적 + 두 번째 호출에서 OSError raise
    original_write_text = Path.write_text
    call_count = {"n": 0}

    def fake_write_text(self, data, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("simulated IO error")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    status, error, files_changed = apply_patches(patches, workdir=tmp_path)

    assert status == "failed"
    assert error is not None
    assert "io error" in error
    assert files_changed == []
    # 핵심 검증: 첫 신규 파일이 rollback으로 unlink됨
    assert not (tmp_path / "new1.py").exists()
    # 두 번째 신규 파일은 write 자체가 실패했으므로 디스크에 없음
    assert not (tmp_path / "new2.py").exists()


def test_apply_patches_new_file_then_modify_same_response(tmp_path):
    """같은 응답 내 신규 파일 작성 후 즉시 SEARCH/REPLACE 수정 (엣지케이스 5)."""
    patches = [
        {"file": "new.py", "search": "", "replace": "def f(): pass\n"},
        {"file": "new.py", "search": "def f(): pass", "replace": "def f():\n    return 1"},
    ]
    status, error, files_changed = apply_patches(patches, workdir=tmp_path)

    assert status == "ok"
    assert error is None
    assert files_changed == ["new.py"]
    assert (tmp_path / "new.py").read_text(encoding="utf-8") == "def f():\n    return 1\n"
