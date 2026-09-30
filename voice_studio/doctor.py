"""doctor.py — `voice-studio doctor`: kiểm trạm giọng đủ để chạy chưa, thiếu thì chỉ bước cài tiếp.

    voice-studio doctor            # bảng người đọc (stderr) + tóm tắt
    voice-studio doctor --json     # một dòng JSON cuối stdout cho bên gọi (marketing, trạm video)

Kiểm: python · trạm (`VOICE_STATION`, tên cũ `OMNIVOICE_DIR` bị nhắc đổi) · `station.json` ·
hai chế độ cài (F17: ĐỎ khi vừa có <repo>/workspace/ vừa có trạm ngoài; embedded: workspace/.env
không bị git theo dõi, repo không nằm trong thư mục đồng bộ đám mây, quyền .env) · kho giọng + profile
mặc định · thư viện nhạc nền (json + `<style>.mp3` của từng style khai) · ffmpeg · torch + thiết bị · engine `omnivoice` · weights đã có
trong cache (chạy offline được). Không tải gì, không nạp model.

Bốn trạng thái mỗi dòng: `PASS` đã kiểm, đạt · `WARN` dùng được nhưng nên sửa · `FAIL` thiếu thứ
bắt buộc · `NOT_CHECKED` doctor KHÔNG kiểm được điều này (chưa có trạm, chưa có engine, hoặc cần
nạp model) — không phải lỗi, và không bao giờ được báo như đã đạt. JSON giữ tên mức cũ
(`ok`/`warn`/`error`) cho bên gọi hiện có, thêm `not_checked` (khi đó `"ok": null`).

Mã thoát: 0 dùng được (có thể kèm cảnh báo) · 3 thiếu thứ bắt buộc (trạm / kho giọng / torch /
engine) — kèm hướng dẫn cài phần còn thiếu.
"""
import argparse
import importlib
import importlib.metadata
import itertools
import os
import subprocess
import sys

from . import API_VERSION, __version__, _env, contract, engine

INSTALL_HINT = (
    "Cài trạm giọng: tạo venv → cài torch theo hệ điều hành → "
    "`pip install -e \"<repo agent-voice-studio>[engine]\"` (xưởng Windows chạy lịch có trạm riêng: bỏ `-e`, xem "
    "docs/INSTALL.md mục 3) → `voice-studio init` → lần tổng hợp đầu chạy "
    "với OMNIVOICE_ONLINE=1 để tải weights (doctor không tải gì). Chi tiết: "
    "skills/voice-routing/references/install-omnivoice.md")

# Khoảng transformers đã chạy thật với engine — PHẢI trùng phần phụ `engine` trong pyproject.toml
# (tests/test_repo_gates.py giữ hai chỗ khớp). Ngoài khoảng: doctor WARN, không chặn.
TRANSFORMERS_TESTED = ">=5.10.2,<5.18"


NOT_CHECKED = "not_checked"
MARKS = {"ok": "PASS", "warn": "WARN", "error": "FAIL", NOT_CHECKED: "NOT_CHECKED"}


def _check(name, ok, detail="", level="error", hint=""):
    return {"name": name, "ok": bool(ok), "level": "ok" if ok else level,
            "detail": detail, "hint": "" if ok else hint}


def _not_checked(name, detail, hint=""):
    """Điều doctor không kiểm được lần này. `ok` là null: không đạt, cũng không hỏng."""
    return {"name": name, "ok": None, "level": NOT_CHECKED, "detail": detail, "hint": hint}


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


def _vtuple(v):
    """Phiên bản → tuple số: "5.17.0" → (5, 17, 0); bỏ đuôi kiểu ".dev0", "+cu126". Không dùng
    `packaging` để lõi không thêm phụ thuộc."""
    parts = []
    for p in str(v).split("+")[0].split("."):
        digits = "".join(itertools.takewhile(str.isdigit, p))
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def in_range(version, spec):
    """`version` thoả mọi điều kiện `>=` / `<` trong `spec` (vd ">=5.10.2,<5.18")?"""
    v = _vtuple(version)
    for cond in spec.split(","):
        cond = cond.strip()
        if cond.startswith(">="):
            if v < _vtuple(cond[2:]):
                return False
        elif cond.startswith("<"):
            if v >= _vtuple(cond[1:]):
                return False
        else:
            raise ValueError(f"điều kiện phiên bản không hỗ trợ: {cond!r}")
    return True


