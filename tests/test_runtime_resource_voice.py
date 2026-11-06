"""SPR-61 TK5 — voice khai nhu cầu runtime và tạo/tìm engine ở `runtime/`.

Hợp đồng: `runtime-resource-v1` + `runtime-layout-v2` (khối `addressing`, `keyRules`, `needs`, `vectors`).
Test thuần: không tạo venv, không cài gì, không gọi CLI `opcos-runtime` thật (cây giả có tệp vỏ rỗng),
không đọc `~/OpcOS` thật (conftest trỏ HOME vào cây giả và xoá OPCOS_RUNTIME / OPCOS_ROOT).
"""
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

import pytest

from voice_studio import _env, doctor, station
from voice_studio.clean import clean_voice

ROOT = Path(__file__).resolve().parent.parent
NEEDS_FILE = ROOT / "opcos-runtime.json"
REPO_KEY = "agent-voice-studio"

# ── Véc-tơ VT1–VT7 chép NGUYÊN VĂN từ khối `vectors` của hợp đồng
#    system/workshop/planning/contracts/runtime-resource-v1.json @ d5c62b76 (đường POSIX, home=/h).
VECTORS = [
    {"id": "VT1", "env": {"OPCOS_RUNTIME": "/r", "OPCOS_ROOT": "/o"}, "paths_json": True,
     "call": {"kind": "own", "category": "venvs", "repoKey": "agent-voice-studio", "resourceKey": "omnivoice"},
     "expect": {"path": "/r/venvs/agent-voice-studio/omnivoice"}},
    {"id": "VT2", "env": {"OPCOS_ROOT": "/o"}, "paths_json": False,
     "call": {"kind": "own", "category": "venvs", "repoKey": "agent-voice-studio", "resourceKey": "omnivoice"},
     "expect": {"path": "/o/runtime/venvs/agent-voice-studio/omnivoice"}},
    {"id": "VT3", "env": {}, "paths_json": True,
     "call": {"kind": "own", "category": "venvs", "repoKey": "agent-voice-studio", "resourceKey": "omnivoice"},
     "expect": {"path": "/h/OpcOS/runtime/venvs/agent-voice-studio/omnivoice"}},
    {"id": "VT4", "env": {}, "paths_json": False,
     "call": {"kind": "own", "category": "venvs", "repoKey": "agent-voice-studio", "resourceKey": "omnivoice"},
     "expect": {"path": None}},
    {"id": "VT5", "env": {"OPCOS_RUNTIME": "/r"}, "paths_json": None,
     "call": {"kind": "own", "category": "venvs", "repoKey": "agent-voice-studio", "resourceKey": "Bad_Key"},
     "expect": {"error": "RT_BAD_KEY"}},
    {"id": "VT6", "env": {"OPCOS_RUNTIME": "/r"}, "paths_json": None,
     "call": {"kind": "own", "category": "models", "repoKey": "agent-voice-studio", "resourceKey": "cv"},
     "expect": {"error": "RT_BAD_KEY"}},
    {"id": "VT7", "env": {"OPCOS_RUNTIME": "/r"}, "paths_json": None,
     "call": {"kind": "own", "category": "venvs", "repoKey": "agent-voice-studio", "resourceKey": "con"},
     "expect": {"error": "RT_BAD_KEY"}},
]


def _fake_isfile(has_paths_json):
    """`isfile` giả cho đúng `/h/OpcOS/paths.json`; đường khác ⇒ không có."""
    def isfile(p):
        return bool(has_paths_json) and Path(p).as_posix() == "/h/OpcOS/paths.json"
    return isfile


@pytest.mark.parametrize("vec", VECTORS, ids=lambda v: v["id"])
def test_vectors(vec):
    call, expect = vec["call"], vec["expect"]
    assert call["repoKey"] == REPO_KEY and call["kind"] == "own"
    kw = dict(env=vec["env"], home="/h", isfile=_fake_isfile(vec["paths_json"]))
    if "error" in expect:
        with pytest.raises(ValueError, match=expect["error"]):
            _env.runtime_resource(call["category"], call["resourceKey"], **kw)
        return
    got = _env.runtime_resource(call["category"], call["resourceKey"], **kw)
    if expect["path"] is None:
        assert got is None
    else:
        assert isinstance(got, Path)
        assert PurePosixPath(got.as_posix()) == PurePosixPath(expect["path"])


