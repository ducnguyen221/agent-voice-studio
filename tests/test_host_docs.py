"""Cổng cho tài liệu agent và host: một nguồn (`AGENTS.md`), bốn trang host, không trôi khỏi mã.

`CLAUDE.md` và `GEMINI.md` chỉ là con trỏ — một bản hướng dẫn thứ hai sẽ lệch khỏi bản đầu
trong vài tuần. Mỗi trang host phải chỉ người đọc tới `voice-studio doctor`, vì đó là câu trả
lời duy nhất đáng tin cho "đã cài xong chưa". Link tương đối gãy là đỏ.
"""
import re
from pathlib import Path

import pytest

from voice_studio import cli

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


def test_agents_md_names_real_commands_only():
    """Lệnh `voice-studio <x>` mà AGENTS.md dạy phải có thật trong `cli.COMMANDS`."""
    named = set(re.findall(r"voice-studio ([a-z][a-z-]+)", read("AGENTS.md")))
    thua = named - set(cli.COMMANDS)
    assert not thua, f"AGENTS.md kể lệnh không có trong mã: {sorted(thua)}"
    assert {"doctor", "init", "speak"} <= named


ENTRY_DOCS = ["AGENTS.md", "INSTALL.md", "START-HERE.md", "README.md", "README.vi.md",
              "docs/INSTALL.md", "docs/troubleshooting.md", "docs/CHANGELOG.md", "samples/README.md"]


@pytest.mark.parametrize("rel", [*ENTRY_DOCS, *HOST_PAGES])
def test_relative_links_resolve(rel):
    base = (ROOT / rel).parent
    missing = []
    for target in re.findall(r"\]\(([^)\s]+)\)", read(rel)):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path = target.split("#", 1)[0]
        if path and not (base / path).exists():
            missing.append(target)
    assert not missing, f"{rel} có link tương đối gãy: {missing}"


# ── VO-2: repo không tự ghi cấu hình host; đăng ký host là bước theo INSTALL.md ─────────────
# Dấu vết của file cấu hình host trên máy người dùng. Mã package nhắc tới một trong số này
# nghĩa là đã có đường ghi (hoặc đọc) cấu hình host ngoài tay người dùng.
HOST_CONFIG_MARKERS = (".claude", ".codex", ".gemini", "claude_desktop_config", "mcp.json",
                       "settings.json", "config.toml")


def test_package_code_never_touches_host_config():
    hits = []
    for py in sorted((ROOT / "voice_studio").rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        hits += [f"{py.relative_to(ROOT)}: {m}" for m in HOST_CONFIG_MARKERS if m in text]
    assert not hits, f"mã package nhắc tới cấu hình host: {hits}"


def test_host_index_says_registration_is_an_install_md_step():
    text = read("hosts/README.md")
    assert "không tự ghi cấu hình của bất kỳ host AI nào" in text
    assert "../INSTALL.md#10-" in text, "đăng ký host phải trỏ về INSTALL.md mục 10"
    assert "## 10. Host" in read("INSTALL.md")
