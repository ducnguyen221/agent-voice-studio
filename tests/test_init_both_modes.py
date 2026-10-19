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
    ws = repo / "workspaces"
    info = tree_ok(ws)
    assert res["mode"] == "embedded" and info["mode"] == "embedded"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(ws))
    # bảng lựa chọn có đủ hai chế độ + khuyến nghị embedded
    table = prompts[0]
    assert "embedded" in table and "separate" in table and "KHUYẾN NGHỊ" in table
    local = json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))
    assert local["mode"] == "embedded" and local["station_path"] == "workspaces"
    assert "secrets" in local
    # cây mẫu được chép: giọng ví dụ trung tính (không audio)
    assert (ws / "omnivoice" / "voices" / "_example" / "README.md").is_file()
    assert not list(ws.rglob("*.wav"))
    # từ giờ mọi script phân giải ra đúng trạm này
    st, src = _env.resolve_station()
    assert os.path.normcase(st) == os.path.normcase(str(ws)) and src == "workspaces"


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
    assert res["mode"] == "embedded" and (repo / "workspaces" / "station.json").is_file()


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
    assert not (repo / "workspaces").exists()
    local = json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))
    assert local["mode"] == "separate"
    assert os.path.normcase(local["station_path"]) == os.path.normcase(str(dest))


def test_answer_2_with_empty_path_stops_and_writes_nothing(repo, tmp_path):
    answers = iter(["2", "  "])
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(ask=lambda p: next(answers))
    assert not (repo / "workspaces").exists() and not (repo / "studio.local.json").exists()


def test_mode_separate_without_a_path_needs_station_when_nobody_can_answer(repo, home):
    """Không OPCOS_WORKSPACES, không --station, không người: không có đường mặc định nào để đoán."""
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(mode="separate", non_interactive=True)


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
    assert not (repo / "workspaces").exists() and not (repo / "studio.local.json").exists()


@pytest.mark.parametrize("wrap", ['"{}"', "'{}'", ' "{}" '])
def test_pasted_path_in_quotes_is_unwrapped(wrap, repo, tmp_path):
    """'Copy as path' của Windows dán đường kèm cặp ngoặc kép — đừng đưa nguyên cho hệ điều hành."""
    dest = tmp_path / "dan-vao"
    answers = iter(["2", wrap.format(dest)])
    res = station.do_init(ask=lambda p: next(answers))
    assert os.path.normcase(res["station"]) == os.path.normcase(str(dest))
    tree_ok(dest)


def test_station_pointing_at_a_file_is_a_contract_error(repo, tmp_path, capsys):
    f = tmp_path / "la-mot-file"
    f.write_text("x", encoding="utf-8")
    rc = cli.main(["init", "--station", str(f), "--json"])
    out, err = capsys.readouterr()
    assert rc == 2 and last_json(out)["ok"] is False and "thư mục" in err
    assert f.read_text(encoding="utf-8") == "x"


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
    assert not (repo / "workspaces").exists()


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
    assert os.path.normcase(st) == os.path.normcase(str(repo / "workspaces"))
    assert src == "workspaces"


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
    assert snapshot(repo) == before


def test_non_interactive_with_a_choice_goes_through(repo):
    rc = cli.main(["init", "--non-interactive", "--yes", "--json"])
    assert rc == 0 and (repo / "workspaces" / "station.json").is_file()


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
    assert not (repo / "workspaces").exists()
    local = json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))
    assert os.path.normcase(local["station_path"]) == os.path.normcase(str(st))


@pytest.mark.parametrize("var", ["VOICE_STATION", "OMNIVOICE_DIR"])
def test_env_station_forces_separate_even_with_yes(var, repo, tmp_path, monkeypatch):
    st = tmp_path / "old-station"
    monkeypatch.setenv(var, str(st / "omnivoice") if var == "OMNIVOICE_DIR" else str(st))
    res = station.do_init(yes=True, ask=never_ask)
    assert res["mode"] == "separate" and var in res["reason"]
    assert os.path.normcase(res["station"]) == os.path.normcase(str(st))
    assert not (repo / "workspaces").exists()


