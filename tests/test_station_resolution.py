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


CONFIGS = {
    "config-cu-ghi-workspace": {"mode": "embedded", "station_path": "workspace"},
    "config-moi-ghi-workspaces": {"mode": "embedded", "station_path": "workspaces"},
    "khong-config": None,
}


def build_layout(repo, layout):
    if layout in ("A-chi-co-cu", "C-co-ca-hai"):
        make_old_station(repo)
    if layout in ("B-chi-co-moi", "C-co-ca-hai"):
        new_dir(repo).mkdir(parents=True)


@pytest.mark.parametrize("cfg", sorted(CONFIGS))
@pytest.mark.parametrize("layout", ["A-chi-co-cu", "B-chi-co-moi", "C-co-ca-hai"])
def test_embedded_config_never_trusts_the_station_path_string(layout, cfg, repo, capsys):
    """`station_path` do `init` embedded ghi (`workspace` cũ / `workspaces` mới) KHÔNG được tin theo chữ:
    luôn đi qua bộ phân giải trạm nhúng chung (workspaces trước; tên cũ chỉ khi nó là trạm và workspaces
    chưa có; dùng tên cũ hoặc có cả hai thì in một dòng nhắc)."""
    build_layout(repo, layout)
    if CONFIGS[cfg] is not None:
        (repo / "studio.local.json").write_text(json.dumps(CONFIGS[cfg]), encoding="utf-8")
    st, src = _env.resolve_station()
    err = capsys.readouterr().err
    if layout == "A-chi-co-cu":                        # (A) chỉ có tên cũ: nhận đúng + nhắc đổi tên
        assert same(st, repo / "workspace") and src == "workspace"
        assert "workspaces" in err and str(repo / "workspace") in err
    elif layout == "B-chi-co-moi":                     # (B) đã đổi tên theo gợi ý: KHÔNG mất trạm
        assert same(st, new_dir(repo)) and src == "workspaces"
        assert err == ""
    else:                                              # (C) có cả hai: workspaces thắng + nhắc
        assert same(st, new_dir(repo)) and src == "workspaces"
        assert "workspaces" in err and str(repo / "workspace") in err


@pytest.mark.parametrize("cfg", ["config-cu-ghi-workspace", "config-moi-ghi-workspaces"])
def test_migrate_moves_the_resolved_embedded_station_when_both_exist(cfg, repo, tmp_path):
    from voice_studio import station
    build_layout(repo, "C-co-ca-hai")
    (new_dir(repo) / "station.json").write_text("{}", encoding="utf-8")
    (repo / "studio.local.json").write_text(json.dumps(CONFIGS[cfg]), encoding="utf-8")
    dest = tmp_path / "ngoai"
    station.migrate_to_separate(str(dest))
    assert (dest / "station.json").is_file() and not new_dir(repo).exists()
    assert (repo / "workspace").is_dir()                  # tên cũ không bị đụng


def test_init_embedded_writes_the_new_name_in_station_path(repo):
    from voice_studio import station
    make_old_station(repo)
    res = station.do_init(yes=True)
    assert same(res["station"], repo / "workspace")       # trạm cũ vẫn được dùng, không dựng trạm thứ hai
    sp = json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))["station_path"]
    assert sp == "workspaces"                              # nhưng khoá ghi theo tên mới


def test_separate_or_other_relative_station_path_is_kept_literally(repo, tmp_path):
    make_old_station(repo)
    (repo / "studio.local.json").write_text(
        json.dumps({"mode": "separate", "station_path": "workspace"}), encoding="utf-8")
    st, src = _env.resolve_station()
    assert same(st, repo / "workspace") and src == "studio.local.json"
    (repo / "studio.local.json").write_text(
        json.dumps({"mode": "embedded", "station_path": "rieng/tram"}), encoding="utf-8")
    st, src = _env.resolve_station()
    assert same(st, repo / "rieng" / "tram") and src == "studio.local.json"


def test_hidden_home_directory_station_is_never_used(repo, home):
    """Trạm giả đặt dưới HOME giả ở tên thư mục ẩn (chuỗi GHÉP: file test không chứa nguyên chuỗi):
    resolver, init và doctor KHÔNG được dùng, nhắc hay đụng vào nó."""
    from voice_studio import doctor, station
    hidden = home / ("." + "voice")
    (hidden / "omnivoice" / "voices").mkdir(parents=True)
    (hidden / "station.json").write_text("{}", encoding="utf-8")
    before = sorted(str(p) for p in hidden.rglob("*"))
    st, src = _env.resolve_station()
    assert same(st, new_dir(repo)) and src == "workspaces"
    res = station.do_init(yes=True)
    assert same(res["station"], new_dir(repo)) and res["mode"] == "embedded"
    text = json.dumps(doctor.run_checks(), ensure_ascii=False, default=str)
    assert str(hidden) not in text and ("." + "voice") not in text.replace("voice_studio", "")
    assert sorted(str(p) for p in hidden.rglob("*")) == before


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
