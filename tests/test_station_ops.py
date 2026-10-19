"""Vận hành trạm: `export --personal` / `import` (chuyển máy), `backup`, `migrate --to separate`,
`update` (git pull --ff-only), `doctor` phần F17, và hook pre-commit của chế độ embedded.

Không có mạng: `update` chạy trên một "origin" là repo git trần trong thư mục tạm.
"""
import contextlib
import json
import ntpath
import os
import posixpath
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from conftest import last_json
from voice_studio import _env, cli, doctor, precommit, station

HAS_GIT = shutil.which("git") is not None
GIT_ENV = dict(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")


def git(cwd, *args, check=True):
    env = dict(os.environ, **GIT_ENV)
    return subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "core.hooksPath=",
                           *args], cwd=str(cwd), env=env, capture_output=True, text=True,
                          check=check, timeout=60)


@pytest.fixture
def live(tmp_path):
    """Trạm có dữ liệu cá nhân GIẢ + đủ loại rác không được vào gói."""
    st = tmp_path / "st"
    v = st / "omnivoice" / "voices"
    v.mkdir(parents=True)
    (v / "demo.wav").write_bytes(b"RIFF")
    (v / "demo.txt").write_text("lời mẫu", encoding="utf-8")
    (v / "_default.txt").write_text("demo", encoding="utf-8")
    (v / "demo.prompt.pt").write_bytes(b"cache")
    bgm = st / "assets" / "bgm"
    bgm.mkdir(parents=True)
    (bgm / "bgm-library.json").write_text('{"styles":[{"name":"neutral"}]}', encoding="utf-8")
    (bgm / "neutral.mp3").write_bytes(b"ID3")
    (st / "station.json").write_text('{"contract":"1.0.0"}', encoding="utf-8")
    (st / "omnivoice" / ".venv" / "Lib").mkdir(parents=True)
    (st / "omnivoice" / ".venv" / "Lib" / "x.py").write_text("", encoding="utf-8")
    (st / "cache").mkdir()
    (st / "cache" / "c.bin").write_bytes(b"c")
    (st / "out").mkdir()
    (st / "out" / "a.wav").write_bytes(b"o")
    return st


PERSONAL = {"omnivoice/voices/demo.wav", "omnivoice/voices/demo.txt",
            "omnivoice/voices/_default.txt", "assets/bgm/bgm-library.json",
            "assets/bgm/neutral.mp3", "station.json"}


# ── export --personal / import ─────────────────────────────────────────────────────────

def test_export_personal_packs_exactly_the_personal_set(live, tmp_path, capsys):
    z = tmp_path / "p.zip"
    rc = cli.main(["export", "--personal", "--station", str(live), "--out", str(z), "--json"])
    res = last_json(capsys.readouterr()[0])
    assert rc == 0 and res["ok"]
    names = set(zipfile.ZipFile(z).namelist())
    assert names - {station.MANIFEST} == PERSONAL
    manifest = json.loads(zipfile.ZipFile(z).read(station.MANIFEST))
    assert manifest["kind"] == "personal" and set(manifest["files"]) == PERSONAL


@pytest.mark.parametrize("bad", ["omnivoice/voices/x_token.json", "assets/bgm/.env",
                                 "omnivoice/voices/client_secret.json"])
def test_export_refuses_secret_like_files(bad, live, tmp_path, capsys):
    (live / bad).write_text("{}", encoding="utf-8")
    z = tmp_path / "p.zip"
    rc = cli.main(["export", "--personal", "--station", str(live), "--out", str(z)])
    assert rc == 2 and not z.exists()
    assert os.path.basename(bad) in capsys.readouterr()[1]


@pytest.mark.parametrize("name", ["demo.prompt.pt", "DEMO.PROMPT.PT", "Demo.Prompt.Pt",
                                  "omnivoice/voices/a.PYC", "b.pyc"])
def test_skip_file_same_verdict_on_every_os(name):
    """Luật đóng gói không được đổi theo hệ điều hành.

    `fnmatch.fnmatch` gọi `os.path.normcase`: trên Windows nó hạ hoa/thường, trên POSIX
    không. Để nguyên thì `DEMO.PROMPT.PT` bị bỏ qua ở máy này mà lọt vào `export --personal`
    ở máy kia — gói phình lên vì cache dựng lại được, và không ai đoán ra vì sao hai máy
    khác nhau. Test này chạy y hệt trên cả hai OS đích.
    """
    assert station._skip_file(name) is True, name


@pytest.mark.parametrize("name", ["demo.wav", "prompt.pt.txt", "station.json", "a.pycx"])
def test_skip_file_keeps_real_files(name):
    assert station._skip_file(name) is False, name


@pytest.mark.parametrize("name", ["X_TOKEN.json", ".ENV", "Client_Secret.json", "key.PEM"])
def test_is_secret_name_same_verdict_on_every_os(name):
    assert station._is_secret_name(name) is True, name


def test_export_without_personal_is_2(live, tmp_path):
    assert cli.main(["export", "--station", str(live), "--out", str(tmp_path / "p.zip")]) == 2


def test_import_roundtrip_and_conflicts(live, tmp_path):
    z = tmp_path / "p.zip"
    station.export_personal(str(live), str(z))
    new = tmp_path / "new"
    res = station.import_personal(str(z), str(new))
    assert set(res["written"]) == PERSONAL
    assert (new / "omnivoice" / "voices" / "demo.txt").read_text(encoding="utf-8") == "lời mẫu"
    # lần hai: trùng file ⇒ từ chối cả gói, không ghi gì
    (new / "omnivoice" / "voices" / "demo.txt").write_text("sửa tay", encoding="utf-8")
    with pytest.raises(station.ContractError, match="đã có"):
        station.import_personal(str(z), str(new))
    assert (new / "omnivoice" / "voices" / "demo.txt").read_text(encoding="utf-8") == "sửa tay"
    station.import_personal(str(z), str(new), force=True)
    assert (new / "omnivoice" / "voices" / "demo.txt").read_text(encoding="utf-8") == "lời mẫu"