def test_shared_repo_key_is_reserved():
    """VT9: `shared` không được làm tên plugin — kiểm ở bộ phân giải chung (voice luôn dùng repoKey riêng)."""
    with pytest.raises(ValueError, match="RT_BAD_KEY"):
        _env._resource_path("venvs", "shared", "x", env={"OPCOS_RUNTIME": "/r"}, home="/h",
                            isfile=_fake_isfile(False))


def test_slug_length_and_blank_env():
    long_key = "a" * 65
    with pytest.raises(ValueError, match="RT_BAD_KEY"):
        _env.runtime_resource("venvs", long_key, env={"OPCOS_RUNTIME": "/r"}, home="/h")
    assert _env.runtime_resource("venvs", "a" * 64, env={"OPCOS_RUNTIME": "/r"}, home="/h") is not None
    # biến rỗng/khoảng trắng coi như chưa đặt
    assert _env.runtime_root(env={"OPCOS_RUNTIME": "  ", "OPCOS_ROOT": ""}, home="/h",
                             isfile=_fake_isfile(False)) is None


# ── tệp nhu cầu ─────────────────────────────────────────────────────────────────────────

CATEGORIES = ("mcp", "engines", "tools", "venvs", "scripts", "bin", "maintenance", "state", "logs",
              "cache", "backups", "_archive")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _validate_needs(doc):
    """Kiểm tay theo `needs.jsonSchema` của hợp đồng (không thêm phụ thuộc jsonschema)."""
    assert set(doc) <= {"schema", "repoKey", "needs"}
    assert {"schema", "repoKey", "needs"} <= set(doc)
    assert doc["schema"] == "opcos-runtime-needs/1"
    assert SLUG.match(doc["repoKey"])
    assert isinstance(doc["needs"], list)
    for n in doc["needs"]:
        assert {"scope", "category"} <= set(n)
        assert set(n) <= {"scope", "category", "key", "engine", "version", "repo", "python", "install", "paths"}
        assert n["scope"] in ("own", "shared", "use") and n["category"] in CATEGORIES
        if n["scope"] == "own":
            assert SLUG.match(n["key"])
        inst = n.get("install", {})
        assert set(inst) <= {"package", "torch", "requirements", "constraints", "kind"}
        assert isinstance(inst.get("torch", False), bool)
        assert all(isinstance(x, str) for x in inst.get("requirements", []))
        assert inst.get("kind", "venv") in ("venv", "files")
        cons = inst.get("constraints", {})
        assert set(cons) <= {"windows", "darwin", "linux"}
        assert all(isinstance(x, str) for lst in cons.values() for x in lst)
        paths = n.get("paths", {})
        assert set(paths) <= {"dir_rel", "file_rel"}
        assert all(isinstance(v, int) for v in paths.values())


def _need(doc, category, key):
    return next(n for n in doc["needs"] if n["category"] == category and n["key"] == key)


def test_needs_file_schema():
    doc = json.loads(NEEDS_FILE.read_text(encoding="utf-8"))
    _validate_needs(doc)
    assert doc["repoKey"] == REPO_KEY
    assert len(doc["needs"]) == 4
    budget = {"omnivoice": (109, 150), "sep": (186, 197), "cv": (186, 197)}
    for key, (d, f) in budget.items():
        n = _need(doc, "venvs", key)
        assert n["scope"] == "own"
        assert n["paths"] == {"dir_rel": d, "file_rel": f}
        assert n["install"]["torch"] is True            # RF22: cả ba venv có torch
        lock = n["install"]["constraints"]["windows"]
        assert lock == [f"locks/{key}-windows.txt"]
        assert (ROOT / lock[0]).is_file()
    omni = _need(doc, "venvs", "omnivoice")
    assert omni["install"]["package"] == ".[engine]" and omni["python"] == "3.12"
    assert _need(doc, "venvs", "sep")["install"]["requirements"] == ["voice_studio/clean/requirements-sep.txt"]
    assert _need(doc, "venvs", "cv")["install"]["requirements"] == ["voice_studio/clean/requirements-cv.txt"]
    clean = _need(doc, "engines", "clean")
    assert clean["install"] == {"kind": "files"}
    # mọi tệp yêu cầu/khoá khai ra phải có thật trong repo
    for n in doc["needs"]:
        for rel in n.get("install", {}).get("requirements", []):
            assert (ROOT / rel).is_file(), rel


