"""Tài liệu cài đặt agent-first: một prompt, một nguồn, không lệnh nguy hiểm, hai hệ điều hành.

`INSTALL.md` ở gốc repo là bản gốc của prompt copy-dán. README, START-HERE và trang `/install/`
của website chỉ chép lại; test này bắt mọi chỗ chép lệch. Test cũng khoá luật an toàn của
runbook: không tải-rồi-chạy, không đổi chính sách máy, không để agent tự chọn chỗ đặt trạm, và
mọi lệnh `voice-studio <x>` nó dạy phải có thật.
"""
import html
import re
from pathlib import Path

import pytest

from voice_studio import cli

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_REPO = "https://github.com/ducnguyen221/agent-voice-studio"
RAW_INSTALL_URL = "https://raw.githubusercontent.com/ducnguyen221/agent-voice-studio/main/INSTALL.md"
PROMPT_START = {
    "vi": "Hãy cài Agent Voice Studio lên máy này",
    "en": "Install Agent Voice Studio on this machine",
}
MAX_PROMPT_LINES = 12
# Nơi chép prompt: file Markdown (khối ```text) hoặc trang web (<pre id="prompt-<lang>">).
COPIES = {
    "vi": ["README.vi.md"],
    "en": ["README.md"],
}
USER_DOCS = ["INSTALL.md", "README.md", "README.vi.md", "docs/INSTALL.md", "hosts/README.md",
             "hosts/claude/README.md", "hosts/codex/README.md", "hosts/antigravity/README.md",
             "hosts/claude-desktop/README.md"]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def normalize(text):
    return "\n".join(line.rstrip() for line in text.strip("\n").split("\n"))


def fenced_blocks(markdown, lang=r"[\w-]*"):
    return re.findall(rf"^```{lang}\n(.*?)^```", markdown, flags=re.MULTILINE | re.DOTALL)


def html_pre_blocks(page):
    blocks = {}
    for i, m in enumerate(re.finditer(r"<pre([^>]*)>(.*?)</pre>", page, flags=re.DOTALL)):
        ident = re.search(r'id="([^"]+)"', m.group(1))
        blocks[ident.group(1) if ident else f"#{i}"] = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))
    return blocks


def prompt_in(rel, lang):
    text = read(rel)
    if rel.endswith(".html"):
        found = html_pre_blocks(text).get(f"prompt-{lang}")
        assert found is not None, f'{rel}: thiếu <pre id="prompt-{lang}">'
        return normalize(found)
    hits = [b for b in fenced_blocks(text) if b.startswith(PROMPT_START[lang])]
    assert len(hits) == 1, f"{rel}: cần đúng 1 khối prompt {lang}, thấy {len(hits)}"
    return normalize(hits[0])


def canonical(lang):
    return prompt_in("INSTALL.md", lang)


@pytest.mark.parametrize("lang,rel", [(lang, rel) for lang, rels in COPIES.items() for rel in rels])
def test_prompt_copies_match_install_md(lang, rel):
    assert prompt_in(rel, lang) == canonical(lang), (
        f"Prompt {lang} trong {rel} lệch bản gốc INSTALL.md — chép lại nguyên văn khối trong INSTALL.md.")


@pytest.mark.parametrize("lang", sorted(PROMPT_START))
def test_prompt_points_to_single_official_source_and_is_short(lang):
    prompt = canonical(lang)
    urls = set(re.findall(r"https?://\S+", prompt))
    assert urls == {OFFICIAL_REPO, RAW_INSTALL_URL}, f"prompt chỉ được trỏ repo chính thức: {sorted(urls)}"
    assert (ROOT / RAW_INSTALL_URL.rsplit("/main/", 1)[1]).is_file()
    assert len(prompt.splitlines()) <= MAX_PROMPT_LINES, "prompt quá dài để dán vào ô chat"
    assert "doctor" in prompt


@pytest.mark.parametrize("lang,must", [
    ("vi", ["Hỏi tôi trước", "admin", "chính sách", "mật khẩu", ".env", "trạm"]),
    ("en", ["Ask me before", "admin", "policy", "passwords", ".env", "station"]),
])
def test_prompt_states_the_safety_rules(lang, must):
    prompt = canonical(lang)
    for word in must:
        assert word in prompt, f"prompt {lang} thiếu ý an toàn: {word}"


BAD_LINE = re.compile(r"\biex\b|Invoke-Expression|DownloadString|\|\s*(?:ba|z)?sh\b", re.IGNORECASE)


def command_blocks(rel):
    text = read(rel)
    if rel.endswith(".html"):
        return list(html_pre_blocks(text).values())
    return [b for lang in ("bash", "sh", "zsh", "powershell", "") for b in fenced_blocks(text, lang)]


@pytest.mark.parametrize("rel", USER_DOCS)
def test_no_download_and_execute_or_policy_change(rel):
    bad = [ln.strip() for b in command_blocks(rel) for ln in b.splitlines() if BAD_LINE.search(ln)]
    bad += re.findall(r"Set-ExecutionPolicy[^\n]*", read(rel), flags=re.IGNORECASE)
    assert not bad, f"{rel}: lệnh bị cấm trong tài liệu cài:\n  " + "\n  ".join(bad)


def test_install_md_never_lets_the_agent_pick_the_station():
    text = read("INSTALL.md")
    assert "--non-interactive" in text and "mã 2" in text
    assert "init --yes" in text and "init --station" in text


def test_install_md_covers_both_operating_systems():
    text = read("INSTALL.md")
    assert "Windows" in text and "macOS" in text
    assert r".venv\Scripts" in text and ".venv/bin/" in text
    assert "winget" in text and "brew" in text
    assert fenced_blocks(text, "powershell") and fenced_blocks(text, "bash")


def test_install_md_teaches_only_real_commands():
    named = set(re.findall(r"voice-studio(?:\.exe)? ([a-z][a-z-]+)", read("INSTALL.md")))
    thua = named - set(cli.COMMANDS)
    assert not thua, f"INSTALL.md dạy lệnh không có trong mã: {sorted(thua)}"
    assert {"init", "doctor", "speak", "uninstall"} <= named


def test_install_md_names_every_host():
    text = read("INSTALL.md")
    for host in ("Claude Code", "Codex", "Antigravity", "Claude Desktop"):
        assert host in text, host


def test_entry_docs_point_to_install_md():
    for rel in ("README.md", "README.vi.md", "AGENTS.md", "hosts/README.md"):
        assert "INSTALL.md" in read(rel), f"{rel} chưa trỏ tới INSTALL.md"


def test_doctor_is_never_said_to_download_weights():
    """doctor không nạp model ⇒ không bao giờ tải gì. Tài liệu nói ngược là người dùng chờ mãi."""
    bad = []
    for rel in USER_DOCS + ["docs/WORKSPACE.md", "skills/voice-routing/references/install-omnivoice.md"]:
        for ln in read(rel).splitlines():
            if re.search(r"OMNIVOICE_ONLINE\s*=\s*1\s+\S*voice-studio(?:\.exe)?\s+doctor", ln):
                bad.append(f"{rel}: {ln.strip()}")
    assert not bad, "\n".join(bad)
