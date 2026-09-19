"""doctor.py — `voice-studio doctor`: kiểm trạm giọng đủ để chạy chưa, thiếu thì chỉ bước cài tiếp.

    voice-studio doctor            # bảng người đọc (stderr) + tóm tắt
    voice-studio doctor --json     # một dòng JSON cuối stdout cho bên gọi (marketing, trạm video)

Kiểm: python · trạm (`VOICE_STATION`, tên cũ `OMNIVOICE_DIR` bị nhắc đổi) · kho giọng + profile
mặc định · thư viện nhạc nền · ffmpeg · torch + thiết bị · engine `omnivoice` · weights đã có
trong cache (chạy offline được). Không tải gì, không nạp model.

Mã thoát: 0 dùng được (có thể kèm cảnh báo) · 3 thiếu thứ bắt buộc (trạm / kho giọng / torch /
engine) — kèm hướng dẫn cài phần còn thiếu.
"""
import argparse
import importlib
import os
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


def run_checks():
    checks = [_check("python", sys.version_info >= (3, 10), sys.version.split()[0],
                     hint="cần Python ≥ 3.10")]

    st = _env.station_dir()
    checks.append(_check("station", os.path.isdir(st), st,
                         hint="chưa có trạm giọng — chạy `voice-studio init` hoặc đặt VOICE_STATION"))
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
