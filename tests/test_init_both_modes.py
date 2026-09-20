"""`voice-studio init` — hai chế độ cài (F17): `embedded` (trạm trong <repo>/workspace/) và
`separate` (trạm ngoài, mặc định ~/.voice), nhận diện máy đã có trạm, `--existing`, `--dry-run`.

Mọi test chạy trong thư mục tạm: "repo" giả (VOICE_STUDIO_REPO) + HOME giả (conftest).
"""
import json
import os

import pytest

from conftest import last_json
from voice_studio import API_VERSION, _env, cli, station


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    (r / "voice_studio").mkdir(parents=True)
    (r / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (r / ".env.example").write_text(
        "# khuon\nVOICE_BGM_VOL=\nVOICE_STUDIO_WORK=\n", encoding="utf-8")
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(r))
    return r


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


def snapshot(*roots):
    out = set()
    for root in roots:
        for dp, dn, fn in os.walk(root):
            for n in dn + fn:
                out.add(os.path.join(dp, n))
    return out


def never_ask(_prompt):
    raise AssertionError("init không được hỏi trong trường hợp này")


def tree_ok(st):
    assert (st / "station.json").is_file()
    assert (st / "omnivoice" / "voices").is_dir()
    assert (st / "assets" / "bgm" / "bgm-library.json").is_file()
    assert (st / "out").is_dir() and (st / "cache").is_dir()
    info = json.loads((st / "station.json").read_text(encoding="utf-8"))
    assert info["contract"] == API_VERSION
    for key in ("device", "default_profile", "venv", "engine_dir", "bgm_dir", "mode"):
        assert key in info
    return info


# ── embedded ──────────────────────────────────────────────────────────────────────────

def test_enter_means_embedded(repo, home):
    prompts = []
    res = station.do_init(ask=lambda p: prompts.append(p) or "")
    ws = repo / "workspace"
    info = tree_ok(ws)
    assert res["mode"] == "embedded" and info["mode"] == "embedded"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(ws))
    # bảng lựa chọn có đủ hai chế độ + khuyến nghị embedded
    table = prompts[0]
    assert "embedded" in table and "separate" in table and "KHUYẾN NGHỊ" in table
    local = json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))
    assert local["mode"] == "embedded" and local["station_path"] == "workspace"
    assert "secrets" in local
    # cây mẫu được chép: giọng ví dụ trung tính (không audio)
    assert (ws / "omnivoice" / "voices" / "_example" / "README.md").is_file()
    assert not list(ws.rglob("*.wav"))
    # từ giờ mọi script phân giải ra đúng trạm này
    st, src = _env.resolve_station()
    assert os.path.normcase(st) == os.path.normcase(str(ws)) and src == "studio.local.json"
    assert not home.exists() or not (home / ".voice").exists()


def test_yes_flag_accepts_recommended_embedded(repo):
    res = station.do_init(yes=True, ask=never_ask)
    assert res["mode"] == "embedded" and (repo / "workspace" / "station.json").is_file()


def test_answer_2_means_separate_at_home_voice(repo, home):
    res = station.do_init(ask=lambda p: "2")
    assert res["mode"] == "separate"
    tree_ok(home / ".voice")
    assert not (repo / "workspace").exists()
    local = json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))
    assert local["mode"] == "separate"


def test_bad_answer_is_contract_error(repo):
    with pytest.raises(station.ContractError):
        station.do_init(ask=lambda p: "ba")
    assert not (repo / "workspace").exists()


# ── embedded: `.env` phải có thật, và phải có người đọc nó ───────────────────────────────
#
# Ba test dưới đây giữ lời hứa "clone là chạy". Trước đó `.env` được `.gitignore` chặn, hook
# chặn, `doctor` kiểm quyền — nhưng KHÔNG AI TẠO RA NÓ và KHÔNG AI ĐỌC NÓ. Tài liệu nói
# "secret ở <repo>/.env" là một câu không đúng với mã, kiểu sai im lặng nhất.

def test_embedded_lays_down_dotenv_from_the_example(repo):
    res = station.do_init(yes=True)
    env_file = repo / ".env"
    assert env_file.is_file() and ".env" in res["created"]
    assert "VOICE_BGM_VOL=" in env_file.read_text(encoding="utf-8")


def test_rerun_never_overwrites_a_filled_dotenv(repo):
    station.do_init(yes=True)
    (repo / ".env").write_text("VOICE_BGM_VOL=0.42\n", encoding="utf-8")
    res = station.do_init(yes=True)
    assert (repo / ".env").read_text(encoding="utf-8") == "VOICE_BGM_VOL=0.42\n"
    assert ".env" not in res["created"]


