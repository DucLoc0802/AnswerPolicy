"""File tools: đọc/ghi đúng phạm vi, lỗi có cấu trúc, chặn traversal/absolute/symlink escape."""

import json
import os
import subprocess

import pytest

from reset_workspace import WorkspaceError, ensure_workspace, reset_workspace
from tools import list_files, read_file, write_file
from tools.files import MAX_READ_BYTES, _list, _read, _write



def make_link(link, target, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        if os.name != "nt" or getattr(exc, "winerror", None) != 1314:
            raise
        if not directory:
            pytest.skip("Windows requires symlink privileges for file links")
        # Junctions exercise real directory-link resolution without symlink privileges.
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True, capture_output=True,
        )


@pytest.fixture
def ws(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "data").mkdir(parents=True)
    (workspace / "output").mkdir()
    (workspace / "data" / "note.md").write_text("Xin chào", encoding="utf-8")
    return workspace


def test_read_ok(ws):
    assert _read(ws, "data/note.md") == {"ok": True, "path": "data/note.md", "content": "Xin chào"}


def test_read_missing_file(ws):
    result = _read(ws, "data/khong-ton-tai.md")
    assert result["ok"] is False and result["error"]["code"] == "FILE_NOT_FOUND"


@pytest.mark.parametrize("path", ["../secret.txt", "data/../../secret.txt"])
def test_read_traversal_blocked(ws, path):
    (ws.parent / "secret.txt").write_text("secret")
    assert _read(ws, path)["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_read_absolute_path_blocked(ws):
    assert _read(ws, str(ws / "data" / "note.md"))["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_read_symlink_escape_blocked(ws):
    (ws.parent / "secret.txt").write_text("secret")
    make_link(ws / "data" / "link.txt", ws.parent / "secret.txt")
    result = _read(ws, "data/link.txt")
    assert result["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"
    assert "content" not in result


def test_read_too_large_and_non_utf8(ws):
    (ws / "data" / "big.txt").write_text("a" * (MAX_READ_BYTES + 1))
    (ws / "data" / "bin.dat").write_bytes(b"\xff\xfe\x00")
    assert _read(ws, "data/big.txt")["error"]["code"] == "FILE_TOO_LARGE"
    assert _read(ws, "data/bin.dat")["error"]["code"] == "NOT_UTF8_TEXT"
    assert _read(ws, "data")["error"]["code"] == "IS_A_DIRECTORY"


def test_write_created_then_updated(ws):
    first = _write(ws, "output/reports/summary.md", "# Tóm tắt")
    assert first == {"ok": True, "path": "output/reports/summary.md", "bytes": len("# Tóm tắt".encode()), "status": "created"}
    second = _write(ws, "output/reports/summary.md", "v2")
    assert second["status"] == "updated" and second["bytes"] == 2
    assert (ws / "output" / "reports" / "summary.md").read_text(encoding="utf-8") == "v2"


@pytest.mark.parametrize("path", ["data/note.md", "summary.md", "output", "output/../data/x.md", "../output/x.md"])
def test_write_outside_output_rejected(ws, path):
    result = _write(ws, path, "x")
    assert result["ok"] is False
    assert result["error"]["code"] in {"PATH_OUTSIDE_OUTPUT", "PATH_OUTSIDE_WORKSPACE"}
    assert (ws / "data" / "note.md").read_text(encoding="utf-8") == "Xin chào"


def test_write_absolute_and_symlink_escape_rejected(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    make_link(ws / "output" / "escape", outside, directory=True)
    assert _write(ws, str(ws / "output" / "a.md"), "x")["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"
    assert _write(ws, "output/escape/a.md", "x")["ok"] is False
    assert list(outside.iterdir()) == []


def test_tools_return_json_against_project_workspace(lab_dirs):
    assert json.loads(read_file.invoke({"path": "data/weekly_notes.md"}))["ok"] is True
    written = json.loads(write_file.invoke({"path": "output/t.md", "content": "ok"}))
    assert written["status"] == "created"
    assert json.loads(read_file.invoke({"path": "output/t.md"}))["content"] == "ok"


def test_reset_restores_fixtures_and_requires_marker(tmp_path):
    fixtures = tmp_path / "fixtures"
    (fixtures / "data").mkdir(parents=True)
    (fixtures / "data" / "a.md").write_text("A")
    workspace = tmp_path / "workspace"
    ensure_workspace(workspace, fixtures)
    (workspace / "data" / "a.md").write_text("changed")
    (workspace / "output" / "r.md").write_text("R")
    ensure_workspace(workspace, fixtures)  # không ghi đè khi đã có workspace
    assert (workspace / "data" / "a.md").read_text() == "changed"
    reset_workspace(workspace, fixtures)
    assert (workspace / "data" / "a.md").read_text() == "A"
    assert list((workspace / "output").iterdir()) == []

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("keep")
    with pytest.raises(WorkspaceError):
        reset_workspace(foreign, fixtures)
    with pytest.raises(WorkspaceError):
        ensure_workspace(foreign, fixtures)
    assert (foreign / "keep.txt").read_text() == "keep"



def test_list_sorted_direct_entries_and_empty_directory(ws):
    (ws / "data" / "a-folder").mkdir()
    (ws / "data" / "a-folder" / "nested.md").write_text("nested")
    assert _list(ws, "data") == {
        "ok": True, "path": "data", "entries": [
            {"name": "a-folder", "path": "data/a-folder", "type": "directory"},
            {"name": "note.md", "path": "data/note.md", "type": "file"},
        ],
    }
    assert _list(ws, "output") == {"ok": True, "path": "output", "entries": []}
    assert _list(ws, ".")["path"] == "."


@pytest.mark.parametrize("path,code", [
    ("data/missing", "DIRECTORY_NOT_FOUND"),
    ("data/note.md", "NOT_A_DIRECTORY"),
    ("../outside", "PATH_OUTSIDE_WORKSPACE"),
    ("data/../../outside", "PATH_OUTSIDE_WORKSPACE"),
    ("", "INVALID_PATH"),
])
def test_list_invalid_paths(ws, path, code):
    result = _list(ws, path)
    assert result["ok"] is False
    assert result["error"]["code"] == code
    assert "entries" not in result


def test_list_absolute_path_blocked(ws):
    assert _list(ws, str(ws / "data"))["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_list_symlink_escape_blocked(ws):
    outside = ws.parent / "outside"
    outside.mkdir()
    (outside / "dummy.txt").write_text("test fixture")
    make_link(ws / "data" / "escape", outside, directory=True)
    assert _list(ws, "data/escape")["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"
    result = _list(ws, "data")
    assert result["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"
    assert "entries" not in result


def test_list_io_error_is_structured(ws, monkeypatch):
    def denied(self):
        raise PermissionError("test denied")
    monkeypatch.setattr(type(ws), "iterdir", denied)
    assert _list(ws, "data")["error"]["code"] == "IO_ERROR"


def test_list_finds_renamed_policies_and_read_file_can_read_them(lab_dirs):
    import paths
    policies = paths.WORKSPACE_DIR / "data/policies"
    originals = sorted(policies.glob("*.md"))
    for index, source in enumerate(originals):
        source.rename(policies / f"renamed-{index}.md")
    result = json.loads(list_files.invoke({"path": "data/policies"}))
    assert result["ok"] is True and len(result["entries"]) == 2
    for entry in result["entries"]:
        read = json.loads(read_file.invoke({"path": entry["path"]}))
        assert read["ok"] is True and "2026-10-01" in read["content"]



def test_list_internal_directory_link_preserves_usable_path(ws):
    make_link(ws / "data" / "alias", ws / "output", directory=True)
    result = _list(ws, "data")
    alias = next(entry for entry in result["entries"] if entry["name"] == "alias")
    assert alias == {"name": "alias", "path": "data/alias", "type": "directory"}
    assert _list(ws, alias["path"])["ok"] is True
