"""Vận hành trạm: `export --personal` / `import` (chuyển máy), `backup`, `migrate --to separate`,
`update` (git pull --ff-only), `doctor` phần F17, và hook pre-commit của chế độ embedded.

Không có mạng: `update` chạy trên một "origin" là repo git trần trong thư mục tạm.
"""
import json
import os
import shutil
import subprocess
import zipfile

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
    shutil.move(str(live), str(r / "workspace"))
    (r / ".env").write_text("HF_TOKEN=gia\n", encoding="utf-8")
    (r / "studio.local.json").write_text(json.dumps(
        {"mode": "embedded", "station_path": "workspace", "secrets": ".env"}), encoding="utf-8")
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
    target = tmp_path / "home" / ".voice"
    res = station.migrate_to_separate(str(target))
    assert not (embedded_repo / "workspace").exists()
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
        station.migrate_to_separate(str(tmp_path / "home" / ".voice"))
    assert (embedded_repo / "workspace" / "station.json").is_file()
    assert (embedded_repo / ".env").is_file() and not (tmp_path / "home" / ".voice").exists()


def test_migrate_refuses_non_empty_target(embedded_repo, tmp_path):
    target = tmp_path / "busy"
    target.mkdir()
    (target / "x").write_text("x", encoding="utf-8")
    with pytest.raises(station.ContractError):
        station.migrate_to_separate(str(target))
    assert (embedded_repo / "workspace" / "station.json").is_file()


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
    git(embedded_repo, "add", "-f", "workspace/station.json")
    c = by_name(doctor.run_checks())
    assert c["git-tracked"]["level"] == "error"


def test_doctor_warns_cloud_synced_repo(tmp_path, monkeypatch):
    r = tmp_path / "OneDrive - X" / "repo"
    (r / "workspace").mkdir(parents=True)
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
    ("workspace/omnivoice/voices/a.txt", "x", True),
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