def test_import_rejects_path_traversal(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr(station.MANIFEST, json.dumps({"kind": "personal", "files": ["../x.txt"]}))
        zf.writestr("../x.txt", "x")
    with pytest.raises(station.ContractError):
        station.import_personal(str(z), str(tmp_path / "st"))
    assert not (tmp_path / "x.txt").exists()


@pytest.mark.parametrize("member", [
    "foo/C:/x.txt",          # ổ đĩa ở part GIỮA: os.path.join của Windows RESET tại đó ⇒ 'C:\\x.txt'
    "foo/c:nasty.txt",       # ổ đĩa + tên file, không dấu gạch ⇒ 'c:nasty.txt' (thư mục hiện hành ổ C)
    "C:/x.txt",              # ổ đĩa ngay part đầu
    "C:x.txt",
    "../x.txt",              # thoát lên trên
    "foo/../../x.txt",
    "/etc/x.txt",            # đường tuyệt đối POSIX
    "\\\\?\\C:\\x.txt",      # tiền tố đường dài Windows
    "\\\\server\\share\\x.txt",   # UNC
    "",
    "foo//x.txt",
])
def test_safe_member_rejects_every_escape(member):
    assert station._safe_member(member) is False, member


@pytest.mark.parametrize("member", ["a.txt", "omnivoice/voices/demo.wav", "a/b/c.txt"])
def test_safe_member_accepts_plain_relative(member):
    assert station._safe_member(member) is True, member


@contextlib.contextmanager
def path_flavour(mod):
    """Ép `os.path` sang một họ đường dẫn (`posixpath` / `ntpath`) trong một đoạn HẸP.

    `station` gọi `os.path.*`, nên đổi thuộc tính `os.path` là đổi ở cấp TIẾN TRÌNH — mọi
    thư viện khác trong lúc đó cũng thấy. Vì vậy: chỉ bọc đúng lời gọi cần đo, gom kết quả
    ra biến, và **assert bên ngoài** — nếu assert đỏ thì traceback của pytest vẫn chạy trên
    `os.path` thật.
    """
    old = os.path
    os.path = mod
    try:
        yield
    finally:
        os.path = old


# Trạm giả cho từng họ: phải TUYỆT ĐỐI **theo chính họ đó**. Đưa đường Windows vào
# `posixpath` thì `realpath` không còn bất biến (mỗi lần gọi lại ghép thêm cwd vào đầu) và
# test sẽ đỏ vì đồ nghề, không phải vì cổng.
PATH_FLAVOURS = [
    pytest.param(posixpath, "/srv/voice-station/st", id="posix"),
    pytest.param(ntpath, "C:\\srv\\voice-station\\st", id="windows"),
]


@pytest.mark.parametrize("flavour, st", PATH_FLAVOURS)
def test_member_target_is_a_second_gate(monkeypatch, flavour, st):
    """Lớp hai (commonpath) phải tự đứng vững: cho `_safe_member` nói dối rồi kiểm lại.

    Chạy HAI LƯỢT, mỗi họ đường dẫn một lượt, nên khẳng định không còn phụ thuộc OS đang
    chạy test. Cạm bẫy đã trả giá: `"D:/x.txt"` là đường TUYỆT ĐỐI trên Windows nhưng chỉ là
    một TÊN THƯ MỤC hợp lệ trên POSIX — viết assert theo một họ thì xanh ở đây, đỏ ở kia.

    Hợp đồng thật của lớp hai, phát biểu một lần cho mọi họ: **trả None khi và chỉ khi đích
    rơi ra ngoài trạm.** Nên `D:/x.txt` bị chặn ở họ Windows (khác ổ) mà được nhận ở họ
    POSIX (thư mục tên `D:` NẰM TRONG trạm — không có gì để chặn; lớp một vẫn từ chối nó vì
    có dấu hai chấm, xem test riêng ở trên).

    Phạm vi lớp hai KHÔNG bao: `foo/C:/x.txt` khi trạm cũng nằm trên ổ C, vì `os.path.join`
    nuốt luôn `C:` cùng ổ — ca đó là việc của lớp một.
    """
    monkeypatch.setattr(station, "_safe_member", lambda n: True)
    names = ("../x.txt", "foo/../../../x.txt", "D:/x.txt", "omnivoice/voices/demo.wav")
    with path_flavour(flavour):
        root = flavour.realpath(st)
        got = {n: station._member_target(st, n) for n in names}

    assert got["../x.txt"] is None, "thoát lên trên phải bị chặn ở mọi họ đường dẫn"
    assert got["foo/../../../x.txt"] is None, "thoát nhiều cấp phải bị chặn ở mọi họ"
    if flavour is ntpath:
        assert got["D:/x.txt"] is None, "ổ đĩa khác = ngoài trạm ⇒ họ Windows phải chặn"
    else:
        assert got["D:/x.txt"] is not None and \
            got["D:/x.txt"].startswith(root + flavour.sep), \
            "trên POSIX `D:` chỉ là tên thư mục trong trạm — chặn ở đây là chặn nhầm"
    good = got["omnivoice/voices/demo.wav"]
    assert good is not None and good.endswith(flavour.join("voices", "demo.wav"))


def test_import_rejects_windows_drive_member(tmp_path, monkeypatch):
    """`voice-studio import` một gói 'giọng của bạn tôi' không được ghi ra ngoài trạm.

    `chdir` vào tmp_path có chủ đích: khi cổng hỏng, `os.path.join` trả đường **theo ổ đĩa**
    (`C:x.txt`) — tức ghi vào thư mục hiện hành của ổ C. Đứng ở tmp_path thì vết đổ đúng vào
    `tmp_path/x.txt`, vừa chứng minh được rò, vừa không rải rác ra repo.
    """
    monkeypatch.chdir(tmp_path)
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr(station.MANIFEST, json.dumps({"kind": "personal", "files": ["foo/C:/x.txt"]}))
        zf.writestr("foo/C:/x.txt", "x")
    with pytest.raises(station.ContractError, match="nguy hiểm"):
        station.import_personal(str(z), str(tmp_path / "st"))
    assert not (tmp_path / "x.txt").exists(), "RÒ: gói ghi được ra ngoài trạm"


def test_import_rejects_zip_without_manifest(tmp_path):
    z = tmp_path / "plain.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "a")
    with pytest.raises(station.ContractError, match="không phải gói"):
        station.import_personal(str(z), str(tmp_path / "st"))


# ── backup / migrate ───────────────────────────────────────────────────────────────────

@pytest.fixture
def embedded_repo(tmp_path, monkeypatch, live):
    r = tmp_path / "repo"
    (r / "voice_studio").mkdir(parents=True)
    (r / "pyproject.toml").write_text("", encoding="utf-8")
    shutil.move(str(live), str(r / "workspaces"))
    (r / ".env").write_text("HF_TOKEN=gia\n", encoding="utf-8")
    (r / "studio.local.json").write_text(json.dumps(
        {"mode": "embedded", "station_path": "workspaces", "secrets": ".env"}), encoding="utf-8")
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(r))
    return r


def test_backup_zips_workspace_without_env_by_default(embedded_repo, tmp_path):
    z = tmp_path / "b.zip"
    station.backup(str(z))
    names = set(zipfile.ZipFile(z).namelist())
    assert "omnivoice/voices/demo.wav" in names and "station.json" in names
    assert not any(n.startswith(("omnivoice/.venv/", "cache/", "out/")) for n in names)
    assert not any(n.endswith(".prompt.pt") for n in names)
    assert ".env" not in names
    z2 = tmp_path / "b2.zip"
    station.backup(str(z2), with_env=True)
    assert ".env" in zipfile.ZipFile(z2).namelist()