def _lines(rel):
    return [ln.strip() for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def test_requirements_and_lock_contents():
    assert _lines("voice_studio/clean/requirements-sep.txt") == ["audio-separator[cpu]", "soundfile", "librosa==0.11.0"]
    assert _lines("voice_studio/clean/requirements-cv.txt") == ["clearvoice", "soundfile", "numpy<2"]
    for key in ("omnivoice", "sep", "cv"):
        lines = _lines(f"locks/{key}-windows.txt")
        assert lines and all(re.fullmatch(r"[A-Za-z0-9_.\-]+==[0-9][^\s=]*", ln) for ln in lines), key
        assert lines == sorted(lines, key=str.lower)
        names = [ln.split("==")[0].lower() for ln in lines]
        assert not any(n.startswith("agent_") or n == "pip" for n in names)
        assert any(ln.startswith("torch==") and ln.endswith("+cu126") for ln in lines)
    omni = {ln.split("==")[0].lower() for ln in _lines("locks/omnivoice-windows.txt")}
    assert omni.isdisjoint({"yt_dlp", "google_api_python_client", "openpyxl", "lxml", "beautifulsoup4"})
    assert "omnivoice" in omni and "transformers" in omni


def test_needs_path_budget_read_by_doctor():
    assert _env.venv_path_budget("omnivoice", repo=str(ROOT)) == (109, 150)
    assert _env.venv_path_budget("sep", repo=str(ROOT)) == (186, 197)
    assert _env.venv_path_budget("cv", repo=str(ROOT)) == (186, 197)
    assert _env.venv_path_budget("không-có", repo=str(ROOT)) == (186, 197)   # không khai ⇒ ngân sách venv torch không ghim
    assert _env.venv_path_budget("sep") == (186, 197)                         # không có repo/tệp ⇒ ngân sách mặc định


# ── cây runtime giả ─────────────────────────────────────────────────────────────────────

def _py_rel(windows):
    return ("Scripts", "python.exe") if windows else ("bin", "python")


@pytest.fixture
def stn(tmp_path, monkeypatch):
    """Trạm tạm tối giản (không cần soundfile): <st>/omnivoice/voices/ rỗng; VOICE_STATION trỏ vào."""
    st = tmp_path / "station"
    (st / "omnivoice" / "voices").mkdir(parents=True)
    monkeypatch.setenv("VOICE_STATION", str(st))
    return st


@pytest.fixture
def opcos(tmp_path, monkeypatch):
    """Cây OpcOS giả: <base>/runtime (R) + <base>/system/operations/runtime/ (chưa có vỏ CLI)."""
    base = tmp_path / "OpcOS"
    (base / "runtime").mkdir(parents=True)
    monkeypatch.setenv("OPCOS_RUNTIME", str(base / "runtime"))
    return base


def _add_cli(base):
    d = base / "system" / "operations" / "runtime"
    d.mkdir(parents=True, exist_ok=True)
    for n in ("opcos-runtime.ps1", "opcos-runtime.sh"):
        (d / n).write_text("", encoding="utf-8")        # vỏ rỗng — test KHÔNG gọi CLI thật
    return d


def _rt_venv(base, key="omnivoice", create=True):
    p = base / "runtime" / "venvs" / REPO_KEY / key
    if create:
        p.mkdir(parents=True)
    return p


def test_engine_venv_order(stn, opcos):
    st = stn
    default = Path(os.path.join(str(st), "omnivoice", ".venv"))
    # 3) không có gì ở runtime ⇒ <engine>/.venv
    assert _env.engine_venv(str(st)) == default
    assert _env.engine_venv() == default
    # 2) venv runtime tồn tại ⇒ nó
    rt = _rt_venv(opcos)
    assert _env.engine_venv(str(st)) == rt and _env.engine_venv() == rt
    # 1) station.json: venv tuyệt đối và tồn tại ⇒ thắng cả runtime
    mine = st.parent / "my-venv"
    mine.mkdir()
    (st / "station.json").write_text(json.dumps({"venv": str(mine)}), encoding="utf-8")
    assert _env.engine_venv(str(st)) == mine and _env.engine_venv() == mine
    # tuyệt đối nhưng không tồn tại ⇒ rơi xuống nấc sau; tương đối ⇒ không tính (như cũ)
    (st / "station.json").write_text(json.dumps({"venv": str(st.parent / "gone")}), encoding="utf-8")
    assert _env.engine_venv(str(st)) == rt
    (st / "station.json").write_text(json.dumps({"venv": "omnivoice/.venv"}), encoding="utf-8")
    assert _env.engine_venv(str(st)) == rt


def test_opcos_runtime_cli(opcos):
    assert _env.opcos_runtime_cli(windows=True) is None          # chưa có tệp vỏ ⇒ None, không lỗi
    d = _add_cli(opcos)
    ps = _env.opcos_runtime_cli(windows=True)
    assert ps == ["powershell", "-NoProfile", "-File", str(d / "opcos-runtime.ps1")]
    sh = _env.opcos_runtime_cli(windows=False)
    assert sh == ["bash", str(d / "opcos-runtime.sh")]


def test_opcos_runtime_cli_without_runtime_root():
    assert _env.opcos_runtime_cli(windows=False) is None


# ── lệnh `init` in ra ───────────────────────────────────────────────────────────────────

def _is_editable(cmds):
    return any(re.search(r"\s-e\s", c) for c in cmds)


@pytest.mark.parametrize("windows", [True, False])
def test_venv_commands_with_cli(windows, opcos, tmp_path):
    d = _add_cli(opcos)
    st = str(tmp_path / "st")
    cmds = station.venv_commands(st, windows=windows)
    script = str(d / ("opcos-runtime.ps1" if windows else "opcos-runtime.sh"))
    first = cmds[0]
    assert script in first and " ensure --repo-dir " in first
    assert "--only venvs/omnivoice" in first and "--torch-index auto" in first
    assert (first.startswith("powershell -NoProfile -File ") if windows else first.startswith("bash "))
    assert "python -m venv" not in "\n".join(cmds)
    assert not _is_editable(cmds)
    py = os.path.join(str(opcos / "runtime" / "venvs" / REPO_KEY / "omnivoice"),
                      *_py_rel(windows))
    assert any(py in c and "voice_studio doctor" in c for c in cmds)
    assert str(tmp_path / "st" / "omnivoice") not in "\n".join(cmds)   # không trỏ venv vào trạm


def test_venv_commands_without_cli(opcos, tmp_path):
    st = str(tmp_path / "st")
    cmds = station.venv_commands(st, windows=False)
    venv = str(opcos / "runtime" / "venvs" / REPO_KEY / "omnivoice")
    joined = "\n".join(cmds)
    assert cmds[0] == f"python -m venv \"{venv}\""
    assert "pip install torch" in joined and "download.pytorch.org" in joined
    repo = _env.repo_root()
    assert f"pip install \"{repo}[engine]\"" in joined
    assert not _is_editable(cmds) and "opcos-runtime" not in joined


def test_venv_commands_no_opcos(tmp_path):
    st = str(tmp_path / "st")
    cmds = station.venv_commands(st, windows=False)
    venv = os.path.join(st, "omnivoice", ".venv")
    py = os.path.join(venv, "bin", "python")
    run = f"\"{py}\""
    repo = _env.repo_root()
    torch = ("pip install torch --index-url https://download.pytorch.org/whl/cu126   # NVIDIA; "
             "không có GPU: bỏ --index-url" if sys.platform != "darwin"
             else "pip install torch   # Apple Silicon: dùng MPS")
    out_wav = os.path.join(st, "out", "thu.wav")
    first = (f"{run} -m voice_studio speak --text \"Xin chào\" --instruct \"female, young adult\" "
             f"--out \"{out_wav}\" --json")
    assert cmds == [
        f"python -m venv \"{venv}\"",
        f"{run} -m {torch}",
        f"{run} -m pip install -e \"{repo}[engine]\"   # omnivoice==0.2.1 + lệnh voice-studio; "
        "xưởng Windows chạy lịch có trạm riêng: bỏ -e (docs/INSTALL.md mục 3)",
        f"{run} -m voice_studio doctor   # kiểm engine (không tải gì)",
        f"OMNIVOICE_ONLINE=1 {first}   # lần tổng hợp đầu: tải weights (~3,3 GB)",
    ]


# ── nhận diện venv đang chạy ────────────────────────────────────────────────────────────

def test_host_venv_runtime(opcos, tmp_path):
    st = tmp_path / "st"
    repo = tmp_path / "repo"
    repo.mkdir()
    base = str(Path(sys.base_prefix).resolve())

    def hv(prefix, engine_ok=True):
        return station.host_venv(str(st), str(repo), prefix=str(prefix), base_prefix=base, engine_ok=engine_ok)

    # đang chạy từ venv dưới runtime/venvs/agent-voice-studio/ ⇒ chính là venv engine (FR6.3)
    assert hv(opcos / "runtime" / "venvs" / REPO_KEY / "omnivoice") is None
    assert hv(opcos / "runtime" / "venvs" / REPO_KEY / "omnivoice", engine_ok=False) is None
    # venv của repo video (chế độ cài chung) giữ hành vi cũ
    video = tmp_path / "agent-video-studio"
    video.mkdir()
    (video / "pyproject.toml").write_text("", encoding="utf-8")
    got = hv(video / ".venv")
    assert got is not None and got["project"] == str(video) and got["engine"] is True
    # venv runtime của repo KHÁC không bị coi là venv engine giọng
    other = opcos / "runtime" / "venvs" / "agent-video-studio" / "video-use"
    other.parent.mkdir(parents=True)
    (other.parent / "pyproject.toml").write_text("", encoding="utf-8")
    assert hv(other) is not None


# ── station.json ────────────────────────────────────────────────────────────────────────

def test_init_new_station_absolute_venv(opcos, tmp_path):
    st = tmp_path / "st"
    st.mkdir()
    expect = str(opcos / "runtime" / "venvs" / REPO_KEY / "omnivoice")
    path, data, changed, venv_exists = station._station_json(str(st), "separate", False)
    assert data["venv"] == expect and os.path.isabs(data["venv"])
    assert changed and venv_exists is False
    # trạm cũ đã có venv trong trạm ⇒ giữ dạng tương đối như trước
    (st / "omnivoice" / ".venv").mkdir(parents=True)
    path, data, changed, venv_exists = station._station_json(str(st), "separate", False)
    assert data["venv"] == "omnivoice/.venv" and venv_exists is True


def test_init_new_station_without_opcos_keeps_relative_venv(tmp_path):
    st = tmp_path / "st"
    st.mkdir()
    path, data, changed, venv_exists = station._station_json(str(st), "separate", False)
    assert data["venv"] == "omnivoice/.venv" and venv_exists is False


@pytest.mark.parametrize("value", ["omnivoice/.venv", "D:/mot-noi-khac/venv"])
def test_init_keeps_existing_venv_value(opcos, tmp_path, value):
    st = tmp_path / "st"
    st.mkdir()
    (st / "station.json").write_text(json.dumps({"mode": "separate", "venv": value}), encoding="utf-8")
    path, data, changed, venv_exists = station._station_json(str(st), "separate", False)
    assert data["venv"] == value                                  # FR6.2: không đè giá trị người dùng/bản cũ


def test_init_prints_runtime_commands(opcos, tmp_path, capsys, monkeypatch):
    """`init` in lệnh theo runtime (CLI giả có mặt) và trạm mới ghi venv tuyệt đối vào station.json."""
    _add_cli(opcos)
    monkeypatch.setattr(station, "host_venv", lambda *a, **k: None)
    st = tmp_path / "st"
    rc = station.init_main(["--mode", "separate", "--station", str(st), "--yes"])
    err = capsys.readouterr().err
    assert rc == 0
    info = json.loads((st / "station.json").read_text(encoding="utf-8"))
    assert info["venv"] == str(opcos / "runtime" / "venvs" / REPO_KEY / "omnivoice")
    assert " ensure --repo-dir " in err and "--only venvs/omnivoice" in err
    assert not (st / "omnivoice" / ".venv").exists()


# ── doctor ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n,expect_ok", [(139, True), (140, False)])
def test_win_path_check_directory_limit(n, expect_ok):
    venv = "C:\\" + "x" * (n - 3)
    assert len(venv) == n
    c = doctor.win_path_check(venv, windows=True, dir_rel=109, file_rel=0)
    assert c["ok"] is expect_ok and c["level"] == ("ok" if expect_ok else "warn")


@pytest.mark.parametrize("n,expect_ok", [(110, True), (111, False)])
def test_win_path_check_file_limit(n, expect_ok):
    venv = "C:\\" + "x" * (n - 3)
    c = doctor.win_path_check(venv, windows=True, dir_rel=10, file_rel=150)
    assert c["ok"] is expect_ok


def test_doctor_path_check_uses_real_venv(stn, opcos, monkeypatch):
    """`run_checks` đo đường venv THẬT đang dùng (engine_venv), không phải `<engine>/.venv` cứng."""
    rt = _rt_venv(opcos)
    seen = []
    real = doctor.win_path_check
    monkeypatch.setattr(doctor, "win_path_check", lambda venv, *a, **k: (seen.append(venv), real(venv, *a, **k))[1])
    doctor.run_checks()
    assert [Path(p) for p in seen] == [rt]
    # đổi sang venv khai trong station.json ⇒ đo venv đó
    mine = stn.parent / "my-venv"
    mine.mkdir()
    (stn / "station.json").write_text(json.dumps({"venv": str(mine)}), encoding="utf-8")
    seen.clear()
    doctor.run_checks()
    assert [Path(p) for p in seen] == [mine]


def _runtime_check(checks):
    return next((c for c in checks if c["name"] == "runtime"), None)


def test_doctor_no_opcos_is_a_warning_not_an_error(stn):
    c = _runtime_check(doctor.run_checks())
    assert c is not None and c["level"] == "warn" and "RT_NO_OPCOS" in c["detail"]


def test_doctor_orphan_venv_warns(stn, opcos):
    rt = _rt_venv(opcos)
    c = _runtime_check(doctor.run_checks())
    assert c["level"] == "warn" and "RT_ORPHAN" in c["detail"]
    (rt / ".opcos-resource.json").write_text("{}", encoding="utf-8")
    c = _runtime_check(doctor.run_checks())
    assert c["level"] == "ok" and "RT_ORPHAN" not in c["detail"]


def test_doctor_runtime_without_venv_is_ok(stn, opcos):
    c = _runtime_check(doctor.run_checks())
    assert c["level"] == "ok" and "RT_NO_OPCOS" not in c["detail"]


# ── clean_voice: tìm venv và mô hình ────────────────────────────────────────────────────

def _make_venv(path, windows=None):
    rel = _py_rel((os.name == "nt") if windows is None else windows)
    py = path.joinpath(*rel)
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("", encoding="utf-8")
    return py


def _same(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_clean_voice_lookup_order(opcos, tmp_path, monkeypatch):
    station_dir = tmp_path / "st"
    clean_dir = station_dir / "voice-clean"
    old_sep = _make_venv(clean_dir / ".venv-sep")
    old_cv = _make_venv(clean_dir / ".venv-cv")
    monkeypatch.setenv("VOICE_STATION", str(station_dir))
    cd = clean_voice.resolve_clean_dir()
    assert _same(cd, clean_dir)
    # chưa có venv ở runtime ⇒ đường cũ trong thư mục công cụ
    assert _same(clean_voice.resolve_venv_python("sep", None, cd), old_sep)
    assert _same(clean_voice.resolve_venv_python("cv", None, cd), old_cv)
    rt_sep = _make_venv(opcos / "runtime" / "venvs" / REPO_KEY / "sep")
    rt_cv = _make_venv(opcos / "runtime" / "venvs" / REPO_KEY / "cv")
    # có ở runtime ⇒ runtime thắng; VOICE_STATION KHÔNG đè được
    assert _same(clean_voice.resolve_venv_python("sep", None, cd), rt_sep)
    assert _same(clean_voice.resolve_venv_python("cv", None, cd), rt_cv)
    # --clean-dir tường minh đè
    assert _same(clean_voice.resolve_venv_python("sep", str(clean_dir), cd), old_sep)
    # VOICE_CLEAN_DIR đè
    vc = tmp_path / "vc"
    vc_sep = _make_venv(vc / ".venv-sep")
    monkeypatch.setenv("VOICE_CLEAN_DIR", str(vc))
    cd2 = clean_voice.resolve_clean_dir()
    assert _same(cd2, vc)
    assert _same(clean_voice.resolve_venv_python("sep", None, cd2), vc_sep)
    # khoá lạ ⇒ ValueError
    with pytest.raises(ValueError):
        clean_voice.resolve_venv_python("musicgen", None, cd)


def test_clean_voice_without_opcos_keeps_old_lookup(tmp_path, monkeypatch):
    clean_dir = tmp_path / "st" / "voice-clean"
    old = _make_venv(clean_dir / ".venv-sep")
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    assert _same(clean_voice.resolve_venv_python("sep", None, clean_dir), old)
    assert clean_voice.venv_python(clean_dir, ".venv-sep") == old


def test_clean_models_lookup_order(opcos, tmp_path, monkeypatch):
    clean_dir = tmp_path / "st" / "voice-clean"
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    # không có gì ở runtime ⇒ models/ và checkpoints/ trong thư mục công cụ (như cũ)
    assert clean_voice.resolve_models_base(clean_dir) == clean_dir
    rt = opcos / "runtime" / "engines" / REPO_KEY / "clean"
    rt.mkdir(parents=True)
    # có ở runtime ⇒ runtime; VOICE_STATION KHÔNG đè
    assert _same(clean_voice.resolve_models_base(clean_dir), rt)
    # VOICE_CLEAN_MODELS đè
    mine = tmp_path / "models-here"
    monkeypatch.setenv("VOICE_CLEAN_MODELS", str(mine))
    assert _same(clean_voice.resolve_models_base(clean_dir), mine)
    # tầng 1 và tầng 2 dùng hai thư mục con của gốc mô hình
    assert clean_voice.models_dirs(mine)[0].name == "models"
    assert clean_voice.models_dirs(mine)[1].name == "checkpoints"


def test_clean_resolvers_agree_with_package_resolver(opcos):
    """Hai bộ phân giải (package và clean_voice tự chứa) phải cho cùng một đích."""
    assert clean_voice._runtime_resource("venvs", "sep") == _env.runtime_resource("venvs", "sep")
    assert clean_voice._runtime_resource("engines", "clean") == _env.runtime_resource("engines", "clean")


def test_clean_resolver_none_without_opcos():
    assert clean_voice._runtime_resource("venvs", "sep") is None


# ── ngân sách đường dài: có / không có tệp khai sinh (review vòng 1) ───────────────────────

def _venv_len(p):
    return len(os.path.abspath(p)) if os.name == "nt" else len(str(p))


def test_win_path_budget_without_manifest_is_186_197(tmp_path):
    """Venv KHÔNG có `.opcos-resource.json` (torch cài không ghim, >= 2.13) ⇒ 186/197, không phải 109/150."""
    venv = tmp_path / "venv"
    venv.mkdir()
    n = _venv_len(venv)
    assert _env.engine_path_budget(venv, repo=str(ROOT)) == (186, 197)
    c = doctor.win_path_check(str(venv), windows=True)
    assert f"thư mục sâu nhất {n + 186}/248" in c["detail"] and f"tệp dài nhất {n + 197}/260" in c["detail"]


def test_win_path_budget_with_manifest_uses_declared_numbers(tmp_path, monkeypatch):
    """Có tệp khai sinh (cài theo khoá, torch 2.12) ⇒ `dir_rel`/`file_rel` khai trong opcos-runtime.json (109/150)."""
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(ROOT))
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / ".opcos-resource.json").write_text("{}", encoding="utf-8")
    n = _venv_len(venv)
    assert _env.engine_path_budget(venv) == (109, 150)
    c = doctor.win_path_check(str(venv), windows=True)
    assert f"thư mục sâu nhất {n + 109}/248" in c["detail"] and f"tệp dài nhất {n + 150}/260" in c["detail"]