def test_env_station_refuses_explicit_embedded(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    with pytest.raises(station.ContractError, match="hai nguồn"):
        station.do_init(mode="embedded")
    assert not (repo / "workspaces").exists()


# ── bố cục trạm nhúng: <repo>/workspaces (tên số ít cũ vẫn được nhận, không bao giờ tạo mới) ──

def _old_station(repo):
    d = repo / "workspace"
    (d / "omnivoice" / "voices").mkdir(parents=True)
    (d / "station.json").write_text("{}", encoding="utf-8")
    return d


def test_new_station_lives_in_workspaces_and_never_singular(repo):
    res = station.do_init(yes=True)
    assert os.path.normcase(res["station"]) == os.path.normcase(str(repo / "workspaces"))
    assert (repo / "workspaces" / "station.json").is_file()
    assert not (repo / "workspace").exists()


def test_old_singular_workspace_is_adopted_with_one_line(repo, capsys):
    old = _old_station(repo)
    res = station.do_init(yes=True)
    assert res["mode"] == "embedded"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(old))
    assert not (repo / "workspaces").exists()                      # không dựng trạm thứ hai
    _out, err = capsys.readouterr()
    lines = [ln for ln in err.splitlines() if "workspaces" in ln and "workspace" in ln]
    assert len(lines) == 1 and str(old) in lines[0]                # MỘT dòng khuyến nghị đổi tên


def test_old_singular_workspace_resolves_for_every_command(repo, capsys):
    old = _old_station(repo)
    st, src = _env.resolve_station()
    assert os.path.normcase(st) == os.path.normcase(str(old)) and src == "workspace"


def test_both_layouts_prefer_workspaces_and_say_so(repo, capsys):
    _old_station(repo)
    (repo / "workspaces").mkdir(parents=True)
    st, src = _env.resolve_station()
    assert os.path.normcase(st) == os.path.normcase(str(repo / "workspaces"))
    assert src == "workspaces"
    _out, err = capsys.readouterr()
    assert "workspace" in err and "workspaces" in err


def test_empty_singular_workspace_is_not_a_station(repo):
    (repo / "workspace").mkdir()                                  # không có dấu trạm: bỏ qua
    res = station.do_init(yes=True)
    assert os.path.normcase(res["station"]) == os.path.normcase(str(repo / "workspaces"))


