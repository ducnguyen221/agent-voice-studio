"""station.py — dựng và vận hành trạm giọng: `init`, `export --personal`, `import`, `backup`,
`migrate --to separate`, `update`.

TRẠM là nơi chứa những gì của riêng người dùng (venv engine, kho giọng, nhạc nền, output);
repo chỉ chứa mã. Có HAI chế độ cài (F17):

    embedded   trạm = <repo>/workspace/ (gitignore), secret ở <repo>/.env — "mở một folder là
               thấy hết". MẶC ĐỊNH và là KHUYẾN NGHỊ cho người dùng mới.
    separate   trạm ngoài repo (mặc định ~/.voice), secret ở kho secret riêng của máy — cho
               người dùng nhiều máy, repo public của chính mình, nhiều repo chia sẻ trạm.

Lựa chọn ghi vào <repo>/studio.local.json (gitignore); `voice_studio._env.resolve_station()`
đọc lại nó cho MỌI lệnh. Máy đã có trạm ngoài (VOICE_STATION / OMNIVOICE_DIR đã đặt, hoặc
~/.voice đã có station.json / omnivoice/voices/) ⇒ tự chọn `separate`, KHÔNG hỏi, KHÔNG BAO
GIỜ tạo workspace/ — tránh hai nguồn sự thật.

`init` KHÔNG tạo venv, không cài torch, không tải model: nó in lệnh để người dùng tự chạy.
Mọi thao tác không đè file đã có (chạy lại an toàn); `update` không bao giờ xoá gì.
"""
import argparse
import datetime
import errno
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

from . import API_VERSION, __version__, _env, bgm, contract
from .contract import ContractError, StationMissing

MANIFEST = "voice-studio-export.json"
MODES = ("embedded", "separate")
SECRET_DIR_NAME = "voice-studio"          # ~/.secret/<tên> khi tách .env khỏi repo

# Tên file nhìn giống secret: không bao giờ vào gói export (backup chỉ kèm .env khi xin rõ).
SECRET_PATTERNS = ("*token*", "*secret*", "*credential*", ".env", ".env.*", "*.pem", "*.key")
# Không bao giờ đóng gói: venv, cache, prompt cache (dựng lại được), rác python.
SKIP_DIRS = {".venv", "venv", "cache", "__pycache__", ".git"}
SKIP_FILES = ("*.prompt.pt", "*.pyc")

CHOICE_TABLE = """\
Chọn cách đặt TRẠM GIỌNG (nơi chứa venv engine, giọng của bạn, nhạc nền, output):

  [1] embedded — gọn trong repo   ← KHUYẾN NGHỊ (Enter)
      Là gì : trạm nằm ở <repo>/workspace/, secret ở <repo>/.env (cả hai bị git bỏ qua).
      Lợi   : mở một folder là thấy hết; không phải đặt biến môi trường.
      Hại   : xoá folder repo là mất luôn giọng — đừng xoá repo để cài lại, dùng
              `voice-studio update`; nhớ `voice-studio backup`.
      Chọn khi: một máy, muốn dùng ngay, không rành kỹ thuật.

  [2] separate — trạm ngoài repo (mặc định ~/.voice)
      Là gì : trạm ở thư mục riêng; secret ở kho secret của máy (~/.secret/…).
      Lợi   : repo luôn sạch (an toàn khi repo là public của bạn); nhiều repo/nhiều máy
              dùng chung một trạm; cập nhật repo không đụng dữ liệu.
      Hại   : thêm một chỗ phải nhớ; nên đặt VOICE_STATION cho mọi công cụ khác thấy.
      Chọn khi: rành kỹ thuật, nhiều máy, hoặc repo public của chính bạn.

Sau này đổi ý được: `voice-studio migrate --to separate`.
"""


# ── tiện ích ───────────────────────────────────────────────────────────────────────────

def _is_secret_name(name):
    base = os.path.basename(name).lower()
    return any(fnmatch.fnmatchcase(base, pat) for pat in SECRET_PATTERNS) and base != ".env.example"