def test_migrate_to_separate_moves_workspace_and_env(embedded_repo, tmp_path):
    target = tmp_path / "home" / "dich"
    res = station.migrate_to_separate(str(target))
    assert not (embedded_repo / "workspaces").exists()
    assert (target / "omnivoice" / "voices" / "demo.wav").is_file()
    assert not (embedded_repo / ".env").exists()
    moved_env = tmp_path / "home" / ".secret" / "voice-studio" / ".env"
    assert moved_env.read_text(encoding="utf-8") == "HF_TOKEN=gia\n"
    local = json.loads((embedded_repo / "studio.local.json").read_text(encoding="utf-8"))
    assert local["mode"] == "separate"
    assert os.path.normcase(local["station_path"]) == os.path.normcase(str(target))
    assert res["mode"] == "separate"
    assert os.path.normcase(_env.station_dir()) == os.path.normcase(str(target))


def test_migrate_checks_env_conflict_before_moving_anything(embedded_repo, tmp_path):
    existing = tmp_path / "home" / ".secret" / "voice-studio" / ".env"
    existing.parent.mkdir(parents=True)
    existing.write_text("CU=1\n", encoding="utf-8")
    with pytest.raises(station.ContractError, match="gộp tay"):
        station.migrate_to_separate(str(tmp_path / "home" / "dich"))
    assert (embedded_repo / "workspaces" / "station.json").is_file()
    assert (embedded_repo / ".env").is_file() and not (tmp_path / "home" / "dich").exists()


def test_migrate_refuses_non_empty_target(embedded_repo, tmp_path):
    target = tmp_path / "busy"
    target.mkdir()
    (target / "x").write_text("x", encoding="utf-8")
    with pytest.raises(station.ContractError):
        station.migrate_to_separate(str(target))
    assert (embedded_repo / "workspaces" / "station.json").is_file()


# ── migrate: hỏi rõ nơi dời; không bao giờ đoán một thư mục ẩn dưới home ──────────────────

def _tree_snapshot(*roots):
    out = {}
    for root in roots:
        for dp, dn, fn in os.walk(root):
            for n in dn:
                out[os.path.join(dp, n)] = None
            for n in fn:
                p = os.path.join(dp, n)
                out[p] = Path(p).read_bytes()
    return out


def _opcos_var(tmp_path, monkeypatch, value=None):
    ws = tmp_path / "opcos-ws"
    ws.mkdir(exist_ok=True)
    monkeypatch.setenv("OPCOS_WORKSPACES", value if value is not None else str(ws))
    return ws