def test_embedded_reads_config_from_dotenv(repo, monkeypatch):
    station.do_init(yes=True)
    (repo / ".env").write_text(
        "# ghi chu\nexport VOICE_BGM_VOL = \"0.42\"\nrac khong co dau bang\n", encoding="utf-8")
    monkeypatch.delenv("VOICE_BGM_VOL", raising=False)
    assert _env.env("VOICE_BGM_VOL") == "0.42"


def test_a_real_environment_variable_beats_the_dotenv(repo, monkeypatch):
    station.do_init(yes=True)
    (repo / ".env").write_text("VOICE_BGM_VOL=0.42\n", encoding="utf-8")
    monkeypatch.setenv("VOICE_BGM_VOL", "0.99")
    assert _env.env("VOICE_BGM_VOL") == "0.99"


def test_separate_mode_never_loads_a_dotenv_sitting_in_the_repo(repo, tmp_path, monkeypatch):
    """Ở `separate`, repo có thể là bản public của chính người dùng: tự nạp một file lạ nằm
    trong đó là mở cửa cho nó."""
    station.do_init(station=str(tmp_path / "ngoai"))
    (repo / ".env").write_text("VOICE_BGM_VOL=0.42\n", encoding="utf-8")
    monkeypatch.delenv("VOICE_BGM_VOL", raising=False)
    assert _env.env_file() is None
    assert _env.env("VOICE_BGM_VOL") is None


def test_the_repo_pointer_is_never_taken_from_a_file_inside_the_repo(repo):
    """`VOICE_STUDIO_REPO` nói repo nằm đâu — một file TRONG repo không có tư cách trả lời,
    và đọc nó ở đây là đệ quy vô hạn."""
    station.do_init(yes=True)
    (repo / ".env").write_text("VOICE_STUDIO_REPO=/khong/ton/tai\n", encoding="utf-8")
    assert _env.read_env_file()["VOICE_STUDIO_REPO"] == "/khong/ton/tai"
    assert os.path.normcase(_env.repo_root()) == os.path.normcase(str(repo))


@pytest.mark.parametrize("argv", [["init", "--non-interactive", "--json"],
                                  ["init", "--json"]])
def test_no_one_to_answer_is_code_2_and_writes_nothing(argv, repo, home, capsys):
    """Khai `--non-interactive` KHÔNG có nghĩa "đoán hộ tôi": thiếu --yes/--mode/--station thì
    vẫn là mã 2, in bảng cho agent trình cho người dùng."""
    before = snapshot(repo)
    rc = cli.main(argv)
    out, err = capsys.readouterr()
    assert rc == 2
    assert "embedded" in err and "separate" in err and "KHUYẾN NGHỊ" in err
    assert "--mode" in err                      # agent phải biết chạy lại thế nào
    assert last_json(out)["ok"] is False
    assert snapshot(repo) == before and not (home / ".voice").exists()


def test_non_interactive_with_a_choice_goes_through(repo):
    rc = cli.main(["init", "--non-interactive", "--yes", "--json"])
    assert rc == 0 and (repo / "workspace" / "station.json").is_file()


def test_embedded_installs_precommit_hook_without_overwriting(repo):
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True)
    res = station.do_init(yes=True)
    hook = hooks / "pre-commit"
    assert hook.is_file() and "voice_studio.precommit" in hook.read_text(encoding="utf-8")
    assert res["hook"] == "installed"
    hook.write_text("#!/bin/sh\necho custom\n", encoding="utf-8")
    res2 = station.do_init(yes=True)
    assert "custom" in hook.read_text(encoding="utf-8") and res2["hook"] == "kept"


def test_embedded_without_repo_is_contract_error(tmp_path, monkeypatch):
    monkeypatch.setattr(_env, "repo_root", lambda: None)
    with pytest.raises(station.ContractError):
        station.do_init(mode="embedded")


# ── separate: tường minh và tự nhận diện (bảo vệ máy đã có trạm ngoài) ────────────────────

def test_station_flag_is_separate_without_asking(repo, tmp_path):
    st = tmp_path / "vs-st"
    res = station.do_init(station=str(st), ask=never_ask)
    assert res["mode"] == "separate" and res["reason"] == "--station"
    tree_ok(st)
    assert not (repo / "workspace").exists()
    local = json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))
    assert os.path.normcase(local["station_path"]) == os.path.normcase(str(st))


@pytest.mark.parametrize("var", ["VOICE_STATION", "OMNIVOICE_DIR"])
def test_env_station_forces_separate_even_with_yes(var, repo, tmp_path, monkeypatch):
    st = tmp_path / "old-station"
    monkeypatch.setenv(var, str(st / "omnivoice") if var == "OMNIVOICE_DIR" else str(st))
    res = station.do_init(yes=True, ask=never_ask)
    assert res["mode"] == "separate" and var in res["reason"]
    assert os.path.normcase(res["station"]) == os.path.normcase(str(st))
    assert not (repo / "workspace").exists()


