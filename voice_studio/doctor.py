"""doctor.py — `voice-studio doctor`: kiểm trạm giọng đủ để chạy chưa, thiếu thì chỉ bước cài tiếp.

    voice-studio doctor            # bảng người đọc (stderr) + tóm tắt
    voice-studio doctor --json     # một dòng JSON cuối stdout cho bên gọi (marketing, trạm video)

Kiểm: python · trạm (`VOICE_STATION`, tên cũ `OMNIVOICE_DIR` bị nhắc đổi) · `station.json` ·
hai chế độ cài (F17: ĐỎ khi vừa có <repo>/workspace/ vừa có trạm ngoài; embedded: workspace/.env
không bị git theo dõi, repo không nằm trong thư mục đồng bộ đám mây, quyền .env) · kho giọng + profile
mặc định · thư viện nhạc nền · ffmpeg · torch + thiết bị · engine `omnivoice` · weights đã có
trong cache (chạy offline được). Không tải gì, không nạp model.

Mã thoát: 0 dùng được (có thể kèm cảnh báo) · 3 thiếu thứ bắt buộc (trạm / kho giọng / torch /
engine) — kèm hướng dẫn cài phần còn thiếu.
"""
import argparse
import importlib
import os
import subprocess
import sys

from . import API_VERSION, _env, contract, engine

INSTALL_HINT = (
    "Cài trạm giọng: tạo venv → cài torch theo hệ điều hành → `pip install omnivoice==0.2.1` → "
    "`pip install -e <repo agent-voice-studio>` → `voice-studio init` → "
    "`OMNIVOICE_ONLINE=1 voice-studio doctor` (lần đầu tải weights). Chi tiết: "
    "skills/voice-routing/references/install-omnivoice.md")


def _check(name, ok, detail="", level="error", hint=""):
    return {"name": name, "ok": bool(ok), "level": "ok" if ok else level,
            "detail": detail, "hint": "" if ok else hint}


def _hf_cache_has(model_id):
    """Weights đã nằm trong cache Hugging Face chưa (chỉ nhìn thư mục, không tải)."""
    home = os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface"),
        "hub")
    return os.path.isdir(os.path.join(home, "models--" + model_id.replace("/", "--"))), home


CLOUD_MARKERS = ("onedrive", "google drive", "googledrive", "my drive", "icloud", "dropbox",
                 "mobile documents", "cloudstorage")


def _major(v):
    try:
        return int(str(v).split(".")[0])
    except (TypeError, ValueError):
        return None


def station_checks(st):
    """station.json + phần F17 (hai nguồn, rào của chế độ embedded)."""
    out = []
    sj = os.path.join(st, _env.STATION_FILE)
    if os.path.isdir(st):
        info, err = _env.read_json(sj)
        if err:
            out.append(_check("station-json", False, err,
                              hint="sửa hoặc xoá rồi `voice-studio init --existing`"))
        elif not os.path.isfile(sj):
            out.append(_check("station-json", False, sj, level="warn",
                              hint="trạm chưa có station.json — `voice-studio init --existing`"))
        elif _major(info.get("contract")) != _major(API_VERSION):
            out.append(_check("station-json", False, f"contract {info.get('contract')} ≠ {API_VERSION}",
                              level="warn", hint="trạm dựng bởi bản hợp đồng khác — kiểm lại rồi chạy init"))
        else:
            out.append(_check("station-json", True, f"{sj} (contract {info.get('contract')})"))

    repo = _env.repo_root()
    if not repo or not os.path.isdir(repo):
        return out
    ws = os.path.join(repo, _env.WORKSPACE)
    _, src = _env.resolve_station()
    local = _env.local_config(repo)
    if os.path.isdir(ws):
        others = []
        if _env.env("VOICE_STATION"):
            others.append("VOICE_STATION")
        if _env.env("OMNIVOICE_DIR"):
            others.append("OMNIVOICE_DIR")
        if local.get("mode") == "separate":
            others.append("studio.local.json=separate")
        if _env.has_marker(_env.default_station()):
            others.append("~/.voice")
        out.append(_check("two-sources", not others,
                          f"{ws} + {', '.join(others)}" if others else ws,
                          hint="hai nguồn sự thật cho một repo: giữ MỘT trạm — gộp dữ liệu rồi xoá "
                               "workspace/ hoặc gỡ biến/trạm ngoài (`voice-studio migrate --to separate`)"))
    embedded = src == _env.WORKSPACE or local.get("mode") == "embedded"
    if not embedded:
        return out
    tracked = _git_tracked(repo)
    if tracked is not None:
        out.append(_check("git-tracked", not tracked, ", ".join(tracked) or "workspace/, .env sạch",
                          hint="dữ liệu trạm/secret đang bị git theo dõi — `git rm --cached` ngay, "
                               "kiểm .gitignore"))
    low = repo.lower()
    cloud = [m for m in CLOUD_MARKERS if m in low]
    out.append(_check("cloud-sync", not cloud, repo, level="warn",
                      hint="repo nằm trong thư mục đồng bộ đám mây — giọng và .env sẽ lên cloud; "
                           "dời repo ra ngoài"))
    env_file = os.path.join(repo, ".env")
    if os.name == "posix" and os.path.isfile(env_file):
        mode = os.stat(env_file).st_mode & 0o777
        out.append(_check("env-perm", not (mode & 0o077), oct(mode), level="warn",
                          hint="chmod 600 .env"))
    return out