def test_migrate_accepts_the_old_singular_workspace_as_source(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    (r / "voice_studio").mkdir(parents=True)
    (r / "pyproject.toml").write_text("", encoding="utf-8")
    old = r / "workspace"
    (old / "omnivoice" / "voices").mkdir(parents=True)
    (old / "station.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(r))
    dest = tmp_path / "ngoai"
    res = station.migrate_to_separate(str(dest))
    assert os.path.normcase(res["station"]) == os.path.normcase(str(dest))
    assert (dest / "station.json").is_file() and not old.exists()


def test_migrate_without_a_target_has_no_default(embedded_repo, tmp_path):
    with pytest.raises(station.ContractError, match="--station"):
        station.migrate_to_separate(None)
    assert (embedded_repo / "workspaces" / "station.json").is_file()
    assert not (tmp_path / "home" / "dich").exists()


@pytest.mark.parametrize("argv", [["migrate", "--to", "separate", "--non-interactive", "--json"],
                                  ["migrate", "--to", "separate", "--json"]])
def test_migrate_non_interactive_requires_station_code_2(argv, embedded_repo, tmp_path, capsys):
    before = _tree_snapshot(embedded_repo, tmp_path / "home")
    rc = cli.main(argv)
    out, err = capsys.readouterr()
    assert rc == 2 and last_json(out)["ok"] is False
    assert "--station" in err
    assert _tree_snapshot(embedded_repo, tmp_path / "home") == before


def test_migrate_cli_with_station_moves_without_asking(embedded_repo, tmp_path, capsys):
    dest = tmp_path / "chon" / "tram"
    rc = cli.main(["migrate", "--to", "separate", "--station", str(dest),
                   "--non-interactive", "--json"])
    out, _ = capsys.readouterr()
    assert rc == 0 and last_json(out)["station"] == str(dest)
    assert (dest / "omnivoice" / "voices" / "demo.wav").is_file()


def test_migrate_asks_where_and_confirms_with_counts(embedded_repo, tmp_path, monkeypatch):
    ws = _opcos_var(tmp_path, monkeypatch)
    files = [os.path.join(dp, n) for dp, _d, fn in os.walk(embedded_repo / "workspaces") for n in fn]
    files.append(str(embedded_repo / ".env"))                   # .env đi theo trạm
    n_files, size = len(files), sum(os.path.getsize(f) for f in files)
    prompts = []
    answers = iter(["", "y"])                                   # Enter = nơi gợi ý, rồi xác nhận
    res = station.do_migrate(ask=lambda p: prompts.append(p) or next(answers))
    want = os.path.abspath(str(ws / "voice"))
    assert os.path.normcase(res["station"]) == os.path.normcase(want)
    assert (ws / "voice" / "omnivoice" / "voices" / "demo.wav").is_file()
    assert not (embedded_repo / "workspaces").exists()
    ask_where, confirm = prompts
    assert want in ask_where                                    # gợi ý hiện đường tuyệt đối
    assert want in confirm and "y/N" in confirm
    assert f"{n_files} file" in confirm and f"{size} byte" in confirm


@pytest.mark.parametrize("answer", ["", "n", "no", "khong", "x"])
def test_migrate_declined_moves_nothing(answer, embedded_repo, tmp_path, monkeypatch):
    _opcos_var(tmp_path, monkeypatch)
    before = _tree_snapshot(embedded_repo, tmp_path / "opcos-ws", tmp_path / "home")
    answers = iter(["", answer])
    with pytest.raises(station.ContractError, match="huỷ"):
        station.do_migrate(ask=lambda p: next(answers))
    assert _tree_snapshot(embedded_repo, tmp_path / "opcos-ws", tmp_path / "home") == before


def test_migrate_without_opcos_var_has_no_suggestion_and_enter_cancels(embedded_repo, tmp_path):
    prompts = []
    with pytest.raises(station.ContractError, match="huỷ"):
        station.do_migrate(ask=lambda p: prompts.append(p) or "")
    assert len(prompts) == 1 and "Gợi ý" not in prompts[0]
    assert (embedded_repo / "workspaces" / "station.json").is_file()


def test_migrate_typed_path_is_made_absolute_and_confirmed(embedded_repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    answers = iter(["dich-tuong-doi", "Y"])
    res = station.do_migrate(ask=lambda p: next(answers))
    want = os.path.abspath(str(tmp_path / "dich-tuong-doi"))
    assert os.path.normcase(res["station"]) == os.path.normcase(want)
    assert (tmp_path / "dich-tuong-doi" / "station.json").is_file()


def test_migrate_relative_opcos_var_is_suggested_as_absolute(embedded_repo, tmp_path, monkeypatch):
    (tmp_path / "rel").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPCOS_WORKSPACES", "rel")
    prompts = []
    answers = iter(["", "y"])
    res = station.do_migrate(ask=lambda p: prompts.append(p) or next(answers))
    want = os.path.abspath(str(tmp_path / "rel" / "voice"))
    assert os.path.isabs(res["station"]) and os.path.normcase(res["station"]) == os.path.normcase(want)
    assert want in prompts[0]
    local = json.loads((embedded_repo / "studio.local.json").read_text(encoding="utf-8"))
    assert os.path.isabs(local["station_path"])


def test_migrate_rejects_busy_target_before_confirming(embedded_repo, tmp_path, monkeypatch):
    ws = _opcos_var(tmp_path, monkeypatch)
    (ws / "voice").mkdir()
    (ws / "voice" / "x").write_text("x", encoding="utf-8")
    prompts = []
    with pytest.raises(station.ContractError, match="không rỗng"):
        station.do_migrate(ask=lambda p: prompts.append(p) or "")
    assert len(prompts) == 1                                    # chưa tới câu xác nhận
    assert (embedded_repo / "workspaces" / "station.json").is_file()


@pytest.mark.parametrize("sub", ["sub/x", "sub", ""])
def test_migrate_target_inside_the_source_is_refused_cleanly(sub, embedded_repo):
    ws = embedded_repo / "workspaces"
    target = ws / sub if sub else ws
    before = _tree_snapshot(embedded_repo)
    with pytest.raises(station.ContractError, match="nằm trong"):
        station.migrate_to_separate(str(target))
    assert _tree_snapshot(embedded_repo) == before                # không để lại thư mục rỗng nào


def test_migrate_typed_target_inside_the_source_is_refused_before_confirming(embedded_repo):
    prompts = []
    inside = embedded_repo / "workspaces" / "sub" / "x"
    with pytest.raises(station.ContractError, match="nằm trong"):
        station.do_migrate(ask=lambda p: prompts.append(p) or str(inside))
    assert len(prompts) == 1 and not (embedded_repo / "workspaces" / "sub").exists()


def test_migrate_typed_path_with_quotes_is_unwrapped(embedded_repo, tmp_path):
    dest = tmp_path / "dan-vao"
    answers = iter([f'"{dest}"', "y"])
    res = station.do_migrate(ask=lambda p: next(answers))
    assert os.path.normcase(res["station"]) == os.path.normcase(str(dest))
    assert (dest / "station.json").is_file()


def test_migrate_station_flag_with_quotes_is_unwrapped(embedded_repo, tmp_path, capsys):
    dest = tmp_path / "co-ngoac"
    rc = cli.main(["migrate", "--to", "separate", "--station", f'"{dest}"', "--json"])
    out, _ = capsys.readouterr()
    assert rc == 0 and os.path.normcase(last_json(out)["station"]) == os.path.normcase(str(dest))


@pytest.mark.parametrize("n, text", [(0, "0 byte"), (1023, "1023 byte"), (1536, "1.5 KB"),
                                     (5 * 1024 * 1024, "5.0 MB"), (3 * 1024 ** 3, "3.0 GB")])
def test_migrate_sizes_are_human_readable(n, text):
    assert station._human_size(n) == text


def test_migrate_confirm_shows_human_size(embedded_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(station, "_tree_stats", lambda ws, env_file: (7, 2 * 1024 * 1024))
    prompts = []
    answers = iter([str(tmp_path / "d"), "n"])
    with pytest.raises(station.ContractError):
        station.do_migrate(ask=lambda p: prompts.append(p) or next(answers))
    assert "7 file" in prompts[1] and "2.0 MB" in prompts[1] and "byte" not in prompts[1]


def test_migrate_does_not_walk_the_tree_when_station_is_given(embedded_repo, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("không cần đếm file khi đã có --station")
    monkeypatch.setattr(station, "_tree_stats", boom)
    res = station.migrate_to_separate(str(tmp_path / "d"))
    assert (tmp_path / "d" / "station.json").is_file() and res["mode"] == "separate"


def test_migrate_failure_leaves_the_users_empty_target_directory_in_place(embedded_repo, tmp_path, monkeypatch):
    """Đích là thư mục RỖNG có sẵn của người dùng; dời hỏng ("chưa đụng gì") thì nó phải còn nguyên."""
    dest = tmp_path / "dich-rong"
    dest.mkdir()

    def fail(src, dst):
        raise station.ContractError("không dời được (giả)")
    monkeypatch.setattr(station, "_move_tree", fail)
    with pytest.raises(station.ContractError, match="giả"):
        station.migrate_to_separate(str(dest))
    assert dest.is_dir() and not os.listdir(dest)
    assert (embedded_repo / "workspaces" / "station.json").is_file()


def test_migrate_station_pointing_at_a_file_is_code_2(embedded_repo, tmp_path, capsys):
    f = tmp_path / "la-mot-file"
    f.write_text("x", encoding="utf-8")
    rc = cli.main(["migrate", "--to", "separate", "--station", str(f), "--json"])
    out, err = capsys.readouterr()
    assert rc == 2 and last_json(out)["ok"] is False and "thư mục" in err
    assert "Traceback" not in err and f.read_text(encoding="utf-8") == "x"
    assert (embedded_repo / "workspaces" / "station.json").is_file()


def test_migrate_typed_file_answer_is_a_contract_error(embedded_repo, tmp_path):
    f = tmp_path / "la-mot-file"
    f.write_text("x", encoding="utf-8")
    prompts = []
    with pytest.raises(station.ContractError, match="thư mục"):
        station.do_migrate(ask=lambda p: prompts.append(p) or str(f))
    assert len(prompts) == 1                                     # chưa tới câu xác nhận


@pytest.mark.parametrize("exc", [OSError("đĩa đầy (giả)"), shutil.Error("chép hỏng (giả)"),
                                 station.ContractError("không dời được (giả)")])
def test_migrate_any_move_failure_restores_the_empty_target_and_reraises(exc, embedded_repo, tmp_path,
                                                                         monkeypatch):
    dest = tmp_path / "dich-rong"
    dest.mkdir()

    def fail(src, dst):
        raise exc
    monkeypatch.setattr(station, "_move_tree", fail)
    with pytest.raises(type(exc)) as got:
        station.migrate_to_separate(str(dest))
    assert got.value is exc                                      # lỗi gốc không bị nuốt
    assert dest.is_dir() and not os.listdir(dest)


def test_migrate_eof_is_a_contract_error(embedded_repo, tmp_path, monkeypatch):
    _opcos_var(tmp_path, monkeypatch)

    def eof(_p):
        raise EOFError
    with pytest.raises(station.ContractError, match="--station"):
        station.do_migrate(ask=eof)
    assert (embedded_repo / "workspaces" / "station.json").is_file()


# ── update = git pull --ff-only, không bao giờ xoá ────────────────────────────────────────

@pytest.mark.skipif(not HAS_GIT, reason="cần git")
def test_update_fast_forwards_and_keeps_workspace(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", str(origin), str(seed))
    (seed / "a.txt").write_text("1", encoding="utf-8")
    git(seed, "add", "a.txt")
    git(seed, "commit", "-m", "1")
    git(seed, "push", "origin", "HEAD:main")
    user = tmp_path / "user"
    git(tmp_path, "clone", str(origin), str(user))
    (user / "workspace").mkdir()
    (user / "workspace" / "mine.txt").write_text("của tôi", encoding="utf-8")
    (seed / "a.txt").write_text("2", encoding="utf-8")
    git(seed, "commit", "-am", "2")
    git(seed, "push", "origin", "HEAD:main")
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(user))
    res = station.update()
    assert os.path.normcase(res["repo"]) == os.path.normcase(str(user))
    assert (user / "a.txt").read_text(encoding="utf-8") == "2"
    assert (user / "workspace" / "mine.txt").read_text(encoding="utf-8") == "của tôi"
    # Mã đang chạy KHÔNG nằm trong bản clone vừa pull ⇒ như bản sao của máy chạy lịch: pull chưa
    # đổi gì trong venv, phải in lệnh cài lại (docs/INSTALL.md mục 3).
    assert res["reinstall"] and f"{user}[engine]" in res["reinstall"]


def test_installed_copy_tells_editable_from_copy(tmp_path):
    pkg_repo = Path(station.__file__).resolve().parent.parent
    assert station.installed_copy(str(pkg_repo)) is False      # chạy từ chính bản clone (-e)
    assert station.installed_copy(str(tmp_path)) is True       # bản clone ở chỗ khác


def test_update_without_repo_is_2(monkeypatch):
    monkeypatch.setattr(_env, "repo_root", lambda: None)
    with pytest.raises(station.ContractError):
        station.update()


# ── doctor phần F17 ───────────────────────────────────────────────────────────────────

def by_name(checks):
    return {c["name"]: c for c in checks}


def test_doctor_red_on_two_sources(embedded_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "ngoai"))
    c = by_name(doctor.run_checks())
    assert c["two-sources"]["level"] == "error"


def test_doctor_no_two_sources_when_only_workspace(embedded_repo):
    c = by_name(doctor.run_checks())
    assert "two-sources" not in c or c["two-sources"]["ok"]
    assert c["station-json"]["ok"]


def test_doctor_warns_missing_station_json(tmp_path, monkeypatch):
    st = tmp_path / "st"
    (st / "omnivoice" / "voices").mkdir(parents=True)
    monkeypatch.setenv("VOICE_STATION", str(st))
    c = by_name(doctor.run_checks())
    assert c["station-json"]["level"] == "warn" and "init" in c["station-json"]["hint"]


def test_doctor_red_on_broken_station_json(tmp_path, monkeypatch):
    st = tmp_path / "st"
    st.mkdir()
    (st / "station.json").write_text("{hỏng", encoding="utf-8")
    monkeypatch.setenv("VOICE_STATION", str(st))
    assert by_name(doctor.run_checks())["station-json"]["level"] == "error"


@pytest.mark.skipif(not HAS_GIT, reason="cần git")
def test_doctor_red_when_workspace_is_tracked(embedded_repo):
    git(embedded_repo, "init")
    git(embedded_repo, "add", "-f", "workspaces/station.json")
    c = by_name(doctor.run_checks())
    assert c["git-tracked"]["level"] == "error"


def test_doctor_warns_cloud_synced_repo(tmp_path, monkeypatch):
    r = tmp_path / "OneDrive - X" / "repo"
    (r / "workspaces").mkdir(parents=True)
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(r))
    assert by_name(doctor.run_checks())["cloud-sync"]["level"] == "warn"


# ── hook pre-commit ───────────────────────────────────────────────────────────────────

@pytest.fixture
def gitrepo(tmp_path):
    if not HAS_GIT:
        pytest.skip("cần git")
    r = tmp_path / "g"
    r.mkdir()
    git(r, "init")
    return r


def stage(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    git(repo, "add", "-f", rel)


@pytest.mark.parametrize("rel,text,blocked", [
    ("workspaces/omnivoice/voices/a.txt", "x", True),
    ("workspace/omnivoice/voices/a.txt", "x", True),          # tên cũ (số ít) vẫn bị chặn
    (".env", "A=1", True),
    ("studio.local.json", "{}", True),
    (".env.example", "HF_TOKEN=", False),
    ("docs/a.md", "không có gì", False),
    ("cfg.py", "key = 'hf_" + "A" * 30 + "'", True),
    ("cfg2.py", "T = 'ghp_" + "b" * 36 + "'", True),
])
def test_precommit_blocks(gitrepo, rel, text, blocked):
    stage(gitrepo, rel, text)
    problems = precommit.check(str(gitrepo))
    assert bool(problems) is blocked, problems


# ── uninstall: gỡ phần mềm, giữ dữ liệu ───────────────────────────────────────────────

def tree_hash(root):
    out = {}
    for dp, _dn, fn in os.walk(root):
        for n in fn:
            full = os.path.join(dp, n)
            out[os.path.relpath(full, root)] = station._sha256(full)
    return out


@pytest.fixture
def pip_calls(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "Successfully uninstalled", "")
    monkeypatch.setattr(station.subprocess, "run", fake_run)
    return calls


def put_hook(repo, text):
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").write_text(text, encoding="utf-8")
    return hooks / "pre-commit"


def test_uninstall_dry_run_touches_nothing(embedded_repo, pip_calls, capsys):
    hook = put_hook(embedded_repo, station._hook_text())
    rc = cli.main(["uninstall", "--dry-run", "--json"])
    res = last_json(capsys.readouterr().out)
    assert rc == 0 and res["dry_run"] is True and res["removed"] == []
    assert hook.is_file() and pip_calls == []
    assert os.path.samefile(res["remove_hook"], hook)


def test_uninstall_yes_removes_hook_and_package_keeps_station(embedded_repo, pip_calls, capsys):
    import sys
    hook = put_hook(embedded_repo, station._hook_text())
    before = tree_hash(embedded_repo / "workspaces")
    rc = cli.main(["uninstall", "--yes", "--json"])
    res = last_json(capsys.readouterr().out)
    assert rc == 0 and not hook.exists()
    assert pip_calls == [[sys.executable, "-m", "pip", "uninstall", "-y", "agent-voice-studio"]]
    assert tree_hash(embedded_repo / "workspaces") == before          # giọng không suy suyển
    assert (embedded_repo / ".env").is_file() and (embedded_repo / "studio.local.json").is_file()
    assert any("workspace" in k for k in res["kept"])
    assert any("claude plugin uninstall" in c for c in res["host_commands"])


def test_uninstall_keeps_a_foreign_hook(embedded_repo, pip_calls, capsys):
    hook = put_hook(embedded_repo, "#!/bin/sh\nexec lint-staged\n")
    rc = cli.main(["uninstall", "--yes", "--keep-package", "--json"])
    res = last_json(capsys.readouterr().out)
    assert rc == 0 and hook.is_file() and res["remove_hook"] is None
    assert pip_calls == []                                            # --keep-package


def test_uninstall_without_yes_and_nobody_to_ask_is_2(embedded_repo, pip_calls, capsys):
    hook = put_hook(embedded_repo, station._hook_text())
    rc = cli.main(["uninstall", "--json"])
    out, err = capsys.readouterr()
    assert rc == 2 and last_json(out)["code"] == 2
    assert hook.is_file() and pip_calls == [] and "--yes" in err


def test_uninstall_pip_failure_is_1_and_names_the_command(embedded_repo, monkeypatch, capsys):
    monkeypatch.setattr(station.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "denied"))
    rc = cli.main(["uninstall", "--yes", "--json"])
    res = last_json(capsys.readouterr().out)
    assert rc == 1 and "pip uninstall" in res["error"]
    assert (embedded_repo / "workspaces" / "station.json").is_file()


# ── doctor: bốn trạng thái ─────────────────────────────────────────────────────────────

def test_doctor_reports_not_checked_honestly(monkeypatch, capsys):
    import sys
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "omnivoice", None)
    rc = cli.main(["doctor", "--json"])
    out, err = capsys.readouterr()
    res = last_json(out)
    assert rc == 3
    assert {"voices", "weights", "synthesis"} <= set(res["not_checked"])
    nc = by_name(res["checks"])
    assert nc["weights"]["ok"] is None and nc["weights"]["level"] == "not_checked"
    assert "voices" not in res["errors"]                    # chưa kiểm ≠ hỏng
    assert "[NOT_CHECKED]" in err and "[FAIL]" in err


def test_doctor_json_keeps_old_level_names(tmp_path, monkeypatch, capsys):
    st = tmp_path / "st"
    (st / "omnivoice" / "voices").mkdir(parents=True)
    monkeypatch.setenv("VOICE_STATION", str(st))
    res = doctor.run_checks()
    levels = {c["level"] for c in res}
    assert levels <= {"ok", "warn", "error", "not_checked"}
    assert by_name(res)["station"]["ok"] is True and by_name(res)["synthesis"]["level"] == "not_checked"


@pytest.mark.parametrize("venv,level", [
    ("C:\\st\\omnivoice\\.venv", "ok"),
    ("C:\\Users\\someone\\AppData\\Local\\Temp\\vs-t22\\agent-voice-studio\\workspace\\omnivoice\\.venv",
     "warn"),
])
def test_doctor_warns_long_engine_venv_path_on_windows(venv, level):
    c = doctor.win_path_check(venv, windows=True)
    assert c["name"] == "win-path" and c["level"] == level
    if level == "warn":
        assert "WinError 206" in c["hint"]


def test_win_path_check_is_silent_elsewhere():
    assert doctor.win_path_check("/" + "x" * 300, windows=False) is None


# ── doctor: trạm OpcOS + bỏ tầng home ─────────────────────────────────────────

@pytest.fixture
def bare_repo(tmp_path, monkeypatch, sandbox_home):
    r = tmp_path / "bare-repo"
    (r / "voice_studio").mkdir(parents=True)
    (r / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(r))
    return r


def opcos_ws(tmp_path, monkeypatch, marked=True):
    ws = tmp_path / "opcos-ws"
    (ws / "voice").mkdir(parents=True)
    if marked:
        (ws / "voice" / "station.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
    return ws


def test_doctor_hints_init_when_opcos_station_unused(bare_repo, tmp_path, monkeypatch):
    ws = opcos_ws(tmp_path, monkeypatch)
    c = by_name(doctor.run_checks())["opcos-station"]
    assert c["level"] == "warn" and not c["ok"]
    assert "init --mode separate --station" in c["hint"] and str(ws / "voice") in c["hint"]


@pytest.mark.parametrize("marked", [True, False])
def test_doctor_silent_when_embedded_was_chosen_on_purpose(marked, bare_repo, tmp_path, monkeypatch):
    """Đã ghi lựa chọn embedded vào studio.local.json thì có `<biến>/voice` cũng không nhắc mỗi lần."""
    opcos_ws(tmp_path, monkeypatch, marked=marked)
    (bare_repo / "studio.local.json").write_text(
        json.dumps({"mode": "embedded", "station_path": "workspaces"}), encoding="utf-8")
    assert "opcos-station" not in by_name(doctor.run_checks())


def test_doctor_still_hints_when_nothing_was_chosen(bare_repo, tmp_path, monkeypatch):
    opcos_ws(tmp_path, monkeypatch)
    (bare_repo / "studio.local.json").write_text(json.dumps({"mode": "separate"}), encoding="utf-8")
    assert "opcos-station" in by_name(doctor.run_checks())


OLD_DATA = "Có dữ liệu cũ ở nơi khác? Dùng `--station <đường>`"


def test_old_data_sentence_is_in_doctor(bare_repo):
    c = doctor.run_checks()
    assert any(OLD_DATA in (x["detail"] + x["hint"]) for x in c)
    assert "." + "voice" not in json.dumps(c, ensure_ascii=False)       # không nêu tên thư mục ẩn nào


def test_old_data_sentence_is_in_the_code_3_messages(tmp_path, monkeypatch, capsys):
    # trạm chưa xác định (bản cài không có repo)
    rc = cli.main(["export", "--personal", "--out", str(tmp_path / "x.zip"), "--json"])
    out = capsys.readouterr().out
    assert rc == 3 and OLD_DATA in last_json(out)["error"]
    # trạm đã trỏ nhưng thư mục chưa có
    with pytest.raises(station.StationMissing, match="Có dữ liệu cũ"):
        station.export_personal(str(tmp_path / "chua-co"), str(tmp_path / "y.zip"))
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "chua-co"))
    with pytest.raises(station.StationMissing, match="Có dữ liệu cũ"):
        station.backup(str(tmp_path / "z.zip"))


def test_doctor_silent_without_opcos_var(bare_repo):
    assert "opcos-station" not in by_name(doctor.run_checks())


def test_doctor_silent_when_station_env_set(bare_repo, tmp_path, monkeypatch):
    opcos_ws(tmp_path, monkeypatch)
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "chon"))
    assert "opcos-station" not in by_name(doctor.run_checks())