def test_env_station_refuses_explicit_embedded(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    with pytest.raises(station.ContractError, match="hai nguồn"):
        station.do_init(mode="embedded")
    assert not (repo / "workspace").exists()


def test_home_voice_with_marker_forces_separate(repo, home):
    (home / ".voice" / "omnivoice" / "voices").mkdir(parents=True)
    res = station.do_init(ask=never_ask)
    assert res["mode"] == "separate" and "~/.voice" in res["reason"]
    assert not (repo / "workspace").exists()


def test_home_voice_without_marker_is_not_a_station(repo, home):
    (home / ".voice").mkdir(parents=True)          # thư mục rỗng: chưa phải trạm
    res = station.do_init(ask=lambda p: "")
    assert res["mode"] == "embedded"


# ── --dry-run, --existing, chạy lại ──────────────────────────────────────────────────────

def test_dry_run_writes_nothing(repo, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OMNIVOICE_DIR", str(tmp_path / "live" / "omnivoice"))
    before = snapshot(tmp_path)
    rc = cli.main(["init", "--dry-run", "--json"])
    out, _ = capsys.readouterr()
    res = last_json(out)
    assert rc == 0 and res["ok"] and res["dry_run"] is True
    assert res["mode"] == "separate" and "OMNIVOICE_DIR" in res["reason"]
    assert snapshot(tmp_path) == before


def make_live_copy(root):
    """Bản chép GIẢ của một trạm đang chạy: 2 profile (file rỗng), _default.txt, venv."""
    voices = root / "omnivoice" / "voices"
    voices.mkdir(parents=True)
    for n in ("alpha", "beta"):
        (voices / f"{n}.wav").write_bytes(b"")
        (voices / f"{n}.txt").write_text("lời mẫu", encoding="utf-8")
    (voices / "_default.txt").write_text("beta", encoding="utf-8")
    (root / "omnivoice" / ".venv").mkdir()
    return voices


def test_existing_detects_live_station_without_touching_it(repo, tmp_path):
    live = tmp_path / "live"
    voices = make_live_copy(live)
    before = {p: p.read_bytes() for p in voices.iterdir()}
    res = station.do_init(station=str(live), existing=True, ask=never_ask)
    info = json.loads((live / "station.json").read_text(encoding="utf-8"))
    assert info["venv"] == "omnivoice/.venv" and info["default_profile"] == "beta"
    assert info["engine_dir"] == "omnivoice" and res["profiles"] == 2
    assert {p: p.read_bytes() for p in voices.iterdir()} == before
    assert not (voices / "_example").exists()           # không rải mẫu vào kho giọng thật
    # --existing chỉ ghi station.json: không tạo thư mục nào trong trạm đang chạy
    assert sorted(p.name for p in live.iterdir()) == ["omnivoice", "station.json"]
    assert set(res["missing"]) == {"assets/bgm", "out", "cache"}


def test_eof_on_prompt_is_contract_error(repo):
    def eof(_p):
        raise EOFError
    with pytest.raises(station.ContractError, match="--mode"):
        station.do_init(ask=eof)
    assert not (repo / "workspace").exists()


def test_existing_on_missing_dir_is_2(repo, tmp_path, capsys):
    rc = cli.main(["init", "--station", str(tmp_path / "khong-co"), "--existing"])
    assert rc == 2 and not (tmp_path / "khong-co").exists()


def test_rerun_reuses_previous_separate_station(repo, tmp_path):
    st = tmp_path / "chon-truoc"
    station.do_init(station=str(st))
    res = station.do_init(ask=never_ask)           # chạy lại không cờ: không hỏi, cùng trạm
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(st))
    assert not (repo / "workspace").exists()


def test_rerun_keeps_user_edits(repo, tmp_path):
    st = tmp_path / "st"
    station.do_init(station=str(st))
    info = json.loads((st / "station.json").read_text(encoding="utf-8"))
    info["device"] = "cpu"
    (st / "station.json").write_text(json.dumps(info), encoding="utf-8")
    lib = st / "assets" / "bgm" / "bgm-library.json"
    lib.write_text('{"styles": []}', encoding="utf-8")
    station.do_init(station=str(st))
    assert json.loads((st / "station.json").read_text(encoding="utf-8"))["device"] == "cpu"
    assert lib.read_text(encoding="utf-8") == '{"styles": []}'


def test_init_prints_venv_commands_not_creating_venv(repo, tmp_path, capsys):
    rc = cli.main(["init", "--station", str(tmp_path / "st"), "--json"])
    out, err = capsys.readouterr()
    assert rc == 0 and last_json(out)["ok"]
    assert "venv" in err and "omnivoice==0.2.1" in err
    assert not (tmp_path / "st" / "omnivoice" / ".venv").exists()
