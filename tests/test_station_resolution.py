"""Phân giải trạm giọng khi KHÔNG ai đặt gì (quyết định Đ4): mặc định là thư mục trong repo.

Người dùng public clone repo, không đặt biến nào ⇒ trạm là `<repo>/workspace/` (bị git bỏ
qua), không phải một thư mục ẩn mới dưới home. `~/.voice` chỉ được dùng khi người dùng đã
chọn nó hoặc nó đã là một trạm từ trước. Cài dạng wheel (không repo) mà chưa đặt gì ⇒ báo
mã 3 kèm cách đặt, không tự tạo thư mục.

HOME giả do conftest dựng (`tmp_path/home`), nên không test nào đọc được trạm thật của máy.
"""
import json
import os

import pytest

from voice_studio import _env, cli
from voice_studio.contract import StationMissing

from conftest import last_json


def same(a, b):
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir(exist_ok=True)
    return h


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "clone"
    r.mkdir()
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(r))
    return r


def make_home_station(home):
    (home / ".voice" / "omnivoice" / "voices").mkdir(parents=True)
    return home / ".voice"


# ── thứ tự từng tầng ──────────────────────────────────────────────────────────────────

def test_tier1_voice_station_beats_everything(repo, home, tmp_path, monkeypatch):
    (repo / "workspace").mkdir()
    make_home_station(home)
    monkeypatch.setenv("OMNIVOICE_DIR", str(tmp_path / "old" / "omnivoice"))
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    st, src = _env.resolve_station()
    assert same(st, tmp_path / "st") and src == "VOICE_STATION"


def test_tier2_legacy_engine_dir_gives_its_parent(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIVOICE_DIR", str(tmp_path / "old" / "omnivoice"))
    st, src = _env.resolve_station()
    assert same(st, tmp_path / "old") and src == "OMNIVOICE_DIR"


def test_tier3_local_config_station_path(repo, tmp_path):
    (repo / "workspace").mkdir()                       # có cả workspace/: lựa chọn đã ghi vẫn thắng
    (repo / "studio.local.json").write_text(
        json.dumps({"mode": "separate", "station_path": str(tmp_path / "chon")}), encoding="utf-8")
    st, src = _env.resolve_station()
    assert same(st, tmp_path / "chon") and src == "studio.local.json"


def test_tier4_existing_workspace_beats_old_home_station(repo, home):
    (repo / "workspace").mkdir()
    make_home_station(home)
    st, src = _env.resolve_station()
    assert same(st, repo / "workspace") and src == "workspace"


def test_tier5_home_station_only_when_it_already_is_one(repo, home):
    make_home_station(home)
    st, src = _env.resolve_station()
    assert same(st, home / ".voice") and src == _env.HOME_STATION


def test_empty_home_dir_is_not_a_station(repo, home):
    (home / ".voice").mkdir()                          # thư mục rỗng: không phải trạm
    st, src = _env.resolve_station()
    assert same(st, repo / "workspace") and src == "workspace"


def test_tier6_default_is_repo_workspace_even_before_init(repo, home):
    st, src = _env.resolve_station()
    assert same(st, repo / "workspace") and src == "workspace"
    assert not (repo / "workspace").exists()            # phân giải KHÔNG tạo thư mục
    assert not (home / ".voice").exists()


def test_tier7_wheel_install_without_anything_is_unset(home):
    # conftest trỏ VOICE_STUDIO_REPO vào một thư mục KHÔNG tồn tại = bản cài không có repo.
    st, src = _env.resolve_station()
    assert st is None and src == _env.UNSET
    with pytest.raises(StationMissing) as e:
        _env.station_dir()
    assert "VOICE_STATION" in str(e.value)
    assert not (home / ".voice").exists()


# ── hệ quả ở CLI ──────────────────────────────────────────────────────────────────────

def test_cli_on_unset_station_exits_3_with_hint(capsys, home):
    rc = cli.main(["export", "--personal", "--out", str(home / "x.zip"), "--json"])
    out = capsys.readouterr().out
    assert rc == 3
    res = last_json(out)
    assert res["ok"] is False and res["code"] == 3 and "VOICE_STATION" in res["error"]
    assert not (home / ".voice").exists()


def test_init_yes_in_clone_builds_repo_workspace(repo, home, capsys):
    rc = cli.main(["init", "--yes", "--json"])
    res = last_json(capsys.readouterr().out)
    assert rc == 0 and res["mode"] == "embedded"
    assert same(res["station"], repo / "workspace")
    assert (repo / "workspace" / "station.json").is_file()
    assert not (home / ".voice").exists()
    st, src = _env.resolve_station()
    assert same(st, repo / "workspace")