def test_doctor_silent_when_local_config_chose(bare_repo, tmp_path, monkeypatch):
    opcos_ws(tmp_path, monkeypatch)
    (bare_repo / "studio.local.json").write_text(
        json.dumps({"mode": "separate", "station_path": str(tmp_path / "chon")}), encoding="utf-8")
    assert "opcos-station" not in by_name(doctor.run_checks())


def test_doctor_notes_opcos_dir_without_marker(bare_repo, tmp_path, monkeypatch):
    ws = opcos_ws(tmp_path, monkeypatch, marked=False)
    c = by_name(doctor.run_checks())["opcos-station"]
    assert c["level"] == "warn" and str(ws) in c["detail"] + c["hint"]
    assert "chưa là trạm" in c["detail"] + c["hint"]


def test_doctor_has_no_station_source_warning(bare_repo, sandbox_home):
    names = by_name(doctor.run_checks())
    assert "station-source" not in names
    assert "legacy-workspace" not in names


def _singular_station(repo):
    d = repo / "workspace"
    (d / "omnivoice" / "voices").mkdir(parents=True)
    (d / "station.json").write_text("{}", encoding="utf-8")
    return d


def test_doctor_warns_when_the_station_still_uses_the_singular_name(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    (r / "voice_studio").mkdir(parents=True)
    (r / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(r))
    _singular_station(r)
    c = by_name(doctor.run_checks())["legacy-workspace"]
    assert c["level"] == "warn" and "workspaces" in c["hint"]


def test_doctor_warns_when_both_layouts_exist(embedded_repo):
    _singular_station(embedded_repo)
    c = by_name(doctor.run_checks())["legacy-workspace"]
    assert c["level"] == "warn" and "workspaces" in c["hint"]


def test_doctor_tracked_check_covers_the_singular_name(embedded_repo):
    git(embedded_repo, "init")
    (embedded_repo / "workspace").mkdir()
    (embedded_repo / "workspace" / "station.json").write_text("{}", encoding="utf-8")
    git(embedded_repo, "add", "-f", "workspace/station.json")
    assert by_name(doctor.run_checks())["git-tracked"]["level"] == "error"


# ── init: trạm nhúng cũ có dữ liệu, chưa ghi lựa chọn, máy có OPCOS_WORKSPACES ────────────────

@pytest.fixture
def old_data_repo(tmp_path, monkeypatch, live):
    """Repo có trạm nhúng `workspaces/` ĐÃ mang dấu + `.env`, CHƯA có studio.local.json; máy đặt OPCOS_WORKSPACES."""
    r = tmp_path / "repo"
    (r / "voice_studio").mkdir(parents=True)
    (r / "pyproject.toml").write_text("", encoding="utf-8")
    shutil.move(str(live), str(r / "workspaces"))
    (r / ".env").write_text("HF_TOKEN=gia\n", encoding="utf-8")
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(r))
    ws = tmp_path / "opcos-ws"
    ws.mkdir()
    monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
    monkeypatch.chdir(tmp_path)               # một lỗi (đường gõ tương đối) không được ghi vào cây repo đang test
    return r


