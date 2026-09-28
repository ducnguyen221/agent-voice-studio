"""Cổng cho tài liệu agent và host: một nguồn (`AGENTS.md`), bốn trang host, không trôi khỏi mã.

`CLAUDE.md` và `GEMINI.md` chỉ là con trỏ — một bản hướng dẫn thứ hai sẽ lệch khỏi bản đầu
trong vài tuần. Mỗi trang host phải chỉ người đọc tới `voice-studio doctor`, vì đó là câu trả
lời duy nhất đáng tin cho "đã cài xong chưa". Link tương đối gãy là đỏ.
"""
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
HOSTS = ("claude", "codex", "claude-desktop", "antigravity")
HOST_PAGES = ["hosts/README.md"] + [f"hosts/{h}/README.md" for h in HOSTS]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("rel", ["CLAUDE.md", "GEMINI.md"])
def test_pointer_files_only_point_to_agents_md(rel):
    text = read(rel)
    assert "AGENTS.md" in text
    assert len([ln for ln in text.splitlines() if ln.strip()]) <= 6, f"{rel} phải là con trỏ, không phải bản thứ hai"


@pytest.mark.parametrize("rel", HOST_PAGES)
def test_every_host_page_exists_and_names_doctor(rel):
    assert "voice-studio doctor" in read(rel), f"{rel} không chỉ tới `voice-studio doctor`"


def test_host_index_lists_every_host_page():
    text = read("hosts/README.md")
    for h in HOSTS:
        assert f"{h}/README.md" in text, f"hosts/README.md thiếu trang {h}"
