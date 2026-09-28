"""Một số phiên bản cho mọi manifest phát hành.

Bump version phải đổi đủ năm chỗ cùng lúc: `pyproject.toml`, `voice_studio/__init__.py` và ba
manifest plugin (Claude marketplace + plugin, Codex plugin). Lệch một chỗ thì marketplace, gói
Python và `voice-studio --version` nói những phiên bản khác nhau — đã từng xảy ra trước một lần
gắn tag, và chỉ được phát hiện bằng mắt.

Bước `verify.yml` trên CI chỉ so ba manifest VỚI NHAU; test này so chúng với gói Python, và chạy
được ngay trên máy trước khi đẩy mã.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
MARKETPLACE = ".claude-plugin/marketplace.json"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def versions(root=ROOT):
    """Mọi chỗ khai phiên bản -> {nơi: số}. `root` đổi được để test đột biến trên bản chép."""
    def rd(rel):
        return (root / rel).read_text(encoding="utf-8")

    found = {}
    m = re.search(r'^version\s*=\s*"([^"]+)"', rd("pyproject.toml"), re.MULTILINE)
    found["pyproject.toml"] = m.group(1) if m else None
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', rd("voice_studio/__init__.py"), re.MULTILINE)
    found["voice_studio/__init__.py"] = m.group(1) if m else None
    for rel in MANIFESTS:
        found[rel] = json.loads(rd(rel)).get("version")
    market = json.loads(rd(MARKETPLACE))
    plugins = market.get("plugins") or []
    assert plugins, f"{MARKETPLACE} không khai plugin nào"
    for p in plugins:
        found[f"{MARKETPLACE}#{p.get('name')}"] = p.get("version")
    return found


def test_all_manifests_share_one_version():
    v = versions()
    assert None not in v.values(), f"thiếu trường version: {v}"
    assert len(set(v.values())) == 1, f"version lệch giữa các manifest: {v}"
    assert re.fullmatch(r"\d+\.\d+\.\d+", next(iter(v.values()))), v


def test_cli_reports_the_same_version():
    from voice_studio import __version__
    assert set(versions().values()) == {__version__}


def test_manifest_names_agree():
    names = {json.loads(read(rel))["name"] for rel in MANIFESTS}
    market = json.loads(read(MARKETPLACE))
    names |= {market["name"]} | {p["name"] for p in market["plugins"]}
    assert names == {"agent-voice-studio"}, names


def test_gate_goes_red_when_one_manifest_drifts(tmp_path):
    """Đột biến: sửa một manifest trên BẢN CHÉP → cổng phải thấy lệch."""
    for rel in ("pyproject.toml", "voice_studio/__init__.py", MARKETPLACE, *MANIFESTS):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(read(rel), encoding="utf-8")
    codex = tmp_path / ".codex-plugin/plugin.json"
    data = json.loads(codex.read_text(encoding="utf-8"))
    data["version"] = "9.9.9"
    codex.write_text(json.dumps(data), encoding="utf-8")
    drifted = versions(tmp_path)
    assert len(set(drifted.values())) == 2
    assert drifted[".codex-plugin/plugin.json"] == "9.9.9"


def test_changelog_leads_with_unreleased_or_current_version():
    """Mục đầu `docs/CHANGELOG.md` là "Chưa phát hành" (đang làm) hoặc đúng số phiên bản hiện tại;
    và số hiện tại phải có mục riêng. Phát hành = đổi tiêu đề "Chưa phát hành" thành số mới."""
    from voice_studio import __version__
    heads = re.findall(r"^## (.+)$", read("docs/CHANGELOG.md"), re.MULTILINE)
    assert heads, "docs/CHANGELOG.md không có mục nào"
    first = heads[0].split(" — ")[0].strip()
    assert first in ("Chưa phát hành", __version__), f"mục đầu CHANGELOG là {heads[0]!r}"
    assert any(h.split(" — ")[0].strip() == __version__ for h in heads), (
        f"docs/CHANGELOG.md thiếu mục cho {__version__}")