def _skip_file(name):
    """Tên này là rác dựng-lại-được (bỏ khỏi mọi gói) hay không?

    `fnmatch.fnmatch` chuẩn hoá hoa/thường THEO HỆ ĐIỀU HÀNH: cùng một `X.PROMPT.PT` bị bỏ
    qua trên Windows nhưng lọt vào gói trên macOS/Linux. Luật đóng gói không được đổi theo
    máy ⇒ tự hạ hoa/thường rồi so bằng `fnmatchcase`. `_is_secret_name` dùng cùng một khuôn.
    """
    return any(fnmatch.fnmatchcase(os.path.basename(name).lower(), pat) for pat in SKIP_FILES)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _template_dir():
    """Cây mẫu `templates/workspace/` đi cùng MÃ (bản clone chứa package này), rồi tới repo."""
    pkg_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for root in (pkg_repo, _env.repo_root()):
        if root:
            t = os.path.join(root, "templates", "workspace")
            if os.path.isdir(t):
                return t
    return None


def _venv_python_rel():
    return "omnivoice/.venv/Scripts/python.exe" if os.name == "nt" else "omnivoice/.venv/bin/python"


def venv_commands(st):
    """Lệnh tạo venv + cài engine để người dùng TỰ chạy (init không làm thay)."""
    venv = os.path.join(st, "omnivoice", ".venv")
    py = os.path.join(st, *_venv_python_rel().split("/"))
    repo = _env.repo_root() or "<thư mục repo agent-voice-studio>"
    torch = ("pip install torch --index-url https://download.pytorch.org/whl/cu126   # NVIDIA; "
             "không có GPU: bỏ --index-url" if sys.platform != "darwin"
             else "pip install torch   # Apple Silicon: dùng MPS")
    return [
        f"python -m venv \"{venv}\"",
        f"\"{py}\" -m {torch}",
        f"\"{py}\" -m pip install omnivoice==0.2.1",
        f"\"{py}\" -m pip install -e \"{repo}\"",
        f"OMNIVOICE_ONLINE=1 \"{py}\" -m voice_studio doctor   # lần đầu: tải weights (~4 GB)",
    ]


# ── nhận diện + chọn chế độ ────────────────────────────────────────────────────────────

def detect_external():
    """Máy đã có trạm ngoài? -> (đường trạm, lý do) hoặc None. Không ghi gì."""
    if _env.env("VOICE_STATION"):
        return _env._expand(_env.env("VOICE_STATION")), "biến VOICE_STATION đã đặt"
    if _env.env("OMNIVOICE_DIR"):
        return (os.path.dirname(_env._expand(_env.env("OMNIVOICE_DIR"))),
                "biến OMNIVOICE_DIR (tên cũ) đã đặt")
    home = _env.default_station()
    if _env.has_marker(home):
        return home, "~/.voice đã là một trạm (có station.json hoặc omnivoice/voices/)"
    return None


def _stdin_is_tty():
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:          # noqa: BLE001 — stdin bị thay (pytest, dịch vụ)
        return False


def _ask_console(prompt):
    contract.log(prompt)
    sys.stderr.write("Chọn [1/2] (Enter = 1, embedded): ")
    sys.stderr.flush()
    return input()


def choose_mode(station=None, mode=None, yes=False, ask=None):
    """-> (chế độ, gốc trạm, lý do). Ném ContractError khi cần người chọn mà không hỏi được."""
    repo = _env.repo_root()
    if station:
        return "separate", _env._expand(station), "--station"
    ext = detect_external()
    if ext:
        if mode == "embedded":
            raise ContractError(
                f"máy đã có trạm giọng ngoài ({ext[1]}: {ext[0]}); tạo thêm workspace/ sẽ thành "
                "hai nguồn sự thật. Dùng trạm đó (bỏ --mode) hoặc gỡ biến/trạm cũ trước.")
        return "separate", ext[0], f"nhận diện trạm có sẵn — {ext[1]}"
    if not mode:
        local = _env.local_config(repo) if repo else {}
        prev = local.get("mode")
        if prev == "separate" and local.get("station_path"):
            st, _src = _env.resolve_station()          # đọc station_path của lần chọn trước
            return "separate", st, "studio.local.json (lần chọn trước)"
        if prev in MODES:
            mode, why = prev, "studio.local.json (lần chọn trước)"
        elif yes:
            mode, why = "embedded", "--yes (nhận khuyến nghị)"
        else:
            if ask is None:
                if not _stdin_is_tty():
                    contract.log(CHOICE_TABLE)
                    raise ContractError(
                        "cần người dùng chọn chế độ cài. Agent: trình bảng trên cho người dùng, "
                        "rồi chạy lại với --mode embedded|separate (hoặc --yes = embedded).")
                ask = _ask_console
            try:
                ans = (ask(CHOICE_TABLE) or "").strip().lower()
            except EOFError:
                # Windows: stdin là NUL vẫn báo isatty() = True — hết dữ liệu nghĩa là không có người.
                raise ContractError(
                    "không đọc được lựa chọn (stdin không có người). Agent: trình bảng lựa chọn cho "
                    "người dùng, rồi chạy lại với --mode embedded|separate (hoặc --yes = embedded).")
            if ans in ("", "1", "embedded"):
                mode = "embedded"
            elif ans in ("2", "separate"):
                mode = "separate"
            else:
                raise ContractError(f"lựa chọn không hợp lệ: {ans!r} (1 = embedded, 2 = separate)")
            why = "người dùng chọn"
    else:
        why = "--mode"
    if mode == "embedded":
        if not repo:
            raise ContractError("chế độ embedded cần chạy từ bản clone repo (pip install -e <repo>); "
                                "bản cài wheel chỉ dùng được separate (--station DIR).")
        return "embedded", os.path.join(repo, _env.WORKSPACE), why
    return "separate", _env.default_station(), why