def _git_tracked(repo):
    if not os.path.isdir(os.path.join(repo, ".git")):
        return None
    try:
        r = subprocess.run(["git", "-C", repo, "ls-files", "--", _env.WORKSPACE, ".env",
                            _env.LOCAL_CONFIG], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def run_checks():
    checks = [_check("python", sys.version_info >= (3, 10), sys.version.split()[0],
                     hint="cần Python ≥ 3.10")]

    st = _env.station_dir()
    checks.append(_check("station", os.path.isdir(st), st,
                         hint="chưa có trạm giọng — chạy `voice-studio init` hoặc đặt VOICE_STATION"))
    checks += station_checks(st)
    if _env.env("OMNIVOICE_DIR") and not _env.env("VOICE_STATION"):
        checks.append(_check("env-name", False, "OMNIVOICE_DIR", level="warn",
                             hint="tên biến cũ — đặt VOICE_STATION=<gốc trạm> (OMNIVOICE_DIR vẫn đọc được)"))
    old_bgm = [n for n in ("NEWS_BGM", "NEWS_BGM_VOL", "NEWS_BGM_DIR") if os.environ.get(n)]
    if old_bgm:
        checks.append(_check("env-name-bgm", False, ", ".join(old_bgm), level="warn",
                             hint="tên biến cũ — đổi sang VOICE_BGM, VOICE_BGM_VOL, VOICE_BGM_DIR"))

    from . import profiles
    vd = profiles.voices_dir()
    names = profiles.list_profiles() if os.path.isdir(vd) else []
    checks.append(_check("voices", os.path.isdir(vd), f"{vd} ({len(names)} profile)",
                         hint="chưa có kho giọng — `voice-studio init` rồi `voice-studio make-profile`"))
    default = profiles.get_default() if names else None
    checks.append(_check("default-profile", bool(default), default or "(không có)", level="warn",
                         hint="chưa có profile mặc định — ghi tên vào voices/_default.txt "
                              "hoặc đặt VOICE_DEFAULT_PROFILE; pipeline phải truyền --profile"))

    from . import bgm
    lib_file = os.path.join(_env.bgm_dir(), bgm.LIBRARY_FILE)
    checks.append(_check("bgm-library", os.path.isfile(lib_file), lib_file, level="warn",
                         hint="chưa có thư viện nhạc nền — `voice-studio init` dựng khung rỗng"))

    try:
        ff = _env.ffmpeg_exe()
        checks.append(_check("ffmpeg", True, ff))
    except RuntimeError as e:
        checks.append(_check("ffmpeg", False, "", level="warn",
                             hint=f"{e} (cần cho mp3 và ghép video)"))

    try:
        importlib.import_module("torch")
        try:
            dev = engine.pick_device()
            checks.append(_check("torch", True, f"thiết bị {dev}"))
        except Exception as e:      # noqa: BLE001 — ép thiết bị không có trên máy
            checks.append(_check("torch", False, str(e), hint="sửa OMNIVOICE_DEVICE"))
    except ImportError as e:
        checks.append(_check("torch", False, str(e), hint="cài torch vào venv engine"))
    try:
        importlib.import_module("omnivoice")
        checks.append(_check("omnivoice", True, "importable"))
    except ImportError as e:
        checks.append(_check("omnivoice", False, str(e), hint="`pip install omnivoice==0.2.1`"))

    cached, hub = _hf_cache_has(engine.MODEL_ID)
    checks.append(_check("weights", cached, f"{engine.MODEL_ID} @ {hub}", level="warn",
                         hint="weights chưa có trong cache — chạy một lần với OMNIVOICE_ONLINE=1"))
    return checks


def doctor(args):
    checks = run_checks()
    for c in checks:
        mark = {"ok": "OK  ", "warn": "WARN", "error": "LỖI "}[c["level"]]
        line = f"[{mark}] {c['name']:<16} {c['detail']}"
        if c["hint"]:
            line += f"\n         → {c['hint']}"
        contract.log(line)
    errors = [c["name"] for c in checks if c["level"] == "error"]
    warns = [c["name"] for c in checks if c["level"] == "warn"]
    result = {"voice_studio": API_VERSION, "station": _env.station_dir(),
              "checks": checks, "errors": errors, "warnings": warns}
    if errors:
        contract.log("\n" + INSTALL_HINT)
        raise _DoctorFailed(result)
    return result


class _DoctorFailed(contract.StationMissing):
    def __init__(self, result):
        super().__init__("trạm giọng chưa đủ: " + ", ".join(result["errors"]))
        self.result = result


def build_parser(prog="voice-studio doctor"):
    ap = argparse.ArgumentParser(prog=prog, description="Kiểm trạm giọng và engine.")
    ap.add_argument("--json", action="store_true")
    return ap


def main(argv=None):
    args, code = contract.parse(build_parser(), argv)
    if args is None:
        return code
    try:
        result = doctor(args)
    except _DoctorFailed as e:
        if args.json:
            contract.emit({"ok": False, "code": contract.STATION_MISSING, "error": str(e), **e.result})
        return contract.STATION_MISSING
    if args.json:
        contract.emit({"ok": True, **result})
    return contract.OK


if __name__ == "__main__":
    sys.exit(main())