def transformers_check(version=None):
    """transformers có nằm trong khoảng đã đo không. Chỉ đọc metadata, không import."""
    if version is None:
        try:
            version = importlib.metadata.version("transformers")
        except importlib.metadata.PackageNotFoundError:
            return _not_checked("transformers", "không thấy metadata transformers trong venv này")
    return _check("transformers", in_range(version, TRANSFORMERS_TESTED),
                  f"{version} (khoảng đã đo {TRANSFORMERS_TESTED})", level="warn",
                  hint=f"ngoài khoảng đã chạy thật; cài lại phần phụ engine để về khoảng đó: "
                       f"pip install \"<repo>[engine]\" (thêm -e trên máy phát triển)")


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

    st, st_src = _env.resolve_station()
    if st is None:
        checks.append(_check("station", False, "(chưa xác định)", hint=_env.UNSET_HINT))
    else:
        checks.append(_check("station", os.path.isdir(st), f"{st} (nguồn: {st_src})",
                             hint="chưa có trạm giọng — chạy `voice-studio init` hoặc đặt VOICE_STATION"))
        checks += station_checks(st)
    if st_src == _env.HOME_STATION:
        checks.append(_check("station-source", False, st, level="warn",
                             hint="trạm ~/.voice được nhận vì nó đã có sẵn; đặt VOICE_STATION trỏ vào "
                                  "đó để lịch chạy và máy khác thấy cùng một trạm"))
    if _env.env("OMNIVOICE_DIR") and not _env.env("VOICE_STATION"):
        checks.append(_check("env-name", False, "OMNIVOICE_DIR", level="warn",
                             hint="tên biến cũ — đặt VOICE_STATION=<gốc trạm> (OMNIVOICE_DIR vẫn đọc được)"))
    old_bgm = [n for n in ("NEWS_BGM", "NEWS_BGM_VOL", "NEWS_BGM_DIR") if os.environ.get(n)]
    if old_bgm:
        checks.append(_check("env-name-bgm", False, ", ".join(old_bgm), level="warn",
                             hint="tên biến cũ — đổi sang VOICE_BGM, VOICE_BGM_VOL, VOICE_BGM_DIR"))

    checks.append(samples_check())
    if st is not None:
        wp = win_path_check(os.path.join(_env.engine_dir(), ".venv"))
        if wp:
            checks.append(wp)
    if st is None:
        why = "chưa có trạm — kiểm lại sau khi đặt trạm"
        checks += [_not_checked(n, why) for n in ("voices", "default-profile", "bgm-library")]
        return checks + engine_checks()

    from . import profiles
    vd = profiles.voices_dir()
    names = profiles.list_profiles() if os.path.isdir(vd) else []
    checks.append(_check("voices", os.path.isdir(vd), f"{vd} ({len(names)} profile)",
                         hint="chưa có kho giọng — `voice-studio init` rồi `voice-studio make-profile`"))
    default = profiles.get_default() if names else None
    checks.append(_check("default-profile", bool(default), default or "(không có)", level="warn",
                         hint="chưa có profile mặc định — ghi tên vào voices/_default.txt "
                              "hoặc đặt VOICE_DEFAULT_PROFILE; pipeline phải truyền --profile"))

    checks.append(bgm_check(_env.bgm_dir()))

    return checks + engine_checks()


BGM_DOC = "docs/bgm-generation.md"


def bgm_check(lib_dir):
    """Thư viện nhạc nền: có `bgm-library.json` chưa, và MỖI style khai trong đó có `<style>.mp3`
    chưa. Thiếu file là WARN, không FAIL — trạm vẫn đọc được giọng; nhưng pipeline chọn đúng style
    thiếu file sẽ dừng ở bước ghép (`bgm.pick` fail-closed), tức là sau khi đã tốn cả lượt tổng
    hợp. Báo ở đây để người dùng biết TRƯỚC lượt chạy. Doctor không sinh nhạc."""
    from . import bgm
    lib_file = os.path.join(lib_dir, bgm.LIBRARY_FILE)
    if not os.path.isfile(lib_file):
        return _check("bgm-library", False, lib_file, level="warn",
                      hint="chưa có thư viện nhạc nền — `voice-studio init` dựng khung rỗng")
    try:
        lib = bgm.library(lib_dir)
    except (OSError, ValueError, AttributeError) as e:     # AttributeError: json không phải object
        return _check("bgm-library", False, f"{lib_file}: {e}", level="warn",
                      hint="bgm-library.json hỏng — sửa tay hoặc xoá rồi `voice-studio init`")
    names = lib.names()
    missing = [n for n in names if not os.path.isfile(lib.path_of(n))]
    if not names:
        return _check("bgm-library", False, f"{lib_file} (0 style)", level="warn",
                      hint=f"thư viện chưa khai style nào — thêm style + <style>.mp3 ({BGM_DOC})")
    if missing:
        return _check("bgm-library", False,
                      f"{lib.dir} — {len(missing)}/{len(names)} style thiếu file mp3: "
                      + ", ".join(missing), level="warn",
                      hint=f"thêm <style>.mp3 (nhạc bạn có quyền dùng) vào {lib.dir}, hoặc sinh theo "
                           f"{BGM_DOC} (weights MusicGen là CC-BY-NC — không thương mại), hoặc bỏ "
                           "style đó khỏi bgm-library.json; pipeline chọn style thiếu file sẽ dừng "
                           "ở bước ghép")
    return _check("bgm-library", True, f"{lib.dir} ({len(names)} style, đủ file mp3)")


