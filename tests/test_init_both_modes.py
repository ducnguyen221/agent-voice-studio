"""`voice-studio init` — hai chế độ cài (F17): `embedded` (trạm trong <repo>/workspace/) và
`separate` (trạm ngoài, đường do người dùng chỉ), nhận diện máy đã có trạm, `--existing`, `--dry-run`.

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


def test_the_choice_table_says_where_the_secrets_live(repo):
    """Cùng bốn mục với hai trạm kia (Là gì · Lợi · Hại · Chọn khi) và cùng nói ra chỗ đặt
    bí mật — người dùng gặp cả ba bộ cài, và ba câu chữ khác nhau là ba lần phải học lại."""
    t = station.CHOICE_TABLE
    for muc in ("Là gì", "Lợi", "Hại", "Chọn khi"):
        assert t.count(muc) >= 2, muc
    assert ".env" in t and station.SECRET_STORE in t
    assert "bấm Enter" in t and "migrate --to separate" in t


def test_yes_flag_accepts_recommended_embedded(repo):
    res = station.do_init(yes=True, ask=never_ask)
    assert res["mode"] == "embedded" and (repo / "workspace" / "station.json").is_file()


def test_answer_2_asks_where_the_separate_station_goes(repo, tmp_path):
    """Thay `test_answer_2_means_separate_at_home_voice`: `separate` không còn đoán một thư mục ẩn
    dưới home — người dùng được hỏi đường."""
    dest = tmp_path / "toi-chon"
    answers = iter(["2", str(dest)])
    prompts = []
    res = station.do_init(ask=lambda p: prompts.append(p) or next(answers))
    assert res["mode"] == "separate"
    tree_ok(dest)
    assert len(prompts) == 2 and "đường" in prompts[1]
    assert not (repo / "workspace").exists()
    local = json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))
    assert local["mode"] == "separate"
    assert os.path.normcase(local["station_path"]) == os.path.normcase(str(dest))


def test_answer_2_with_empty_path_stops_and_writes_nothing(repo, tmp_path):
    answers = iter(["2", "  "])
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(ask=lambda p: next(answers))
    assert not (repo / "workspace").exists() and not (repo / "studio.local.json").exists()


def test_mode_separate_without_a_path_needs_station_when_nobody_can_answer(repo, home):
    """Không OPCOS_WORKSPACES, không --station, không người: không có đường mặc định nào để đoán."""
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(mode="separate", non_interactive=True)
    assert not (home / ".voice").exists()


def test_mode_separate_without_a_path_asks_for_one_when_someone_can_answer(repo, tmp_path):
    """Truyền `--mode separate` mà có người ngồi đó: hỏi đường (trước đây là mã 2)."""
    dest = tmp_path / "toi-chon"
    prompts = []
    res = station.do_init(mode="separate", ask=lambda p: prompts.append(p) or str(dest))
    assert os.path.normcase(res["station"]) == os.path.normcase(str(dest))
    tree_ok(dest)
    assert len(prompts) == 1 and "đường" in prompts[0]


def test_mode_separate_empty_path_answer_stops(repo, home):
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(mode="separate", ask=lambda p: "")
    assert not (repo / "workspace").exists() and not (repo / "studio.local.json").exists()


@pytest.mark.parametrize("wrap", ['"{}"', "'{}'", ' "{}" '])
def test_pasted_path_in_quotes_is_unwrapped(wrap, repo, tmp_path):
    """'Copy as path' của Windows dán đường kèm cặp ngoặc kép — đừng đưa nguyên cho hệ điều hành."""
    dest = tmp_path / "dan-vao"
    answers = iter(["2", wrap.format(dest)])
    res = station.do_init(ask=lambda p: next(answers))
    assert os.path.normcase(res["station"]) == os.path.normcase(str(dest))
    tree_ok(dest)


def test_station_flag_in_quotes_is_unwrapped(repo, tmp_path):
    dest = tmp_path / "co-ngoac"
    res = station.do_init(station=f'"{dest}"', ask=never_ask)
    assert os.path.normcase(res["station"]) == os.path.normcase(str(dest))


def test_opcos_workspaces_is_read_in_exactly_one_place():
    """Một điểm đọc biến cấp máy: `_env.opcos_base()`. Chỗ khác đọc lại là hai nguồn sự thật."""
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice_studio")
    readers = []
    for dp, _d, fn in os.walk(root):
        for n in fn:
            if n.endswith(".py"):
                src = open(os.path.join(dp, n), encoding="utf-8").read()
                if "environ" in src and any(
                        ('"OPCOS_WORKSPACES"' in ln or "'OPCOS_WORKSPACES'" in ln)
                        and ("environ" in ln or "getenv" in ln) for ln in src.splitlines()):
                    readers.append(n)
    assert readers == ["_env.py"], readers


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


@pytest.mark.parametrize("var", ["VOICE_STUDIO_REPO", "VOICE_STATION", "OMNIVOICE_DIR"])
def test_a_dotenv_can_never_move_the_repo_or_the_station(var, repo):
    """Ba biến này quay ngược lại chính cái đã quyết định có đọc `.env` hay không: `.env` chỉ
    được nạp khi mode = embedded, tức trạm đã chốt ở <repo>/workspace/. Để một dòng trong đó
    trỏ trạm đi nơi khác là tự tạo ra "hai nguồn sự thật"."""
    station.do_init(yes=True)
    (repo / ".env").write_text(f"{var}=/khong/ton/tai\n", encoding="utf-8")
    assert _env.read_env_file()[var] == "/khong/ton/tai"     # đọc được nếu ai hỏi thẳng file
    assert _env.env(var) != "/khong/ton/tai"                 # nhưng env() không lấy từ đó
    assert os.path.normcase(_env.repo_root()) == os.path.normcase(str(repo))
    st, src = _env.resolve_station()
    assert os.path.normcase(st) == os.path.normcase(str(repo / "workspace"))
    assert src == "studio.local.json"


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


# Thay `test_home_voice_with_marker_forces_separate`: một thư mục ẩn dưới home mang dấu trạm là
# trạm CŨ cần quyết định, không phải trạm mặc định — `init` hỏi, không tự nhận.

def _legacy(home):
    (home / ".voice" / "omnivoice" / "voices").mkdir(parents=True)
    return home / ".voice"


def test_legacy_home_station_is_asked_not_adopted(repo, home):
    legacy = _legacy(home)
    before = snapshot(home)
    prompts = []
    res = station.do_init(ask=lambda p: prompts.append(p) or "")      # Enter = lựa chọn đầu
    assert res["mode"] == "embedded" and (repo / "workspace" / "station.json").is_file()
    t = prompts[0]
    # nhãn [1] khớp ĐƯỜNG THẬT sẽ dùng (không nói một đằng làm một nẻo)
    option1 = t.split("[2]")[0]
    assert str(legacy) in t and os.path.normcase(str(repo / "workspace")) in os.path.normcase(option1)
    assert res["mode"] == "embedded"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(repo / "workspace"))
    assert "[1]" in t and "[2]" in t and "[3]" in t
    assert "KHUYẾN NGHỊ" in t.split("[2]")[0]                          # [1] là khuyến nghị
    assert snapshot(home) == before                                    # trạm cũ không bị đụng


def test_legacy_home_station_answer_2_adopts_it(repo, home):
    legacy = _legacy(home)
    res = station.do_init(ask=lambda p: "2")
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(legacy))
    assert "người dùng" in res["reason"]
    assert not (repo / "workspace").exists()


def test_legacy_home_station_answer_3_stops_with_move_instructions(repo, home):
    legacy = _legacy(home)
    before = snapshot(home)
    with pytest.raises(station.ContractError, match="workspace"):
        station.do_init(ask=lambda p: "3")
    assert snapshot(home) == before
    assert not (repo / "workspace").exists() and not (repo / "studio.local.json").exists()
    assert legacy.is_dir()


def test_legacy_home_station_bad_answer_or_eof_stops(repo, home):
    _legacy(home)
    with pytest.raises(station.ContractError):
        station.do_init(ask=lambda p: "ba")

    def eof(_p):
        raise EOFError
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(ask=eof)
    assert not (repo / "workspace").exists()


def test_legacy_home_station_answer_1_uses_opcos_station_when_there_is_one(repo, tmp_path, monkeypatch, home):
    _legacy(home)
    ws = tmp_path / "opcos-ws"
    (ws / "voice").mkdir(parents=True)
    (ws / "voice" / "station.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
    res = station.do_init(ask=lambda p: "1")
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(ws / "voice"))


@pytest.mark.parametrize("flags", [["--yes"], ["--non-interactive", "--yes"]])
def test_legacy_home_station_is_never_adopted_without_a_person(flags, repo, home, capsys):
    legacy = _legacy(home)
    rc = cli.main(["init", "--json", *flags])
    out, err = capsys.readouterr()
    res = last_json(out)
    assert rc == 0 and res["mode"] == "embedded"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(repo / "workspace"))
    # một dòng cho người đọc: trạm cũ có đó, nhận nó bằng cách nào
    assert str(legacy) in err and f"--station {legacy}" in err
    assert not (legacy / "station.json").exists()


def test_legacy_home_station_without_a_choice_is_code_2(repo, home, capsys):
    legacy = _legacy(home)
    before = snapshot(home, repo)
    rc = cli.main(["init", "--non-interactive", "--json"])
    out, err = capsys.readouterr()
    assert rc == 2 and last_json(out)["ok"] is False
    assert str(legacy) in err and "--station" in err
    assert snapshot(home, repo) == before


def test_legacy_home_station_does_not_block_explicit_embedded(repo, home):
    legacy = _legacy(home)
    res = station.do_init(mode="embedded", ask=never_ask)
    assert res["mode"] == "embedded" and (repo / "workspace" / "station.json").is_file()
    assert not (legacy / "station.json").exists()


def test_legacy_home_station_is_not_asked_again_after_a_choice(repo, home):
    _legacy(home)
    (repo / "studio.local.json").write_text(json.dumps({"mode": "embedded"}), encoding="utf-8")
    res = station.do_init(ask=never_ask)
    assert res["mode"] == "embedded"


def test_explicit_station_flag_still_adopts_the_legacy_directory(repo, home):
    legacy = _legacy(home)
    res = station.do_init(station=str(legacy), existing=True, ask=never_ask)
    assert res["mode"] == "separate" and res["reason"] == "--station"


def test_no_default_home_station_wording_left_in_code():
    """Không dòng mã/doc nào còn gọi `~/.voice` là đường mặc định."""
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = re.compile(r"(mặc định|mac dinh|default)[^\n]{0,24}~/\.voice|~/\.voice[^\n]{0,24}(mặc định|default)",
                     re.IGNORECASE)
    hits = []
    for sub in ("voice_studio", "docs", "skills", "templates", "README.md", "README.vi.md",
                "GUIDE.md", "GUIDE.vi.md", "INSTALL.md", "START-HERE.md"):
        top = os.path.join(root, sub)
        files = ([top] if os.path.isfile(top) else
                 [os.path.join(dp, n) for dp, _d, fn in os.walk(top) for n in fn
                  if n.endswith((".py", ".md", ".html", ".json"))])
        for f in files:
            if os.path.basename(f) == "CHANGELOG.md":
                continue                                  # lịch sử phát hành kể chuyện cũ
            for i, line in enumerate(open(f, encoding="utf-8"), 1):
                if bad.search(line):
                    hits.append(f"{os.path.relpath(f, root)}:{i}")
    assert not hits, hits
    assert not hasattr(_env, "default_station")


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


def test_init_prints_venv_commands_not_creating_venv(repo, tmp_path, capsys, monkeypatch):
    # Không có venv dự án khác (máy giọng độc lập) — tách khỏi venv đang chạy test.
    monkeypatch.setattr(station, "host_venv", lambda *a, **k: None)
    rc = cli.main(["init", "--station", str(tmp_path / "st"), "--json"])
    out, err = capsys.readouterr()
    assert rc == 0 and last_json(out)["ok"]
    assert "venv" in err and "omnivoice==0.2.1" in err
    # engine cài qua phần phụ [engine] ⇒ transformers nằm trong khoảng đã đo, không tự trôi
    assert "[engine]" in err
    assert not (tmp_path / "st" / "omnivoice" / ".venv").exists()


@pytest.mark.parametrize("windows", [True, False])
def test_venv_commands_use_the_os_shell_syntax(windows, tmp_path):
    cmds = station.venv_commands(str(tmp_path / "st"), windows=windows)
    engine_calls = cmds[1:-1]
    if windows:
        assert all(c.startswith('& "') and "Scripts" in c for c in engine_calls)
        assert cmds[-1].startswith("$env:OMNIVOICE_ONLINE")
    else:
        assert all(c.startswith('"') and "/bin/python" in c.replace(os.sep, "/") for c in engine_calls)
        assert cmds[-1].startswith("OMNIVOICE_ONLINE=1 ")
    # doctor không tải gì — lệnh tải weights là lần tổng hợp đầu, không phải doctor
    assert "doctor" not in cmds[-1] and "speak" in cmds[-1]


# ── P2-8: voice_studio chạy từ venv của dự án khác (vd .venv của repo video) ──────────────

def _host(engine_ok, cached, prefix="/somewhere/agent-video-studio/.venv"):
    return {"prefix": prefix, "project": os.path.dirname(prefix), "engine": engine_ok,
            "weights_cached": cached, "hf_cache": "/hf/hub"}


def test_init_in_other_projects_venv_does_not_ask_for_engine_venv(repo, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(station, "host_venv", lambda *a, **k: _host(True, True))
    rc = cli.main(["init", "--station", str(tmp_path / "st"), "--json"])
    out, err = capsys.readouterr()
    assert rc == 0 and last_json(out)["host_venv"]["engine"] is True
    assert "agent-video-studio/.venv" in err
    assert "Bước tiếp theo" not in err and "python -m venv" not in err
    assert "GB" not in err                                  # weights đã có: không nói chuyện tải
    assert "không tải lại" in err


def test_init_in_other_projects_venv_without_engine_points_to_that_venv(repo, tmp_path, capsys,
                                                                        monkeypatch):
    monkeypatch.setattr(station, "host_venv", lambda *a, **k: _host(False, False))
    rc = cli.main(["init", "--station", str(tmp_path / "st")])
    _, err = capsys.readouterr()
    assert rc == 0
    assert "python -m venv" not in err and "omnivoice/.venv" in err   # nói rõ: KHÔNG tạo nó
    assert "VÀO venv này" in err and "[engine]" in err and "-e" in err
    assert "3,3 GB" in err and "4 GB" not in err


def test_host_venv_classifies_prefixes(tmp_path):
    st = tmp_path / "st"
    rep = tmp_path / "voice-repo"
    video = tmp_path / "agent-video-studio"
    video.mkdir()
    (video / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    base = str(tmp_path / "python312")

    def hv(prefix, engine_ok):
        return station.host_venv(str(st), str(rep), prefix=str(prefix), base_prefix=base,
                                 engine_ok=engine_ok)

    # python hệ thống (không phải venv) · venv engine chuẩn · venv nhẹ trong repo giọng
    assert station.host_venv(str(st), str(rep), prefix=base, base_prefix=base) is None
    assert hv(st / "omnivoice" / ".venv", True) is None
    assert hv(rep / ".venv", True) is None
    # venv lẻ chưa có engine, không thuộc dự án nào ⇒ vẫn in lệnh tạo venv engine
    assert hv(tmp_path / "loose-venv", False) is None
    # venv lẻ ĐÃ có engine ⇒ dùng luôn
    assert hv(tmp_path / "loose-venv", True)["project"] is None
    # venv của dự án khác (repo video), có hay chưa có engine
    for engine_ok in (True, False):
        got = hv(video / ".venv", engine_ok)
        assert got["project"] == str(video) and got["engine"] is engine_ok
        assert set(got) == {"prefix", "project", "engine", "weights_cached", "hf_cache"}
        assert got["weights_cached"] is False               # HOME giả: cache rỗng


# ── trạm OpcOS: OPCOS_WORKSPACES chỉ được đọc ở init/doctor ───────────────────

@pytest.fixture
def opcos(tmp_path, monkeypatch, sandbox_home):
    """OPCOS_WORKSPACES trỏ thư mục có `voice/station.json`; trả đường trạm OpcOS."""
    ws = tmp_path / "opcos-ws"
    (ws / "voice").mkdir(parents=True)
    (ws / "voice" / "station.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
    return ws / "voice"


def read_local(repo):
    return json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))


def test_init_mode_separate_defaults_to_opcos_station_and_writes_absolute_path(repo, opcos, sandbox_home):
    (sandbox_home / ".voice" / "station.json").unlink()      # chỉ còn trạm OpcOS, không ext ở home
    before = set(os.listdir(opcos.parent))
    res = station.do_init(mode="separate", ask=never_ask)
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(opcos))
    local = read_local(repo)
    assert local["mode"] == "separate" and local["station_path"] == os.path.abspath(str(opcos))
    assert set(os.listdir(opcos.parent)) == before           # không tạo trạm/thư mục anh em
    assert not (repo / "workspace").exists()
    assert not (sandbox_home / ".voice" / "omnivoice").exists()


def test_init_separate_relative_opcos_workspaces_writes_absolute_path(repo, tmp_path, monkeypatch, sandbox_home):
    """OPCOS_WORKSPACES tương đối + cwd ≠ repo: station_path vẫn tuyệt đối và resolve_station() đúng."""
    (sandbox_home / ".voice" / "station.json").unlink()
    cwd = tmp_path / "elsewhere"
    (cwd / "ws" / "voice").mkdir(parents=True)
    (cwd / "ws" / "voice" / "station.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("OPCOS_WORKSPACES", "ws")
    res = station.do_init(mode="separate", ask=never_ask)
    want = os.path.abspath(str(cwd / "ws" / "voice"))
    assert os.path.normcase(res["station"]) == os.path.normcase(want)
    sp = read_local(repo)["station_path"]
    assert os.path.isabs(sp) and os.path.normcase(sp) == os.path.normcase(want)
    monkeypatch.chdir(tmp_path)                              # đổi cwd: con trỏ vẫn đúng
    got, _src = _env.resolve_station()
    assert os.path.normcase(got) == os.path.normcase(want)


def test_init_interactive_proposes_opcos_station(repo, opcos, sandbox_home):
    (sandbox_home / ".voice" / "station.json").unlink()
    prompts = []
    res = station.do_init(ask=lambda p: prompts.append(p) or "2")
    assert str(opcos) in prompts[0]                          # bảng nêu đường trạm OpcOS
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(opcos))
    assert read_local(repo)["station_path"] == os.path.abspath(str(opcos))
    # trả lời nhận embedded → embedded
    (repo / "studio.local.json").unlink()
    res = station.do_init(ask=lambda p: "1")
    assert res["mode"] == "embedded"
    assert read_local(repo)["station_path"] == "workspace"


def test_init_yes_with_opcos_var_stays_embedded(repo, opcos, sandbox_home):
    (sandbox_home / ".voice" / "station.json").unlink()
    res = station.do_init(yes=True, ask=never_ask)
    assert res["mode"] == "embedded"
    assert read_local(repo)["station_path"] == "workspace"
    assert str(opcos) not in json.dumps(read_local(repo))


def test_init_mode_embedded_allowed_with_opcos_var(repo, opcos, sandbox_home):
    (sandbox_home / ".voice" / "station.json").unlink()
    res = station.do_init(mode="embedded", ask=never_ask)    # không ContractError
    assert res["mode"] == "embedded" and (repo / "workspace" / "station.json").is_file()


def test_init_again_on_embedded_clone_is_not_flipped(repo, opcos, sandbox_home):
    (sandbox_home / ".voice" / "station.json").unlink()
    (repo / "studio.local.json").write_text(json.dumps({"mode": "embedded"}), encoding="utf-8")
    res = station.do_init(ask=never_ask)
    assert res["mode"] == "embedded"
    assert read_local(repo)["station_path"] == "workspace"


def test_init_yes_ignores_opcos_dir_without_marker(repo, tmp_path, monkeypatch, sandbox_home):
    (sandbox_home / ".voice" / "station.json").unlink()
    (tmp_path / "bare-ws" / "voice").mkdir(parents=True)     # thư mục có, không dấu trạm
    monkeypatch.setenv("OPCOS_WORKSPACES", str(tmp_path / "bare-ws"))
    res = station.do_init(yes=True, ask=never_ask)
    assert res["mode"] == "embedded" and "station_path" in read_local(repo)
    assert read_local(repo)["station_path"] == "workspace"


def test_init_prev_separate_without_station_path_needs_a_station(repo, opcos, sandbox_home):
    # Thay `..._ignores_opcos`: lựa chọn đã ghi (`mode: separate`, chưa có station_path) thắng —
    # KHÔNG đề xuất trạm OpcOS, và cũng không còn đường mặc định để đoán: phải chỉ `--station`.
    (sandbox_home / ".voice" / "station.json").unlink()
    (repo / "studio.local.json").write_text(json.dumps({"mode": "separate"}), encoding="utf-8")
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(ask=never_ask, dry_run=True)


@pytest.fixture
def bare_opcos(repo, tmp_path, monkeypatch, sandbox_home):
    """OPCOS_WORKSPACES có, `<biến>/voice` CHƯA mang dấu trạm (thư mục trống hoặc chưa có)."""
    (sandbox_home / ".voice" / "station.json").unlink()
    base = tmp_path / "bare-ws"
    (base / "voice").mkdir(parents=True)
    monkeypatch.setenv("OPCOS_WORKSPACES", str(base))
    return base / "voice"


def test_init_mode_separate_opcos_dir_without_marker_is_suggested_and_confirmed(repo, bare_opcos):
    # Thay `..._uses_default` rồi `..._needs_a_station`: `--mode separate` + OPCOS_WORKSPACES là
    # `<biến>/voice` (tuyệt đối) kể cả khi thư mục chưa mang dấu; có người thì HỎI xác nhận/đổi.
    prompts = []
    res = station.do_init(mode="separate", ask=lambda p: prompts.append(p) or "")
    assert os.path.normcase(res["station"]) == os.path.normcase(str(bare_opcos))
    assert len(prompts) == 1 and os.path.normcase(str(bare_opcos)) in os.path.normcase(prompts[0])
    tree_ok(bare_opcos)
    assert read_local(repo)["station_path"] == os.path.abspath(str(bare_opcos))


def test_init_mode_separate_opcos_suggestion_can_be_changed(repo, bare_opcos, tmp_path):
    other = tmp_path / "khac"
    res = station.do_init(mode="separate", ask=lambda p: f'"{other}"')
    assert os.path.normcase(res["station"]) == os.path.normcase(str(other))
    assert not (bare_opcos / "station.json").exists()


def test_init_mode_separate_opcos_without_one_to_ask_uses_it_and_says_so(repo, bare_opcos, capsys):
    res = station.do_init(mode="separate", non_interactive=True)
    assert os.path.normcase(res["station"]) == os.path.normcase(str(bare_opcos))
    _, err = capsys.readouterr()
    assert str(bare_opcos) in err and "OPCOS_WORKSPACES" in err


def test_init_mode_separate_opcos_cli_non_interactive(repo, bare_opcos, capsys):
    rc = cli.main(["init", "--mode", "separate", "--non-interactive", "--json"])
    out, err = capsys.readouterr()
    assert rc == 0 and os.path.normcase(last_json(out)["station"]) == os.path.normcase(str(bare_opcos))
    assert str(bare_opcos) in err


def test_init_mode_separate_relative_opcos_is_absolute(repo, tmp_path, monkeypatch, sandbox_home):
    (sandbox_home / ".voice" / "station.json").unlink()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPCOS_WORKSPACES", "rel-ws")
    res = station.do_init(mode="separate", non_interactive=True, dry_run=True)
    assert os.path.isabs(res["station"])
    assert os.path.normcase(res["station"]) == os.path.normcase(str(tmp_path / "rel-ws" / "voice"))


def test_init_prev_separate_ignores_the_unmarked_opcos_dir(repo, bare_opcos):
    # Lựa chọn đã ghi thiếu station_path: vẫn phải chỉ `--station`, không lấy trạm OpcOS thay.
    (repo / "studio.local.json").write_text(json.dumps({"mode": "separate"}), encoding="utf-8")
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(ask=never_ask, dry_run=True)


def test_init_without_opcos_var_asks_about_the_marked_home_directory(repo, sandbox_home):
    # Thay `..._unchanged`: biến vắng + trạm cũ mang dấu (trạm mồi) → hỏi, không tự nhận.
    prompts = []
    res = station.do_init(ask=lambda p: prompts.append(p) or "")
    assert res["mode"] == "embedded"
    assert os.path.normcase(str(repo / "workspace")) in os.path.normcase(prompts[0])


def test_init_opcos_var_does_not_override_detected_external(repo, opcos, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "chon"))
    res = station.do_init(ask=never_ask)
    assert os.path.normcase(res["station"]) == os.path.normcase(str(tmp_path / "chon"))


def test_venv_commands_weights_size_is_measured_value(tmp_path):
    cmds = "\n".join(station.venv_commands(str(tmp_path / "st"), windows=False))
    assert "3,3 GB" in cmds and "4 GB" not in cmds