# ── init ───────────────────────────────────────────────────────────────────────────────

def _copy_template(dst, created):
    t = _template_dir()
    if not t:
        return
    for dp, dn, fn in os.walk(t):
        rel = os.path.relpath(dp, t)
        for n in fn:
            if n == _env.STATION_FILE and rel == ".":
                continue                       # station.json do init tự viết
            target = os.path.normpath(os.path.join(dst, rel, n))
            if not os.path.exists(target):
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(os.path.join(dp, n), target)
                created.append(os.path.relpath(target, dst).replace(os.sep, "/"))


def _station_json(st, mode, existing):
    path = os.path.join(st, _env.STATION_FILE)
    cur, err = _env.read_json(path)
    if err:
        raise ContractError(f"station.json hỏng, sửa tay hoặc xoá rồi chạy lại: {err}")
    base = {}
    t = _template_dir()
    if t:
        base = _env.read_json(os.path.join(t, _env.STATION_FILE))[0]
    voices = os.path.join(st, "omnivoice", "voices")
    default = None
    dfile = os.path.join(voices, "_default.txt")
    if os.path.isfile(dfile):
        with open(dfile, "r", encoding="utf-8") as f:
            default = f.read().strip() or None
    venv_exists = os.path.isdir(os.path.join(st, "omnivoice", ".venv"))
    computed = {
        "contract": API_VERSION,
        "mode": mode,
        "device": None,
        "default_profile": default,
        "venv": "omnivoice/.venv",
        "engine_dir": "omnivoice",
        "bgm_dir": "assets/bgm",
    }
    data = {k: v for k, v in base.items() if not k.startswith("_")}
    data.update(computed)
    data.update(cur)                      # giá trị người dùng đã sửa luôn thắng
    if "default_profile" not in cur or cur.get("default_profile") is None:
        data["default_profile"] = default
    data.setdefault("created_by", f"voice-studio {__version__}")
    data.setdefault("created", datetime.date.today().isoformat())
    changed = data != cur
    return path, data, changed, venv_exists


def _hook_text():
    py = sys.executable.replace("\\", "/")
    return ("#!/bin/sh\n"
            "# voice-studio: chặn commit dữ liệu trạm (workspace/), .env, studio.local.json và\n"
            "# chuỗi giống token. Cài bởi `voice-studio init` (chế độ embedded).\n"
            f"exec \"{py}\" -m voice_studio.precommit\n")


def _install_hook(repo):
    hooks = os.path.join(repo, ".git", "hooks")
    if not os.path.isdir(hooks):
        return "no-git"
    hook = os.path.join(hooks, "pre-commit")
    if os.path.exists(hook):
        return "kept"
    with open(hook, "w", encoding="utf-8", newline="\n") as f:
        f.write(_hook_text())
    try:
        os.chmod(hook, 0o755)
    except OSError:
        pass
    return "installed"


