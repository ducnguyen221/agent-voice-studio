"""Cổng cho chính CI: chạy mọi nhánh, quyền tối thiểu, action ghim SHA, hai hệ điều hành.

Đọc YAML bằng regex có chủ đích — không kéo thêm phụ thuộc chỉ để kiểm vài dòng. Một workflow
mất `permissions:` hay quay về tag `@v4` sẽ vẫn chạy xanh, nên chỉ một test mới thấy được.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
FILES = ("tests.yml", "verify.yml")


def read(name):
    return (WF / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", FILES)
def test_runs_on_every_branch(name):
    push = re.search(r"^  push:\n((?:    .*\n)+)", read(name), re.MULTILINE)
    assert push and "branches: ['**']" in push.group(1), f"{name} phải chạy trên mọi nhánh"


@pytest.mark.parametrize("name", FILES)
def test_least_privilege(name):
    assert re.search(r"^permissions:\n  contents: read\s*$", read(name), re.MULTILINE), (
        f"{name} thiếu `permissions: contents: read` ở cấp workflow")


@pytest.mark.parametrize("name", FILES)
def test_actions_are_pinned_by_sha(name):
    uses = re.findall(r"uses:\s*(\S+)", read(name))
    assert uses
    loose = [u for u in uses if not re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u)]
    assert not loose, f"{name}: action chưa ghim SHA: {loose}"


def test_tests_run_on_windows_and_macos_with_python_matrix():
    text = read("tests.yml")
    assert "windows-latest" in text and "macos-latest" in text
    m = re.search(r"python-version: \[([^\]]+)\]", text)
    versions = {v.strip().strip('"') for v in m.group(1).split(",")}
    assert {"3.12", "3.13", "3.14"} <= versions
    assert "fail-fast: false" in text