def _scripted(*items):
    """Hàm hỏi giả: ghi lại câu hỏi; phần tử là ngoại lệ thì ném, hết câu trả lời thì nổ."""
    it = iter(items)
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        try:
            val = next(it)
        except StopIteration:
            raise AssertionError("hỏi nhiều hơn dự kiến: " + prompt)
        if isinstance(val, type) and issubclass(val, BaseException):
            raise val
        return val
    ask.prompts = prompts
    return ask


def _hashes(root):
    import hashlib
    out = {}
    for dp, _d, fn in os.walk(root):
        for n in fn:
            p = os.path.join(dp, n)
            out[os.path.relpath(p, root).replace(os.sep, "/")] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return out


def _kept(before, after):
    """Mọi file có sẵn còn nguyên nội dung (`init` được thêm file mẫu thiếu, không được đổi/xoá file có sẵn;
    `station.json` được cập nhật nên bỏ qua)."""
    return all(after.get(k) == v for k, v in before.items() if k != "station.json")


def _local(repo):
    return json.loads((repo / "studio.local.json").read_text(encoding="utf-8"))


def test_init_old_station_chuyen_then_yes_moves_it_with_two_questions(old_data_repo, tmp_path):
    """`chuyen` then `y` ⇒ embedded is written, then the move goes through the `migrate` path; 2 questions; hashes match."""
    before = _hashes(old_data_repo / "workspaces")
    ask = _scripted("chuyen", "y")
    res = station.do_init(ask=ask)
    oc = tmp_path / "opcos-ws" / "voice"
    assert len(ask.prompts) == 2 and "y/N" in ask.prompts[1] and str(oc) in ask.prompts[1]
    assert res["mode"] == "separate" and os.path.normcase(res["station"]) == os.path.normcase(str(oc))
    assert not (old_data_repo / "workspaces").exists()
    after = _hashes(oc)
    for rel, digest in before.items():
        if rel != "station.json":                      # station.json đổi `mode` (so như JSON ở dưới)
            assert after[rel] == digest, rel
    assert json.loads((oc / "station.json").read_text(encoding="utf-8"))["mode"] == "separate"
    assert _local(old_data_repo)["mode"] == "separate"
    assert os.path.normcase(_local(old_data_repo)["station_path"]) == os.path.normcase(str(oc))
    assert (tmp_path / "home" / ".secret" / "voice-studio" / ".env").read_text(encoding="utf-8") == "HF_TOKEN=gia\n"