# Windows chưa bật đường dài: thư mục sâu nhất tối đa 248 ký tự. Gói torch (bản CUDA 2.13) có
# thư mục giấy phép lồng sâu ~160 ký tự tính từ gốc venv ⇒ gốc venv dài quá ~88 ký tự là `pip
# install torch` gãy giữa chừng với WinError 206 và để lại một torch cài dở (đo 28/09 khi cài
# sạch vào trạm embedded nằm trong %TEMP%). Chừa biên: cảnh báo từ 80 ký tự.
WIN_VENV_PATH_WARN = 80


def win_path_check(venv, windows=None):
    """Cảnh báo đường venv engine quá dài trên Windows; hệ khác (hoặc đường ngắn) ⇒ None."""
    windows = (os.name == "nt") if windows is None else windows
    if not windows:
        return None
    n = len(os.path.abspath(venv)) if os.name == "nt" else len(venv)
    return _check("win-path", n <= WIN_VENV_PATH_WARN, f"{venv} ({n} ký tự)", level="warn",
                  hint=f"đường venv engine dài hơn {WIN_VENV_PATH_WARN} ký tự: cài torch có thể gãy "
                       "(WinError 206) khi Windows chưa bật đường dài. Clone repo vào thư mục ngắn, "
                       "hoặc đặt trạm ở đường ngắn (`voice-studio init --station <thư mục ngắn>`); "
                       "bật LongPathsEnabled là việc của quản trị máy, không phải của agent")


def samples_check():
    """Bài mẫu của repo còn đúng không — offline, không cần trạm hay engine."""
    from . import samples
    try:
        ok, detail = samples.check()
    except FileNotFoundError as e:
        return _not_checked("samples", str(e))
    except (OSError, ValueError) as e:
        ok, detail = False, str(e)
    return _check("samples", ok, detail, level="warn",
                  hint="bài mẫu trong samples/ bị sửa lệch — `git status samples/`")


def engine_checks():
    """Phần không phụ thuộc trạm: ffmpeg · torch + thiết bị · omnivoice · weights trong cache."""
    checks = []
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
    have_engine = False
    try:
        importlib.import_module("omnivoice")
        checks.append(_check("omnivoice", True, "importable"))
        have_engine = True
        checks.append(transformers_check())
    except ImportError as e:
        checks.append(_check("omnivoice", False, str(e),
                             hint="`pip install \"<repo>[engine]\"` (omnivoice==0.2.1 + transformers "
                                  "trong khoảng đã đo; thêm -e trên máy phát triển)"))

    cached, hub = _hf_cache_has(engine.MODEL_ID)
    if have_engine:
        checks.append(_check("weights", cached, f"{engine.MODEL_ID} @ {hub}", level="warn",
                             hint="weights chưa có trong cache — lần tổng hợp đầu (speak/make-profile) "
                                  "chạy với OMNIVOICE_ONLINE=1; doctor không tải"))
    else:
        checks.append(_not_checked("weights", f"engine chưa cài — chưa kiểm cache {hub}"))
    # doctor không bao giờ nạp model (nặng hàng GB, có thể cần mạng): chưa ai chứng minh máy này
    # ĐỌC được thành tiếng. Nói thẳng điều đó thay vì để một bảng toàn PASS gợi ý ngược lại.
    checks.append(_not_checked(
        "synthesis", "doctor không nạp model",
        hint='thử thật: voice-studio speak --text "Xin chào" --out <trạm>/out/thu.wav --json'))
    return checks


def doctor(args):
    checks = run_checks()
    for c in checks:
        mark = "[" + MARKS[c["level"]] + "]"
        line = f"{mark:<13} {c['name']:<16} {c['detail']}"
        if c["hint"]:
            line += f"\n{'':<14}→ {c['hint']}"
        contract.log(line)
    errors = [c["name"] for c in checks if c["level"] == "error"]
    warns = [c["name"] for c in checks if c["level"] == "warn"]
    unchecked = [c["name"] for c in checks if c["level"] == NOT_CHECKED]
    result = {"voice_studio": API_VERSION, "version": __version__, "station": _env.resolve_station()[0],
              "checks": checks, "errors": errors, "warnings": warns, "not_checked": unchecked}
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
