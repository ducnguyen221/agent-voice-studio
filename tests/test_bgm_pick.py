"""Test `voice_studio.bgm` với một thư viện mẫu 3 style tên trung tính (file mp3 rỗng)."""
import json
import os

import pytest

from voice_studio import bgm

STYLES = ["calm", "bright", "drive"]


@pytest.fixture
def lib(tmp_path):
    d = tmp_path / "assets" / "bgm"
    d.mkdir(parents=True)
    for s in STYLES:
        (d / f"{s}.mp3").write_bytes(b"")
    (d / "bgm-library.json").write_text(json.dumps({
        "volume": 0.12,
        "default": "calm",
        # khoá "dir" cũ trỏ sang một máy khác — PHẢI bị bỏ qua, suy từ vị trí file
        "dir": os.path.join("elsewhere", "old-machine", "bgm"),
        "styles": [{"name": s, "mood": "m", "use": "u"} for s in STYLES],
    }), encoding="utf-8")
    return d


def test_library_ignores_dir_key(lib):
    L = bgm.library(str(lib))
    assert L.dir == str(lib)
    assert L.names() == STYLES and L.default == "calm" and L.volume == 0.12


def test_pick_named_style(lib):
    assert bgm.pick("bright", dir=str(lib)) == str(lib / "bright.mp3")


def test_pick_none_gives_default(lib):
    assert bgm.pick(None, dir=str(lib)) == str(lib / "calm.mp3")


def test_pick_unknown_falls_back_to_default(lib):
    with pytest.warns(UserWarning, match="nope"):
        assert bgm.pick("nope", dir=str(lib)) == str(lib / "calm.mp3")


def test_pick_missing_file_is_loud(lib):
    os.remove(lib / "drive.mp3")
    with pytest.raises(FileNotFoundError):
        bgm.pick("drive", dir=str(lib))


def test_volume_default_when_absent(tmp_path):
    d = tmp_path / "b"
    d.mkdir()
    (d / "bgm-library.json").write_text(json.dumps({"styles": [{"name": "x"}]}), encoding="utf-8")
    L = bgm.library(str(d))
    assert L.volume == bgm.DEFAULT_VOLUME == 0.10
    assert L.default == "x"                        # thiếu "default" → style đầu tiên


def test_dir_from_env_and_station(lib, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_BGM_DIR", str(lib))
    assert bgm.library().dir == str(lib)
    monkeypatch.delenv("VOICE_BGM_DIR")
    monkeypatch.setenv("VOICE_STATION", str(tmp_path))
    assert bgm.bgm_dir() == str(tmp_path / "assets" / "bgm")


def test_legacy_dir_env_warns(lib, monkeypatch):
    monkeypatch.setenv("NEWS_BGM_DIR", str(lib))
    with pytest.warns(DeprecationWarning):
        assert bgm.bgm_dir() == str(lib)


def test_missing_library_is_explained(tmp_path):
    with pytest.raises(FileNotFoundError, match="init_library"):
        bgm.library(str(tmp_path / "none"))


def test_init_library_creates_skeleton_without_audio(tmp_path):
    d = tmp_path / "station" / "assets" / "bgm"
    bgm.init_library(str(d))
    assert (d / "bgm-library.json").exists() and (d / "README.md").exists()
    assert not [p for p in os.listdir(d) if p.endswith(".mp3")]
    data = json.loads((d / "bgm-library.json").read_text(encoding="utf-8"))
    assert "dir" not in data and data["volume"] == 0.10 and data["styles"]
    # chạy lại không được đè thư viện người dùng đã sửa
    (d / "bgm-library.json").write_text('{"styles": [{"name": "mine"}]}', encoding="utf-8")
    bgm.init_library(str(d))
    assert "mine" in (d / "bgm-library.json").read_text(encoding="utf-8")


def test_cli_list_and_pick(lib, capsys):
    assert bgm.main(["list", "--dir", str(lib)]) == 0
    out = capsys.readouterr().out
    assert all(s in out for s in STYLES) and "*" in out            # đánh dấu mặc định
    assert bgm.main(["pick", "bright", "--dir", str(lib)]) == 0
    assert capsys.readouterr().out.strip() == str(lib / "bright.mp3")


def test_cli_missing_library_exit_3(tmp_path, capsys):
    assert bgm.main(["list", "--dir", str(tmp_path / "none")]) == 3


def test_cli_json(lib, capsys):
    assert bgm.main(["pick", "drive", "--dir", str(lib), "--json"]) == 0
    line = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(line)
    assert data == {"ok": True, "style": "drive", "path": str(lib / "drive.mp3"), "volume": 0.12}