@pytest.mark.parametrize("answer", ["n", "", "khong", EOFError])
def test_init_old_station_chuyen_then_decline_keeps_it_with_exit_0(answer, old_data_repo, tmp_path, capsys):
    """`n`/Enter/EOF ở y/N ⇒ giữ (đã ghi embedded), 0 byte dời, không lỗi, một dòng chỉ lệnh `migrate`."""
    before = _hashes(old_data_repo / "workspaces")
    ask = _scripted("chuyen", answer)
    res = station.do_init(ask=ask)
    assert len(ask.prompts) == 2
    assert res["mode"] == "embedded"
    assert _local(old_data_repo)["mode"] == "embedded"
    after = _hashes(old_data_repo / "workspaces")
    assert _kept(before, after)
    assert not (tmp_path / "opcos-ws" / "voice").exists()
    assert (old_data_repo / ".env").is_file()
    assert "migrate --to separate" in capsys.readouterr().err


def test_init_old_station_chuyen_into_a_non_empty_target_is_code_2_before_the_y_n_question(old_data_repo, tmp_path):
    """Target không rỗng ⇒ mã 2 TRƯỚC câu y/N; trạm cũ đã ghi embedded vẫn dùng được."""
    oc = tmp_path / "opcos-ws" / "voice"
    oc.mkdir()
    (oc / "co-san.txt").write_text("x", encoding="utf-8")
    before = _hashes(old_data_repo / "workspaces")
    ask = _scripted("chuyen")
    with pytest.raises(station.ContractError, match="không rỗng"):
        station.do_init(ask=ask)
    assert len(ask.prompts) == 1                           # KHÔNG có câu y/N
    assert _local(old_data_repo)["mode"] == "embedded"
    after = _hashes(old_data_repo / "workspaces")
    assert _kept(before, after)
    assert sorted(os.listdir(oc)) == ["co-san.txt"]