def test_win_path_budget_differs_at_the_boundary(tmp_path, monkeypatch):
    """Gốc 64..110 ký tự: không tệp khai sinh ⇒ WARN (186 + n > 248); có tệp khai sinh ⇒ PASS (109/150 vừa)."""
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(ROOT))
    n = _venv_len(tmp_path / "v")
    if n > 110:
        pytest.skip("tmp_path quá dài cho ca biên")
    venv = tmp_path / ("p" * max(0, 64 - n) + "v")
    venv.mkdir()
    assert 64 <= _venv_len(venv) <= 110
    assert doctor.win_path_check(str(venv), windows=True)["level"] == "warn"
    (venv / ".opcos-resource.json").write_text("{}", encoding="utf-8")
    assert doctor.win_path_check(str(venv), windows=True)["level"] == "ok"


# ── clean_voice: tiến trình cha chạy lại trong venv `sep` ──────────────────────────────────

def test_clean_reexec_passes_chosen_values_and_exit_code(opcos, tmp_path, monkeypatch):
    station_dir = tmp_path / "st"
    clean_dir = station_dir / "voice-clean"
    monkeypatch.setenv("VOICE_STATION", str(station_dir))
    rt_sep = _make_venv(opcos / "runtime" / "venvs" / REPO_KEY / "sep")
    rt_cv = _make_venv(opcos / "runtime" / "venvs" / REPO_KEY / "cv")
    models = opcos / "runtime" / "engines" / REPO_KEY / "clean"
    models.mkdir(parents=True)
    calls = []

    class Done:
        returncode = 7

    monkeypatch.setattr(clean_voice, "_need_reexec", lambda args: True)
    monkeypatch.setattr(clean_voice.subprocess, "run", lambda argv, *a, **k: (calls.append(argv), Done())[1])
    rc = clean_voice.main(["in.mp3", "--no-enhance"])
    assert rc == 7                                              # mã thoát của tiến trình con chuyển nguyên
    assert len(calls) == 1
    argv = calls[0]
    assert _same(argv[0], rt_sep) and _same(argv[1], clean_voice.__file__)
    rest = argv[2:]
    assert rest[:2] == ["in.mp3", "--no-enhance"]
    assert _same(rest[rest.index("--clean-dir") + 1], clean_dir)
    assert _same(rest[rest.index("--cv-python") + 1], rt_cv)
    assert _same(rest[rest.index("--models-dir") + 1], models)
    # người dùng đã truyền --clean-dir ⇒ không thêm lần nữa, và venv tầng 1 theo đường tường minh
    old_sep = _make_venv(clean_dir / ".venv-sep")
    calls.clear()
    rc = clean_voice.main(["in.mp3", "--clean-dir", str(clean_dir)])
    argv = calls[0]
    assert argv.count("--clean-dir") == 1 and _same(argv[0], old_sep)
