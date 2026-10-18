"""Phân giải trạm giọng khi KHÔNG ai đặt gì: mặc định là thư mục trong repo.

Người dùng public clone repo, không đặt biến nào ⇒ trạm là `<repo>/workspaces/` (bị git bỏ
qua), cùng tên `workspaces` với trạm dùng chung khi cài cạnh OpcOS — chỉ khác là nằm trong
repo. Tên số ít cũ `<repo>/workspace/` còn được nhận nếu nó đã là một trạm và `workspaces`
chưa có. Cài dạng wheel (không repo) mà chưa đặt gì ⇒ báo mã 3 kèm cách đặt, không tự tạo thư mục.

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


NEW = ("workspaces",)


def new_dir(repo):
    return repo.joinpath(*NEW)


def make_old_station(repo):
    d = repo / "workspace"
    (d / "omnivoice" / "voices").mkdir(parents=True)
    return d


# ── thứ tự từng tầng ──────────────────────────────────────────────────────────────────

def test_tier1_voice_station_beats_everything(repo, tmp_path, monkeypatch):
    new_dir(repo).mkdir(parents=True)
    make_old_station(repo)
    monkeypatch.setenv("OMNIVOICE_DIR", str(tmp_path / "old" / "omnivoice"))
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    st, src = _env.resolve_station()
    assert same(st, tmp_path / "st") and src == "VOICE_STATION"


def test_tier2_legacy_engine_dir_gives_its_parent(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIVOICE_DIR", str(tmp_path / "old" / "omnivoice"))
    st, src = _env.resolve_station()
    assert same(st, tmp_path / "old") and src == "OMNIVOICE_DIR"


def test_tier3_local_config_station_path(repo, tmp_path):
    new_dir(repo).mkdir(parents=True)                     # có cả workspaces: lựa chọn đã ghi vẫn thắng
    (repo / "studio.local.json").write_text(
        json.dumps({"mode": "separate", "station_path": str(tmp_path / "chon")}), encoding="utf-8")
    st, src = _env.resolve_station()
    assert same(st, tmp_path / "chon") and src == "studio.local.json"


def test_tier3_local_config_relative_old_name_still_resolves(repo):
    """studio.local.json do bản cũ ghi (`station_path: workspace`) vẫn trỏ đúng trạm cũ."""
    make_old_station(repo)
    (repo / "studio.local.json").write_text(
        json.dumps({"mode": "embedded", "station_path": "workspace"}), encoding="utf-8")
    st, src = _env.resolve_station()
    assert same(st, repo / "workspace") and src == "studio.local.json"


def test_tier4_existing_workspaces_is_the_embedded_station(repo):
    new_dir(repo).mkdir(parents=True)
    st, src = _env.resolve_station()
    assert same(st, new_dir(repo)) and src == "workspaces"


def test_tier4_old_singular_station_is_adopted_when_the_new_one_is_missing(repo, capsys):
    old = make_old_station(repo)
    st, src = _env.resolve_station()
    assert same(st, old) and src == "workspace"
    _out, err = capsys.readouterr()
    assert "workspaces" in err and str(old) in err        # một dòng khuyến nghị đổi tên
    _env.resolve_station()                                # lần sau trong cùng tiến trình: không nhắc lại
    assert capsys.readouterr().err == ""


def test_tier4_both_layouts_prefer_the_new_one_and_say_so(repo, capsys):
    make_old_station(repo)
    new_dir(repo).mkdir(parents=True)
    st, src = _env.resolve_station()
    assert same(st, new_dir(repo)) and src == "workspaces"
    _out, err = capsys.readouterr()
    assert "workspace" in err and "workspaces" in err


def test_tier4_old_singular_dir_without_marker_is_not_a_station(repo):
    (repo / "workspace").mkdir()
    st, src = _env.resolve_station()
    assert same(st, new_dir(repo)) and src == "workspaces"


def test_resolve_station_ignores_opcos_workspaces(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("OPCOS_WORKSPACES", str(make_opcos_station(tmp_path)))
    st, src = _env.resolve_station()
    assert same(st, new_dir(repo)) and src == "workspaces"


def make_opcos_station(tmp_path, name="ocws"):
    ws = tmp_path / name
    (ws / "voice").mkdir(parents=True)
    (ws / "voice" / "station.json").write_text("{}", encoding="utf-8")
    return ws


def test_sandbox_home_hides_real_home(sandbox_home, tmp_path):
    assert os.path.expanduser("~").startswith(str(tmp_path))
    assert "OPCOS_WORKSPACES" not in os.environ and "VOICE_STATION" not in os.environ


def test_opcos_station_found_when_marked(tmp_path, monkeypatch):
    ws = make_opcos_station(tmp_path)
    monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
    assert _env.opcos_station() == str(ws / "voice")


def test_opcos_station_none_without_marker(tmp_path, monkeypatch):
    (tmp_path / "ocws" / "voice").mkdir(parents=True)        # thư mục có, không dấu trạm
    monkeypatch.setenv("OPCOS_WORKSPACES", str(tmp_path / "ocws"))
    assert _env.opcos_station() is None
    monkeypatch.delenv("OPCOS_WORKSPACES")
    assert _env.opcos_station() is None


def test_opcos_station_blank_file_or_tilde(tmp_path, monkeypatch, sandbox_home):
    for blank in ("", "  "):
        monkeypatch.setenv("OPCOS_WORKSPACES", blank)
        assert _env.opcos_station() is None
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(f))
    assert _env.opcos_station() is None
    make_opcos_station(sandbox_home, "ws")
    monkeypatch.setenv("OPCOS_WORKSPACES", "~/ws")
    assert same(_env.opcos_station(), sandbox_home / "ws" / "voice")


def test_tier6_default_is_repo_workspaces_even_before_init(repo, home):
    st, src = _env.resolve_station()
    assert same(st, new_dir(repo)) and src == "workspaces"
    assert not (repo / "workspaces").exists() and not (repo / "workspace").exists()   # phân giải KHÔNG tạo gì


def test_tier7_wheel_install_without_anything_is_unset(home):
    # conftest trỏ VOICE_STUDIO_REPO vào một thư mục KHÔNG tồn tại = bản cài không có repo.
    st, src = _env.resolve_station()
    assert st is None and src == _env.UNSET
    with pytest.raises(StationMissing) as e:
        _env.station_dir()
    assert "VOICE_STATION" in str(e.value)


# ── hệ quả ở CLI ──────────────────────────────────────────────────────────────────────

def test_cli_on_unset_station_exits_3_with_hint(capsys, home):
    rc = cli.main(["export", "--personal", "--out", str(home / "x.zip"), "--json"])
    out = capsys.readouterr().out
    assert rc == 3
    res = last_json(out)
    assert res["ok"] is False and res["code"] == 3 and "VOICE_STATION" in res["error"]


def test_init_yes_in_clone_builds_repo_workspaces(repo, home, capsys):
    rc = cli.main(["init", "--yes", "--json"])
    res = last_json(capsys.readouterr().out)
    assert rc == 0 and res["mode"] == "embedded"
    assert same(res["station"], new_dir(repo))
    assert (new_dir(repo) / "station.json").is_file()
    assert not (repo / "workspace").exists()
    st, src = _env.resolve_station()
    assert same(st, new_dir(repo))