def do_init(station=None, mode=None, existing=False, yes=False, dry_run=False, ask=None):
    mode, st, why = choose_mode(station=station, mode=mode, yes=yes, ask=ask)
    repo = _env.repo_root()
    res = {"mode": mode, "station": st, "reason": why, "dry_run": bool(dry_run),
           "repo": repo, "created": [], "hook": None}
    if existing and not os.path.isdir(st):
        raise ContractError(f"--existing nhưng không có thư mục trạm: {st}")
    voices = os.path.join(st, "omnivoice", "voices")
    res["profiles"] = (len([n for n in os.listdir(voices) if n.endswith(".wav")
                            and not n.startswith("_")]) if os.path.isdir(voices) else 0)
    if dry_run:
        return res
    created = res["created"]
    if existing:
        # Trạm đang chạy: CHỈ ghi station.json — không tạo thư mục, không rải file mẫu.
        res["missing"] = [sub for sub in ("omnivoice/voices", "assets/bgm", "out", "cache")
                          if not os.path.isdir(os.path.join(st, *sub.split("/")))]
    else:
        for sub in ("omnivoice/voices", "assets/bgm", "out", "cache"):
            d = os.path.join(st, *sub.split("/"))
            if not os.path.isdir(d):
                os.makedirs(d)
                created.append(sub + "/")
        bgm.init_library(os.path.join(st, "assets", "bgm"))
        _copy_template(st, created)
    path, data, changed, venv_exists = _station_json(st, mode, existing)
    if changed:
        _write_json(path, data)
        created.append(_env.STATION_FILE)
    res["venv_exists"] = venv_exists
    res["default_profile"] = data.get("default_profile")
    if repo and os.path.isdir(repo):
        local_path = os.path.join(repo, _env.LOCAL_CONFIG)
        local = _env.read_json(local_path)[0]
        local.update({
            "mode": mode,
            "station_path": _env.WORKSPACE if mode == "embedded" else st,
            "secrets": ".env" if mode == "embedded" else f"~/.secret/{SECRET_DIR_NAME}",
        })
        _write_json(local_path, local)
        if mode == "embedded":
            res["hook"] = _install_hook(repo)
    return res


def _print_init(res):
    log = contract.log
    tag = "(xem trước — chưa ghi gì) " if res["dry_run"] else ""
    log(f"[init] {tag}chế độ: {res['mode']} · trạm: {res['station']}")
    log(f"[init] lý do: {res['reason']}")
    if res["dry_run"]:
        return
    for c in res["created"]:
        log(f"  + {c}")
    for m in res.get("missing") or []:
        log(f"  ! chưa có {m}/ (--existing không tự tạo — `voice-studio init --station … ` không cờ để dựng)")
    if res.get("hook") == "installed":
        log("[init] đã cài hook pre-commit chặn commit workspace/, .env, studio.local.json, token")
    if not res.get("venv_exists"):
        log("\nBước tiếp theo — tạo venv engine và cài (init không làm thay):")
        for c in venv_commands(res["station"]):
            log("  " + c)
    if res["mode"] == "separate":
        log(f"\nNên đặt biến cho mọi công cụ khác thấy trạm: VOICE_STATION={res['station']}")


def init_main(argv=None):
    ap = argparse.ArgumentParser(
        prog="voice-studio init",
        description="Dựng cây trạm giọng + station.json. Không tạo venv, không tải model.")
    ap.add_argument("--station", help="trạm ngoài repo (chọn separate, không hỏi)")
    ap.add_argument("--mode", choices=MODES, help="chọn chế độ không cần hỏi")
    ap.add_argument("--yes", action="store_true", help="nhận khuyến nghị (embedded) không hỏi")
    ap.add_argument("--existing", action="store_true",
                    help="nhận một trạm đang chạy: chỉ ghi station.json, không rải file mẫu")
    ap.add_argument("--dry-run", action="store_true", help="chỉ báo sẽ làm gì, không ghi")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        res = do_init(station=a.station, mode=a.mode, existing=a.existing, yes=a.yes,
                      dry_run=a.dry_run)
        _print_init(res)
        return res
    return contract.run(fn, args, args.json)


# ── export --personal / import ─────────────────────────────────────────────────────────

PERSONAL_ROOTS = ("omnivoice/voices", "assets/bgm")


def _walk(root, rel_root):
    base = os.path.join(root, *rel_root.split("/"))
    if not os.path.isdir(base):
        return
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for n in sorted(fn):
            full = os.path.join(dp, n)
            yield full, os.path.relpath(full, root).replace(os.sep, "/")