def test_no_home_directory_station_is_mentioned_anywhere():
    """Không còn dạng thư mục trạm ẩn dưới home: mã, test, tài liệu, trợ giúp (trừ lịch sử phát hành)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import re
    # tên thư mục ẩn dưới home (ghép chuỗi để file này không tự bắt mình); `x.voices_dir` / `self.voice` không tính
    # Dạng `~/.x`, `/.x/`, biến-home + `.x` của MỌI trạm anh em (giọng, video, marketing).
    needle = re.compile(r"(?<![A-Za-z0-9_)\]])\.(" + "|".join(("voi" + "ce", "vid" + "eo", "market" + "ing"))
                        + r")(?![A-Za-z0-9_])")
    allowed_changelog_prefix = "## 0.4.0"
    hits = []
    scanned = 0
    for sub in ("voice_studio", "studio", "tests", "docs", "skills", "templates", "hosts", "samples",
                "extras", "README.md", "README.vi.md", "GUIDE.md", "GUIDE.vi.md", "INSTALL.md",
                "START-HERE.md", "AGENTS.md", "ECOSYSTEM.md", ".env.example", ".gitignore", "pyproject.toml"):
        top = os.path.join(root, sub)
        if not os.path.exists(top):
            continue
        files = ([top] if os.path.isfile(top) else
                 [os.path.join(dp, n) for dp, _d, fn in os.walk(top) for n in fn
                  if n.endswith((".py", ".md", ".html", ".json", ".txt", ".example", ".toml"))
                  and "__pycache__" not in dp])
        for f in files:
            text = open(f, encoding="utf-8", errors="replace").read()
            scanned += 1
            if os.path.basename(f) == "CHANGELOG.md":
                head = text.split(allowed_changelog_prefix)[0]       # mục "Chưa phát hành" phải sạch
                text = head
            for i, line in enumerate(text.splitlines(), 1):
                if needle.search(line):
                    hits.append(f"{os.path.relpath(f, root)}:{i}")
    # Quét rỗng (đổi tên thư mục, sai đường) cũng "không có hit" — bắt buộc đã quét đủ nhiều file.
    assert scanned > 50, f"chỉ quét được {scanned} file: test canh chữ mất tác dụng"
    assert not hits, hits
    assert not hasattr(_env, "legacy_station") and not hasattr(_env, "default_station")


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
    assert not (repo / "workspaces").exists()


def test_existing_on_missing_dir_is_2(repo, tmp_path, capsys):
    rc = cli.main(["init", "--station", str(tmp_path / "khong-co"), "--existing"])
    assert rc == 2 and not (tmp_path / "khong-co").exists()


def test_rerun_reuses_previous_separate_station(repo, tmp_path):
    st = tmp_path / "chon-truoc"
    station.do_init(station=str(st))
    res = station.do_init(ask=never_ask)           # chạy lại không cờ: không hỏi, cùng trạm
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(st))
    assert not (repo / "workspaces").exists()


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
    before = set(os.listdir(opcos.parent))
    res = station.do_init(mode="separate", ask=never_ask)
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(opcos))
    local = read_local(repo)
    assert local["mode"] == "separate" and local["station_path"] == os.path.abspath(str(opcos))
    assert set(os.listdir(opcos.parent)) == before           # không tạo trạm/thư mục anh em
    assert not (repo / "workspaces").exists()


def test_init_separate_relative_opcos_workspaces_writes_absolute_path(repo, tmp_path, monkeypatch, sandbox_home):
    """OPCOS_WORKSPACES tương đối + cwd ≠ repo: station_path vẫn tuyệt đối và resolve_station() đúng."""
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


def test_init_interactive_with_opcos_var_asks_to_confirm_or_change(repo, opcos, sandbox_home, tmp_path):
    prompts = []
    res = station.do_init(ask=lambda p: prompts.append(p) or "")          # Enter = nhận đề xuất
    assert len(prompts) == 1 and os.path.normcase(str(opcos)) in os.path.normcase(prompts[0])
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(opcos))
    assert read_local(repo)["station_path"] == os.path.abspath(str(opcos))
    # gõ đường khác → dùng đường đó
    (repo / "studio.local.json").unlink()
    other = tmp_path / "khac"
    res = station.do_init(ask=lambda p: f'"{other}"')
    assert os.path.normcase(res["station"]) == os.path.normcase(str(other))
    assert read_local(repo)["station_path"] == os.path.abspath(str(other))
    assert not (repo / "workspaces").exists()


def test_init_mode_embedded_allowed_with_opcos_var(repo, opcos, sandbox_home):
    res = station.do_init(mode="embedded", ask=never_ask)    # không ContractError
    assert res["mode"] == "embedded" and (repo / "workspaces" / "station.json").is_file()


def test_init_again_on_embedded_clone_is_not_flipped(repo, opcos, sandbox_home):
    (repo / "studio.local.json").write_text(json.dumps({"mode": "embedded"}), encoding="utf-8")
    res = station.do_init(ask=never_ask)
    assert res["mode"] == "embedded"
    assert read_local(repo)["station_path"] == "workspaces"


def test_init_prev_separate_without_station_path_needs_a_station(repo, opcos, sandbox_home):
    # Thay `..._ignores_opcos`: lựa chọn đã ghi (`mode: separate`, chưa có station_path) thắng —
    # KHÔNG đề xuất trạm OpcOS, và cũng không còn đường mặc định để đoán: phải chỉ `--station`.
    (repo / "studio.local.json").write_text(json.dumps({"mode": "separate"}), encoding="utf-8")
    with pytest.raises(station.ContractError, match="--station"):
        station.do_init(ask=never_ask, dry_run=True)


@pytest.fixture
def bare_opcos(repo, tmp_path, monkeypatch, sandbox_home):
    """OPCOS_WORKSPACES có, `<biến>/voice` CHƯA mang dấu trạm (thư mục trống hoặc chưa có)."""
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


def test_init_without_opcos_var_asks_the_two_way_question_and_names_the_real_path(repo, sandbox_home):
    # Thay `..._asks_about_the_marked_home_directory`: không còn trạm cũ dưới home để hỏi.
    prompts = []
    res = station.do_init(ask=lambda p: prompts.append(p) or "")
    assert res["mode"] == "embedded"
    assert os.path.normcase(str(repo / "workspaces")) in os.path.normcase(prompts[0])


def test_init_opcos_var_does_not_override_detected_external(repo, opcos, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "chon"))
    res = station.do_init(ask=never_ask)
    assert os.path.normcase(res["station"]) == os.path.normcase(str(tmp_path / "chon"))


def test_venv_commands_weights_size_is_measured_value(tmp_path):
    cmds = "\n".join(station.venv_commands(str(tmp_path / "st"), windows=False))
    assert "3,3 GB" in cmds and "4 GB" not in cmds


# ── thay ba test khoá hành vi cũ (`--yes`/không người có biến ra trạm OpcOS) ───────────────────────────

def test_init_yes_with_opcos_var_builds_the_opcos_station(repo, opcos, sandbox_home, capsys):
    """Ô CL22 (thay `test_init_yes_with_opcos_var_stays_embedded`): `--yes` + biến ⇒ `<biến>/voice`, không hỏi."""
    res = station.do_init(yes=True, ask=never_ask)
    assert res["mode"] == "separate"
    assert os.path.normcase(res["station"]) == os.path.normcase(str(opcos))
    assert read_local(repo)["station_path"] == os.path.abspath(str(opcos))
    assert not (repo / "workspaces").exists()
    assert capsys.readouterr().err.count("OPCOS_WORKSPACES") == 0        # đã mang dấu ⇒ dùng thẳng, 0 dòng


def test_init_yes_builds_the_opcos_station_even_when_the_dir_has_no_marker(repo, tmp_path, monkeypatch, sandbox_home, capsys):
    """Ô CL22 (thay `test_init_yes_ignores_opcos_dir_without_marker`): thư mục chưa dấu ⇒ dựng ở đó + 1 dòng."""
    (tmp_path / "bare-ws" / "voice").mkdir(parents=True)
    monkeypatch.setenv("OPCOS_WORKSPACES", str(tmp_path / "bare-ws"))
    res = station.do_init(yes=True, ask=never_ask)
    want = tmp_path / "bare-ws" / "voice"
    assert res["mode"] == "separate" and os.path.normcase(res["station"]) == os.path.normcase(str(want))
    assert (want / "station.json").is_file() and not (repo / "workspaces").exists()
    err = capsys.readouterr().err
    assert str(want) in err and "--station" in err


def test_init_opcos_without_anyone_to_ask_builds_the_opcos_station(repo, opcos, capsys):
    """Ô CL25 (thay `..._non_interactive_without_yes_or_mode_is_code_2`): không người, có biến ⇒ trạm OpcOS, mã 0."""
    rc = cli.main(["init", "--non-interactive", "--json"])
    out, _err = capsys.readouterr()
    assert rc == 0 and last_json(out)["ok"] is True
    assert os.path.normcase(last_json(out)["station"]) == os.path.normcase(str(opcos))
    assert not (repo / "workspaces").exists()


def test_init_stdin_at_eof_with_opcos_var_uses_the_opcos_station(repo, opcos, monkeypatch, capsys):
    """Ô CL26 (FR2.3, CQ6): hết dữ liệu ở câu đường khi có biến = không có người ⇒ trạm OpcOS, mã 0."""
    def eof(_prompt):
        raise EOFError
    res = station.do_init(ask=eof)
    assert res["mode"] == "separate" and os.path.normcase(res["station"]) == os.path.normcase(str(opcos))


@pytest.mark.parametrize("typed", ["1", "2", "embedded", "separate", "Embedded"])
def test_init_bare_choice_at_the_path_question_is_code_2_and_creates_nothing(typed, repo, opcos, tmp_path, monkeypatch):
    """Ô CL29–CL32 (CQ1, FR2.4): `1`/`2`/`embedded`/`separate` ở câu nhận đường ⇒ mã 2; không tạo `<cwd>/1`."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(station.ContractError, match="--mode embedded"):
        station.do_init(ask=lambda p: typed)
    assert not (tmp_path / typed).exists() and not (repo / "studio.local.json").exists()


def test_init_typed_path_that_is_a_file_is_code_2_and_writes_nothing(repo, opcos, tmp_path):
    """Ô CL34: gõ một đường mà đường đó là FILE ở câu nhận đường ⇒ mã 2, chưa ghi gì."""
    f = tmp_path / "la-file"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(station.ContractError, match="FILE"):
        station.do_init(ask=lambda p: str(f))
    assert not (repo / "studio.local.json").exists() and not (repo / "workspaces").exists()