def test_init_old_station_dry_run_with_chuyen_prints_the_plan_and_writes_nothing(old_data_repo, tmp_path, capsys):
    """`--dry-run` + chuyển ⇒ in "sẽ dời", 0 byte dời, không ghi studio.local.json."""
    snap = _hashes(old_data_repo)
    ask = _scripted("chuyen")
    res = station.do_init(ask=ask, dry_run=True)
    station._print_init(res)
    err = capsys.readouterr().err
    assert len(ask.prompts) == 1
    assert "sẽ dời" in err and str(tmp_path / "opcos-ws" / "voice") in err
    assert not (old_data_repo / "studio.local.json").exists()
    assert not (tmp_path / "opcos-ws" / "voice").exists()
    assert _hashes(old_data_repo) == snap


def test_init_old_station_ctrl_c_at_the_y_n_question_propagates_and_moves_nothing(old_data_repo, tmp_path):
    """Ctrl+C ở y/N ⇒ lan ra (contract.run đổi thành mã 2); embedded đã ghi, 0 byte dời."""
    before = _hashes(old_data_repo / "workspaces")
    with pytest.raises(KeyboardInterrupt):
        station.do_init(ask=_scripted("chuyen", KeyboardInterrupt))
    assert _local(old_data_repo)["mode"] == "embedded"
    assert _kept(before, _hashes(old_data_repo / "workspaces"))
    assert not (tmp_path / "opcos-ws" / "voice").exists()


def test_init_old_station_yes_keeps_it_and_the_second_run_is_silent_and_never_asks(old_data_repo, capsys):
    """`--yes` giữ trạm cũ (ghi embedded); init lần hai: 0 câu, không dòng `migrate`."""
    res = station.do_init(yes=True)
    err = capsys.readouterr().err
    assert res["mode"] == "embedded" and _local(old_data_repo)["mode"] == "embedded"
    assert "migrate --to separate" in err
    assert not (old_data_repo.parent / "opcos-ws" / "voice").exists()
    res2 = station.do_init(ask=_scripted())
    assert res2["mode"] == "embedded"
    assert "migrate --to separate" not in capsys.readouterr().err


def test_init_old_station_dry_run_with_yes_prints_the_keep_plan_and_writes_nothing(old_data_repo, capsys):
    """`--dry-run --yes` trên trạm nhúng cũ có dữ liệu ⇒ kế hoạch 'giữ', 0 byte, không ghi studio.local.json."""
    snap = _hashes(old_data_repo)
    res = station.do_init(yes=True, dry_run=True, ask=_scripted())
    station._print_init(res)
    assert res["mode"] == "embedded" and res["dry_run"] is True
    assert not (old_data_repo / "studio.local.json").exists()
    assert _hashes(old_data_repo) == snap
    assert "migrate --to separate" in capsys.readouterr().err


@pytest.mark.parametrize("how", ["yes", "chuyen-then-y"])
def test_init_old_station_with_opcos_workspaces_pointing_at_a_file_is_code_2(how, old_data_repo, tmp_path, monkeypatch):
    """The old station is kept data-wise, but a broken variable is still the caller's error: exit code 2 naming it,
    before any question, nothing written (no hint to run a `migrate` that cannot work)."""
    f = tmp_path / "la-file"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(f))
    before = _hashes(old_data_repo)
    ask = _scripted("chuyen", "y")
    with pytest.raises(station.ContractError, match="OPCOS_WORKSPACES"):
        station.do_init(yes=True, ask=ask) if how == "yes" else station.do_init(ask=ask)
    assert ask.prompts == []                           # the error comes before any question
    assert not (old_data_repo / "studio.local.json").exists()
    assert _hashes(old_data_repo) == before


def test_init_old_station_with_opcos_workspaces_pointing_at_a_file_cli_is_code_2_without_traceback(
        old_data_repo, tmp_path, monkeypatch, capsys):
    f = tmp_path / "la-file"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(f))
    rc = cli.main(["init", "--yes", "--json"])
    out, err = capsys.readouterr()
    assert rc == 2 and "Traceback" not in err
    assert "OPCOS_WORKSPACES" in last_json(out)["error"]


# ── a junction into the source station must be refused by real path (before any question, nothing moved) ──────

def _junction(link, target):
    if os.name != "nt":
        pytest.skip("junctions are a Windows feature")
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("mklink /J is not available here: " + (r.stderr or r.stdout).strip())


def test_migrate_refuses_a_target_that_reaches_the_source_through_a_junction(embedded_repo, tmp_path):
    jn = tmp_path / "jn"
    _junction(jn, embedded_repo / "workspaces")
    before = _hashes(embedded_repo)
    with pytest.raises(station.ContractError, match="nằm trong"):
        station.migrate_to_separate(str(jn / "x"))
    assert _hashes(embedded_repo) == before
    assert not (embedded_repo / "workspaces" / "x").exists()


def test_init_move_into_a_junction_that_reaches_the_source_is_code_2_before_the_y_n_question(
        old_data_repo, tmp_path, monkeypatch):
    sub = old_data_repo / "workspaces" / "sub"
    sub.mkdir()
    jn = tmp_path / "jn"
    _junction(jn, sub)
    monkeypatch.setenv("OPCOS_WORKSPACES", str(jn))
    before = _hashes(old_data_repo / "workspaces")
    ask = _scripted("chuyen")
    with pytest.raises(station.ContractError, match="nằm trong"):
        station.do_init(ask=ask)
    assert len(ask.prompts) == 1                                  # no y/N question
    assert _kept(before, _hashes(old_data_repo / "workspaces"))


# ── studio.local.json must not point at the target before the move has finished ─────────────────────────────

def test_a_failed_move_leaves_the_recorded_choice_untouched(embedded_repo, tmp_path, monkeypatch):
    def fail(src, dst):
        raise station.ContractError("không dời được (giả)")
    monkeypatch.setattr(station, "_move_tree", fail)
    local = embedded_repo / "studio.local.json"
    before = local.read_bytes()
    with pytest.raises(station.ContractError, match="giả"):
        station.migrate_to_separate(str(tmp_path / "dich"))
    assert local.read_bytes() == before and json.loads(before)["mode"] == "embedded"
    assert (embedded_repo / "workspaces" / "station.json").is_file()