def personal_files(st):
    files = []
    for r in PERSONAL_ROOTS:
        files += [(f, rel) for f, rel in _walk(st, r) if not _skip_file(rel)]
    sj = os.path.join(st, _env.STATION_FILE)
    if os.path.isfile(sj):
        files.append((sj, _env.STATION_FILE))
    return files


def _zip(files, out, manifest):
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".part"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for full, rel in files:
                zf.write(full, rel)
            zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return out


def export_personal(st, out):
    st = _env._expand(st)
    if not os.path.isdir(st):
        raise StationMissing(f"không có trạm giọng: {st} (chạy `voice-studio init`)")
    files = personal_files(st)
    bad = [rel for _, rel in files if _is_secret_name(rel)]
    if bad:
        raise ContractError("từ chối đóng gói — có file trông như secret: " + ", ".join(bad) +
                            ". Dời chúng về kho secret rồi chạy lại.")
    manifest = {"kind": "personal", "contract": API_VERSION, "voice_studio": __version__,
                "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "files": [rel for _, rel in files]}
    path = _zip(files, out, manifest)
    return {"out": path, "files": manifest["files"], "station": st}


def _safe_member(name):
    """Tên thành phần trong gói có an toàn để ghép vào trạm không? (lớp một)

    Từ chối: rỗng · đường tuyệt đối · UNC · `..` · part rỗng · **dấu hai chấm ở BẤT KỲ part
    nào**. Chỉ soi `parts[0]` là không đủ trên Windows: `os.path.join` RESET khi gặp một
    thành phần có ổ đĩa, nên `foo/C:/x.txt` ghép ra `C:x.txt` — đường theo ổ đĩa, rơi vào
    thư mục hiện hành của ổ C chứ không phải trong trạm.
    """
    n = name.replace("\\", "/")
    if not n or n.startswith("/"):
        return False
    return not any(p == "" or p == ".." or ":" in p for p in n.split("/"))


def _member_target(st, name):
    """Đường đích tuyệt đối của `name` trong trạm `st` — hoặc None nếu nó thoát ra ngoài.

    Lớp hai, cố ý độc lập với `_safe_member`: kiểm HẬU NGHIỆM bằng `commonpath` trên đường
    đã `realpath`, nên một lối thoát mà lớp một chưa nghĩ tới (symlink, dạng tên lạ) vẫn bị
    chặn trước khi có byte nào được ghi.
    """
    if not _safe_member(name):
        return None
    root = os.path.realpath(st)
    target = os.path.realpath(os.path.join(root, *name.replace("\\", "/").split("/")))
    try:
        if os.path.commonpath([root, target]) != root or target == root:
            return None
    except ValueError:              # khác ổ đĩa trên Windows ⇒ chắc chắn ngoài trạm
        return None
    return target


def import_personal(zip_path, st, force=False):
    st = _env._expand(st)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if MANIFEST not in names:
            raise ContractError(f"{zip_path} không phải gói `voice-studio export --personal`")
        manifest = json.loads(zf.read(MANIFEST).decode("utf-8"))
        if manifest.get("kind") != "personal":
            raise ContractError("gói không phải loại personal")
        members = [n for n in names if n != MANIFEST]
        targets = {n: _member_target(st, n) for n in members}
        unsafe = [n for n in members if targets[n] is None]
        if unsafe:
            raise ContractError("gói chứa đường dẫn nguy hiểm: " + ", ".join(unsafe))
        secret = [n for n in members if _is_secret_name(n)]
        if secret:
            raise ContractError("gói chứa file trông như secret: " + ", ".join(secret))
        clash = [n for n in members if os.path.exists(targets[n])]
        if clash and not force:
            raise ContractError("trạm đích đã có: " + ", ".join(clash) +
                                " — dùng --force để ghi đè")
        for n in members:
            target = targets[n]
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(n) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return {"station": st, "written": members, "overwritten": clash}


def export_main(argv=None):
    ap = argparse.ArgumentParser(
        prog="voice-studio export",
        description="Đóng gói giọng cá nhân để chuyển máy: voices/ (+ _default.txt), assets/bgm/, "
                    "station.json. Không venv, không cache, không *.prompt.pt; từ chối file giống secret.")
    ap.add_argument("--personal", action="store_true", help="gói dữ liệu cá nhân (bắt buộc)")
    ap.add_argument("--out", required=True, help="file zip đích")
    ap.add_argument("--station", help="trạm nguồn (mặc định: trạm đang phân giải)")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        if not a.personal:
            raise ContractError("bản này chỉ hỗ trợ `export --personal`; sao lưu cả trạm: "
                                "`voice-studio backup`")
        res = export_personal(a.station or _env.station_dir(), a.out)
        contract.log(f"[export] {len(res['files'])} file → {res['out']}")
        return res
    return contract.run(fn, args, args.json)


def import_main(argv=None):
    ap = argparse.ArgumentParser(prog="voice-studio import",
                                 description="Nhập gói giọng cá nhân vào trạm.")
    ap.add_argument("zip", help="gói từ `voice-studio export --personal`")
    ap.add_argument("--station", help="trạm đích (mặc định: trạm đang phân giải)")
    ap.add_argument("--force", action="store_true", help="ghi đè file trùng tên")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        res = import_personal(a.zip, a.station or _env.station_dir(), force=a.force)
        contract.log(f"[import] {len(res['written'])} file → {res['station']}")
        return res
    return contract.run(fn, args, args.json)


# ── backup / migrate / update ──────────────────────────────────────────────────────────

BACKUP_SKIP_TOP = {"out", "cache"}


def backup(out, station=None, with_env=False):
    st = _env._expand(station) if station else _env.station_dir()
    if not os.path.isdir(st):
        raise StationMissing(f"không có trạm giọng: {st}")
    files = []
    for dp, dn, fn in os.walk(st):
        rel_dir = os.path.relpath(dp, st)
        dn[:] = [d for d in dn if d not in SKIP_DIRS and
                 not (rel_dir == "." and d in BACKUP_SKIP_TOP)]
        for n in sorted(fn):
            full = os.path.join(dp, n)
            rel = os.path.relpath(full, st).replace(os.sep, "/")
            if _skip_file(rel):
                continue
            if _is_secret_name(rel) and not with_env:
                contract.log(f"[backup] bỏ qua file giống secret: {rel} (thêm --with-env nếu cố ý)")
                continue
            files.append((full, rel))
    repo = _env.repo_root()
    if with_env and repo and os.path.isfile(os.path.join(repo, ".env")):
        files.append((os.path.join(repo, ".env"), ".env"))
    manifest = {"kind": "backup", "contract": API_VERSION, "station": st,
                "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "with_env": bool(with_env), "files": [r for _, r in files]}
    return {"out": _zip(files, out, manifest), "files": manifest["files"], "station": st}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _move_tree(src, dst):
    """Dời thư mục an toàn. Cùng ổ: `os.rename` — hỏng thì hỏng SẠCH, không đụng gì.
    Khác ổ: chép → đối chiếu sha256 từng file → mới xoá nguồn (ba bước rời).

    KHÔNG dùng shutil.move cho thư mục: khi rename bị từ chối (file đang bị giữ) nó âm thầm
    rơi về copytree + rmtree, rmtree dừng giữa chừng ⇒ cây nằm hai nơi, trông như mất dữ liệu.
    """
    try:
        os.rename(src, dst)
        return
    except OSError as e:
        cross = e.errno == errno.EXDEV or getattr(e, "winerror", None) == 17
        if not cross:
            raise ContractError(f"không dời được {src} → {dst} ({e}). Có thể một chương trình "
                                "đang mở file trong trạm — đóng nó rồi chạy lại. Chưa đụng gì.")
    shutil.copytree(src, dst)
    for dp, _dn, fn in os.walk(src):
        for n in fn:
            a = os.path.join(dp, n)
            b = os.path.join(dst, os.path.relpath(a, src))
            if not os.path.isfile(b) or _sha256(a) != _sha256(b):
                raise ContractError(f"chép sang {dst} không khớp ở {b} — nguồn {src} giữ nguyên, "
                                    "xoá bản chép dở ở đích rồi chạy lại.")
    try:
        shutil.rmtree(src)
    except OSError as e:
        raise ContractError(f"đã chép đủ và khớp sang {dst}, nhưng xoá nguồn {src} dở dang ({e}). "
                            "Phần còn lại ở nguồn là BẢN SAO — đừng chạy lại lệnh; đóng chương trình "
                            "đang giữ file rồi xoá tay.")


def _move_file(src, dst):
    try:
        os.rename(src, dst)
    except OSError:
        shutil.copy2(src, dst)
        if _sha256(src) != _sha256(dst):
            os.remove(dst)
            raise ContractError(f"chép {src} → {dst} không khớp; giữ nguyên nguồn")
        os.remove(src)


def migrate_to_separate(target=None):
    repo = _env.repo_root()
    if not repo:
        raise ContractError("không xác định được repo (cài -e từ bản clone, hoặc đặt VOICE_STUDIO_REPO)")
    ws = os.path.join(repo, _env.WORKSPACE)
    if not os.path.isdir(ws):
        raise ContractError(f"không có {ws} — máy này không ở chế độ embedded")
    target = _env._expand(target) if target else _env.default_station()
    if os.path.exists(target) and os.listdir(target):
        raise ContractError(f"thư mục đích không rỗng: {target} — chọn chỗ khác (--station)")
    env_file = os.path.join(repo, ".env")
    sec = os.path.join(os.path.expanduser("~"), ".secret", SECRET_DIR_NAME)
    moved_env = os.path.join(sec, ".env") if os.path.isfile(env_file) else None
    if moved_env and os.path.exists(moved_env):          # kiểm TRƯỚC khi dời gì
        raise ContractError(f"{moved_env} đã có — gộp tay rồi xoá {env_file}, sau đó chạy lại")
    if os.path.isdir(target):
        os.rmdir(target)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    _move_tree(ws, target)
    if moved_env:
        os.makedirs(sec, exist_ok=True)
        _move_file(env_file, moved_env)
    local_path = os.path.join(repo, _env.LOCAL_CONFIG)
    local = _env.read_json(local_path)[0]
    local.update({"mode": "separate", "station_path": target,
                  "secrets": f"~/.secret/{SECRET_DIR_NAME}"})
    _write_json(local_path, local)
    sj = os.path.join(target, _env.STATION_FILE)
    info, err = _env.read_json(sj)
    if not err and info:
        info["mode"] = "separate"
        _write_json(sj, info)
    return {"mode": "separate", "station": target, "env_moved_to": moved_env}


def update():
    repo = _env.repo_root()
    if not repo or not os.path.isdir(os.path.join(repo, ".git")):
        raise ContractError("không thấy bản clone git của repo — `update` chỉ chạy trên bản clone")
    r = subprocess.run(["git", "-C", repo, "pull", "--ff-only"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    if r.returncode != 0:
        raise contract.EngineError(
            "git pull --ff-only không chạy được (có sửa đổi cục bộ lệch nhánh?). Không xoá gì; "
            "xử lý tay rồi chạy lại.\n" + (r.stderr or r.stdout).strip())
    return {"repo": repo, "output": (r.stdout or "").strip()}


def backup_main(argv=None):
    ap = argparse.ArgumentParser(prog="voice-studio backup",
                                 description="Zip cả trạm (trừ venv, cache, out/, *.prompt.pt).")
    ap.add_argument("--out", required=True)
    ap.add_argument("--station")
    ap.add_argument("--with-env", action="store_true", help="kèm <repo>/.env (chứa secret!)")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        res = backup(a.out, a.station, a.with_env)
        contract.log(f"[backup] {len(res['files'])} file → {res['out']}")
        return res
    return contract.run(fn, args, args.json)


def migrate_main(argv=None):
    ap = argparse.ArgumentParser(prog="voice-studio migrate",
                                 description="Chuyển trạm embedded (workspace/) ra ngoài repo.")
    ap.add_argument("--to", required=True, choices=["separate"])
    ap.add_argument("--station", help="đích (mặc định ~/.voice)")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        res = migrate_to_separate(a.station)
        contract.log(f"[migrate] trạm giờ ở {res['station']} — đặt VOICE_STATION trỏ vào đó")
        return res
    return contract.run(fn, args, args.json)


def update_main(argv=None):
    ap = argparse.ArgumentParser(prog="voice-studio update",
                                 description="Cập nhật repo: git pull --ff-only. Không bao giờ xoá gì.")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        res = update()
        contract.log(res["output"] or "[update] đã mới nhất")
        return res
    return contract.run(fn, args, args.json)
