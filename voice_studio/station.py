"""station.py — dựng và vận hành trạm giọng: `init`, `export --personal`, `import`, `backup`,
`migrate --to separate`, `update`, `uninstall`.

TRẠM là nơi chứa những gì của riêng người dùng (venv engine, kho giọng, nhạc nền, output);
repo chỉ chứa mã. Có HAI chế độ cài (F17):

    embedded   trạm = <repo>/workspaces/ (gitignore), secret ở <repo>/.env — "mở một folder là
               thấy hết". MẶC ĐỊNH và là KHUYẾN NGHỊ cho người dùng mới.
    separate   trạm ngoài repo (đường do người dùng chỉ; cài cạnh OpcOS thì <OPCOS_WORKSPACES>/voice),
               secret ở kho secret riêng của máy — cho người dùng nhiều máy, repo public của chính
               mình, nhiều repo chia sẻ trạm.

Lựa chọn ghi vào <repo>/studio.local.json (gitignore); `voice_studio._env.resolve_station()`
đọc lại nó cho MỌI lệnh. Máy đã đặt trạm ngoài (VOICE_STATION / OMNIVOICE_DIR) ⇒ tự chọn
`separate`, KHÔNG hỏi, KHÔNG BAO GIỜ tạo workspaces/ — tránh hai nguồn sự thật. Tên số ít cũ
`<repo>/workspace/` chỉ còn được NHẬN (nếu đã là trạm), không bao giờ được tạo.

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
MODES = _env.MODES                        # hợp đồng F17 — một nguồn sự thật ở _env
SECRET_DIR_NAME = "voice-studio"          # ~/.secret/<tên> khi tách .env khỏi repo
# Giá trị này ĐI VÀO studio.local.json, nên nó phải là ASCII và là một đường dẫn thật: một
# chuỗi mô tả có dấu đọc bằng công cụ khác encoding sẽ hiện ra rác, và không ai dán nó vào
# đâu được. Trùng đích mặc định của `voice-studio migrate --to separate`.
SECRET_STORE = f"~/.secret/{SECRET_DIR_NAME}"

# Tên file nhìn giống secret: không bao giờ vào gói export (backup chỉ kèm .env khi xin rõ).
SECRET_PATTERNS = ("*token*", "*secret*", "*credential*", ".env", ".env.*", "*.pem", "*.key")
# Không bao giờ đóng gói: venv, cache, prompt cache (dựng lại được), rác python.
SKIP_DIRS = {".venv", "venv", "cache", "__pycache__", ".git"}
SKIP_FILES = ("*.prompt.pt", "*.pyc")

CHOICE_TABLE = """\
Chọn chỗ đặt TRẠM GIỌNG (nơi chứa venv engine, giọng của bạn, nhạc nền, output):

  [1] embedded — gọn trong repo   ← KHUYẾN NGHỊ (bấm Enter)
      Là gì : trạm nằm ở <repo>/workspaces/, biến cấu hình ở <repo>/.env (git bỏ qua cả hai).
      Lợi   : mở một folder là thấy hết; không phải đặt biến môi trường; backup một phát.
      Hại   : xoá folder repo là mất luôn giọng — đừng xoá repo để cài lại, dùng
              `voice-studio update`; và nhớ `voice-studio backup`.
      Chọn khi: một máy, muốn dùng được ngay, không rành kỹ thuật.

  [2] separate — trạm ngoài repo (bạn chỉ đường; hoặc trạm OpcOS nếu OPCOS_WORKSPACES có trạm)
      Là gì : trạm ở thư mục riêng; bí mật ở kho secret của máy ({kho}).
      Lợi   : repo luôn sạch (an toàn khi repo là bản public của chính bạn); nhiều máy /
              nhiều repo dùng chung một trạm; cập nhật repo không đụng dữ liệu.
      Hại   : thêm một chỗ phải nhớ; nên đặt VOICE_STATION cho lịch chạy thấy trạm.
      Chọn khi: rành kỹ thuật, nhiều máy, hoặc repo public của chính bạn.

Sau này đổi ý được: `voice-studio migrate --to separate`.
""".format(kho=SECRET_STORE)

STATION_ASK_PATH = ("Nơi đặt trạm separate (đường dẫn; thư mục chưa có hoặc đang trống; "
                    "Enter để thôi): ")
STATION_CONFIRM = ("Trạm sẽ đặt ở {path} (OPCOS_WORKSPACES/voice). "
                   "Enter để nhận, hoặc gõ đường khác: ")
NEED_STATION = ("chế độ separate cần chỉ rõ nơi đặt trạm: chạy lại với --station DIR (hoặc đặt "
                "OPCOS_WORKSPACES để dùng <biến>/voice).")
# Gõ lựa chọn TRẦN ở câu nhận đường (câu này nhận ĐƯỜNG, không nhận "1"/"2") ⇒ mã 2, không tạo `<cwd>/1`.
STATION_CONFIRM_REJECT = ("1", "2", "embedded", "separate")
# Trạm nhúng cũ có dữ liệu, chưa ghi lựa chọn, máy có OPCOS_WORKSPACES: dữ liệu có sẵn thắng biến.
OLD_STATION_PROMPT = ("Trạm cũ có dữ liệu ở {path}. Enter = giữ và dùng như cũ; "
                      "gõ `chuyen` = dời vào {oc}: ")
MOVE_WORDS = ("chuyen", "chuyển", "c")
KEEP_OLD_LINE = ("[init] giữ trạm trong repo {path}; máy có OPCOS_WORKSPACES — dời sau bằng: "
                 "voice-studio migrate --to separate --station {oc}")
TWO_STATIONS_LINE = ("[init] giữ trạm trong repo {path}; {oc} cũng đã là một trạm — có hai trạm mang dấu: "
                     "gộp bằng tay, hoặc chọn một bằng --station {oc}")


class Choice(tuple):
    """Kết quả của `choose_mode`: unpack được như `(chế độ, gốc trạm, lý do)` (3 giá trị, như trước).

    `then_migrate` là cờ TƯỜNG MINH: không None ⇒ người dùng chọn dời trạm nhúng cũ vào đó. Hàm chọn chế
    độ KHÔNG BAO GIỜ dời dữ liệu — `do_init` đọc cờ này, ghi `embedded` trước, rồi (không `--dry-run`) mới
    gọi phần kiểm đích + xác nhận y/N của `migrate`.
    """
    def __new__(cls, mode, path, why, then_migrate=None):
        self = tuple.__new__(cls, (mode, path, why))
        self.then_migrate = then_migrate
        return self


def _unquote(text):
    """Bỏ khoảng trắng và MỘT cặp ngoặc kép/đơn bọc quanh đường dán (Windows 'Copy as path')."""
    s = (text or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


def _path(text):
    return _env._expand(_unquote(text))


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
    """Cây mẫu `templates/workspaces/` đi cùng MÃ (bản clone chứa package này), rồi tới repo."""
    pkg_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for root in (pkg_repo, _env.repo_root()):
        if root:
            t = os.path.join(root, "templates", _env.WORKSPACE)
            if os.path.isdir(t):
                return t
    return None


def venv_commands(st, windows=None):
    """Lệnh tạo venv + cài engine để người dùng TỰ chạy (init không làm thay).

    Cú pháp theo shell mặc định của hệ điều hành: PowerShell trên Windows (gọi exe có dấu nháy
    phải qua `&`, biến môi trường đặt bằng `$env:`), sh/zsh ở nơi khác. Một lệnh dán vào sai
    shell là lỗi cú pháp ngay dòng đầu — người mới không biết đó là lỗi của tài liệu.
    """
    windows = (os.name == "nt") if windows is None else windows
    venv = os.path.join(st, "omnivoice", ".venv")
    py = os.path.join(venv, "Scripts", "python.exe") if windows else os.path.join(venv, "bin", "python")
    run = f"& \"{py}\"" if windows else f"\"{py}\""
    repo = _env.repo_root() or "<thư mục repo agent-voice-studio>"
    torch = ("pip install torch --index-url https://download.pytorch.org/whl/cu126   # NVIDIA; "
             "không có GPU: bỏ --index-url" if sys.platform != "darwin"
             else "pip install torch   # Apple Silicon: dùng MPS")
    out_wav = os.path.join(st, "out", "thu.wav")
    first = (f"{run} -m voice_studio speak --text \"Xin chào\" --instruct \"female, young adult\" "
             f"--out \"{out_wav}\" --json")
    online = (f"$env:OMNIVOICE_ONLINE = \"1\"; {first}; Remove-Item Env:OMNIVOICE_ONLINE" if windows
              else f"OMNIVOICE_ONLINE=1 {first}")
    return [
        f"python -m venv \"{venv}\"",
        f"{run} -m {torch}",
        # Phần phụ `engine` = omnivoice==0.2.1 + transformers trong khoảng đã đo (pyproject.toml).
        f"{run} -m pip install -e \"{repo}[engine]\"   # omnivoice==0.2.1 + lệnh voice-studio; "
        "xưởng Windows chạy lịch có trạm riêng: bỏ -e (docs/INSTALL.md mục 3)",
        f"{run} -m voice_studio doctor   # kiểm engine (không tải gì)",
        online + "   # lần tổng hợp đầu: tải weights (~3,3 GB)",
    ]


def _under(path, root):
    """`path` nằm trong (hoặc là) `root`? So không phân biệt hoa/thường trên Windows."""
    if not root:
        return False
    a, b = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:              # khác ổ đĩa trên Windows
        return False


def _project_of(prefix):
    """Thư mục dự án chứa venv `prefix` (cha có `pyproject.toml` hoặc `.git`), hoặc None."""
    parent = os.path.dirname(os.path.abspath(prefix))
    if any(os.path.exists(os.path.join(parent, m)) for m in ("pyproject.toml", ".git")):
        return parent
    return None


def host_venv(st, repo=None, prefix=None, base_prefix=None, engine_ok=None):
    """`voice_studio` đang chạy từ một venv KHÁC venv engine chuẩn mà ta nên dùng luôn (vd `.venv`
    của repo video, nơi engine giọng được cài `-e` cùng tiến trình render)? -> dict, hoặc None.

    None (in lệnh tạo venv engine như cũ) khi: python hệ thống · chính `<trạm>/omnivoice/.venv` ·
    venv nằm TRONG bản clone repo giọng (phần A của INSTALL) · venv lẻ chưa có engine và không thuộc
    dự án nào. Còn lại — venv đã có engine, hoặc venv của một dự án khác — thì bảo người dùng tạo
    thêm `<trạm>/omnivoice/.venv` và tải lại weights là SAI: engine phải nằm cùng venv với bên gọi,
    và weights dùng chung cache Hugging Face của máy.
    """
    prefix = os.path.abspath(prefix or sys.prefix)
    base = os.path.abspath(base_prefix or sys.base_prefix)
    if os.path.normcase(prefix) == os.path.normcase(base):
        return None
    repo = repo if repo is not None else _env.repo_root()
    if _under(prefix, os.path.join(st, "omnivoice", ".venv")) or _under(prefix, repo):
        return None
    if engine_ok is None:
        import importlib.util
        engine_ok = all(importlib.util.find_spec(m) is not None for m in ("torch", "omnivoice"))
    project = _project_of(prefix)
    if not engine_ok and not project:
        return None
    from . import doctor, engine
    cached, hub = doctor._hf_cache_has(engine.MODEL_ID)
    return {"prefix": prefix, "project": project, "engine": bool(engine_ok),
            "weights_cached": cached, "hf_cache": hub}


# ── nhận diện + chọn chế độ ────────────────────────────────────────────────────────────

def detect_external():
    """Máy đã CHỌN một trạm ngoài (biến VOICE_STATION / OMNIVOICE_DIR — máy chạy lịch đặt biến là
    đã chọn)? -> (đường trạm, lý do) hoặc None. Không ghi gì, không dò thư mục nào khác."""
    if _env.env("VOICE_STATION"):
        return _env._expand(_env.env("VOICE_STATION")), "biến VOICE_STATION đã đặt"
    if _env.env("OMNIVOICE_DIR"):
        return (os.path.dirname(_env._expand(_env.env("OMNIVOICE_DIR"))),
                "biến OMNIVOICE_DIR (tên cũ) đã đặt")
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


def _ask_path_console(prompt):
    sys.stderr.write(prompt)
    sys.stderr.flush()
    return input()


def _reject_bare_choice(typed):
    """Câu nhận ĐƯỜNG mà người dùng gõ `1`/`2`/`embedded`/`separate` ⇒ mã 2 (không tạo thư mục `<cwd>/1`)."""
    if typed.strip().lower() in STATION_CONFIRM_REJECT:
        oc = _env.opcos_dir()
        raise ContractError(
            f"câu này nhận ĐƯỜNG DẪN, không nhận lựa chọn {typed.strip()!r}. Enter = {oc} "
            "(OPCOS_WORKSPACES/voice); gõ đường khác để dùng nơi khác; muốn trạm trong repo: "
            "chạy lại với --mode embedded. Chưa ghi gì.")


def _opcos_target():
    """`<OPCOS_WORKSPACES>/voice` tuyệt đối, hoặc None khi biến vắng. Biến (hay một thư mục cha của nó) hoặc
    `<biến>/voice` là một FILE ⇒ ContractError nêu TÊN BIẾN, trước mọi `makedirs` (lỗi hợp đồng của người gọi)."""
    base = _env.opcos_base()
    if not base:
        return None
    bad = '"' if '"' in base else (next((c for c in '<>|?*' if c in base[2:]), None) if os.name == "nt" else None)
    if bad:
        raise ContractError(
            f"OPCOS_WORKSPACES có ký tự không hợp lệ trong đường dẫn ({bad!r}): {base}. Đặt lại biến là một đường "
            "thư mục thuần, không kèm dấu nháy, hoặc chạy lại với --station DIR. Chưa ghi gì.")
    if _env.has_marker(base):
        raise ContractError(
            f"OPCOS_WORKSPACES trỏ vào chính một trạm ({base}); biến phải là thư mục CHA chứa các trạm. Đặt lại "
            f"biến, hoặc dùng --station {base}. Chưa ghi gì.")
    probe = base
    while not os.path.exists(probe) and os.path.dirname(probe) != probe:
        probe = os.path.dirname(probe)
    if os.path.exists(probe) and not os.path.isdir(probe):
        raise ContractError(
            f"OPCOS_WORKSPACES trỏ vào một FILE, không phải thư mục: {probe}. Đặt lại biến trỏ vào một "
            "thư mục (hoặc bỏ biến), hoặc chạy lại với --station DIR. Chưa ghi gì.")
    oc = os.path.join(base, "voice")
    if os.path.exists(oc) and not os.path.isdir(oc):
        raise ContractError(
            f"OPCOS_WORKSPACES/voice là một FILE, không phải thư mục: {oc}. Đổi tên/xoá file đó (hoặc "
            "đặt lại OPCOS_WORKSPACES), hoặc chạy lại với --station DIR. Chưa ghi gì.")
    return oc


def _keep_old_station(repo, ask, default_ask, interactive):
    """Dữ liệu có sẵn thắng biến (chưa ghi lựa chọn, máy có OPCOS_WORKSPACES): trạm nhúng trong repo đã
    MANG DẤU (xét cả hai tên) ⇒ GIỮ, không bao giờ dựng trạm OpcOS rỗng cạnh dữ liệu cũ. -> Choice | None.

    · `both` mới chưa dấu (`workspace` cũ mang dấu + `workspaces` chưa dấu): giữ `workspaces`, 0 câu, dòng nhắc
      gộp có sẵn (từ `_env.embedded_station`), KHÔNG gợi `migrate` (dời thư mục rỗng là vô nghĩa).
    · còn lại: có người ⇒ MỘT câu giữ/chuyển (Enter/EOF/chữ khác = giữ); `--yes`/không người ⇒ giữ + 1 dòng.
    Ctrl+C không bị bắt. Hàm này không dời gì: chọn chuyển chỉ đặt cờ `then_migrate`.
    """
    new_m = _env.has_marker(os.path.join(repo, _env.WORKSPACE))
    old_m = _env.has_marker(os.path.join(repo, _env.LEGACY_WORKSPACE))
    if not (new_m or old_m):
        return None
    oc = _opcos_target()                 # biến trỏ vào file ⇒ mã 2 nêu tên biến, trước mọi câu hỏi
    path = _env.embedded_station(repo)[0]
    why = f"trạm nhúng trong repo đã có dữ liệu ({path}); máy có OPCOS_WORKSPACES"
    if not new_m and os.path.isdir(os.path.join(repo, _env.WORKSPACE)):
        return Choice("embedded", path, why)                    # `both`: nhắc gộp đã in, không hỏi
    if interactive:
        try:
            typed = _unquote((_ask_path_console if default_ask else ask)(
                OLD_STATION_PROMPT.format(path=path, oc=oc)))
        except EOFError:                                        # hết dữ liệu = không có người = giữ
            typed = ""
        if typed.lower() in MOVE_WORDS:
            return Choice("embedded", path, why, then_migrate=oc)
    contract.log((TWO_STATIONS_LINE if _env.has_marker(oc) else KEEP_OLD_LINE).format(path=path, oc=oc))
    return Choice("embedded", path, why)


def choose_mode(station=None, mode=None, yes=False, ask=None, non_interactive=False):
    """-> Choice (unpack được `(chế độ, gốc trạm, lý do)`). Ném ContractError khi cần người chọn mà không hỏi được.

    Thứ tự ưu tiên:

        --station → biến trạm riêng → lựa chọn đã ghi → --mode (embedded: trạm nhúng; separate: đã dấu ? dùng :
        có người ? 1 câu : dựng + 1 dòng) → máy có OPCOS_WORKSPACES?
            không ─ có người ? bảng [1]/[2] : (--yes ? trạm nhúng : mã 2)
            có ──── trạm nhúng đã mang dấu, chưa ghi lựa chọn ⇒ GIỮ (--yes/không người/Enter/EOF) hoặc, có người
                    gõ `chuyen`, trả cờ `then_migrate` (hàm này không dời gì)
                    · `--yes` / không người / không terminal ⇒ `<biến>/voice` (đã dấu ? dùng thẳng : dựng + 1 dòng)
                    · có người ⇒ 1 câu nhận đường: Enter = `<biến>/voice`; đường ⇒ dùng đường đó; `1`/`2`/
                      `embedded`/`separate` ⇒ mã 2; EOF ⇒ như `--yes` (không có người); Ctrl+C ⇒ lan ra
                      (`contract.run` đổi thành mã 2)

    `non_interactive` = người gọi TỰ KHAI "không có ai ngồi đây". Nó KHÔNG có nghĩa là "cứ đoán hộ tôi":
    khi máy KHÔNG đặt OPCOS_WORKSPACES, thiếu `--yes`/`--mode`/`--station` thì vẫn là mã 2 (đoán ở đây là dựng
    trạm sai chỗ). Khi máy có OPCOS_WORKSPACES thì chỗ đặt đã biết — trạm OpcOS `<biến>/voice`.
    """
    repo = _env.repo_root()
    from_prev = False                    # chế độ lấy từ studio.local.json — không đề xuất trạm OpcOS
    default_ask = ask is None
    # `--yes` là "đừng hỏi gì cả" (có terminal hay không): không đường nào dưới đây được gọi input().
    interactive = not yes and (ask is not None or (not non_interactive and _stdin_is_tty()))
    if station:
        return Choice("separate", _path(station), "--station")
    ext = detect_external()
    if ext:
        if mode == "embedded":
            raise ContractError(
                f"máy đã có trạm giọng ngoài ({ext[1]}: {ext[0]}); tạo thêm workspaces/ sẽ thành "
                "hai nguồn sự thật. Dùng trạm đó (bỏ --mode) hoặc gỡ biến/trạm cũ trước.")
        return Choice("separate", ext[0], f"nhận diện trạm có sẵn — {ext[1]}")
    if not mode:
        local = _env.local_config(repo) if repo else {}
        prev = local.get("mode")
        if prev == "separate" and local.get("station_path"):
            st, _src = _env.resolve_station()          # đọc station_path của lần chọn trước
            return Choice("separate", st, "studio.local.json (lần chọn trước)")
        if prev in MODES:
            mode, why = prev, "studio.local.json (lần chọn trước)"
            from_prev = True
        else:
            if repo and _env.opcos_base():
                kept = _keep_old_station(repo, ask, default_ask, interactive)
                if kept is not None:
                    return kept
            if yes:
                if _env.opcos_base():
                    mode, why = "separate", "--yes + OPCOS_WORKSPACES"
                else:
                    mode, why = "embedded", "--yes (nhận khuyến nghị)"
            elif ask is None and (non_interactive or not _stdin_is_tty()):
                if not _env.opcos_base():
                    contract.log(CHOICE_TABLE)
                    raise ContractError(
                        "cần người dùng chọn chế độ cài. Agent: trình bảng trên cho người dùng, "
                        "rồi chạy lại với --mode embedded|separate, hoặc --station <đường> (trạm ngoài repo), "
                        "hoặc --yes (nhận trạm nhúng khi máy không đặt OPCOS_WORKSPACES).")
                mode, why = "separate", "không có người trả lời + OPCOS_WORKSPACES"
            else:
                ask = ask or _ask_console
                oc = _opcos_target()     # cài cạnh OpcOS: `<OPCOS_WORKSPACES>/voice`, dù chưa là trạm
                if oc:
                    # Một câu duy nhất: Enter nhận `<biến>/voice`, hoặc gõ đường khác.
                    eof = False
                    try:
                        typed = _unquote((_ask_path_console if default_ask else ask)(
                            STATION_CONFIRM.format(path=oc)))
                    except EOFError:     # Windows `< NUL`: isatty() = True nhưng hết dữ liệu = không có người
                        typed, eof = "", True
                    if typed:
                        _reject_bare_choice(typed)
                        return Choice("separate", _env._expand(typed), "người dùng chỉ đường trạm")
                    if eof:
                        contract.log(f"[init] separate: dùng {oc} (OPCOS_WORKSPACES/voice). "
                                     "Muốn nơi khác: --station <đường>.")
                        return Choice("separate", oc, f"hết dữ liệu ở câu hỏi (không có người): {oc}")
                    return Choice("separate", oc, f"người dùng nhận OPCOS_WORKSPACES/voice: {oc}")
                # [1] in ĐƯỜNG THẬT sẽ dùng (không để người đọc tự đoán `<repo>`)
                table = CHOICE_TABLE.replace(
                    "<repo>/workspaces/",
                    (_env.embedded_station(repo)[0] + "/") if repo else "<repo>/workspaces/")
                try:
                    ans = (ask(table) or "").strip().lower()
                except EOFError:
                    # Windows: stdin là NUL vẫn báo isatty() = True — hết dữ liệu nghĩa là không có người.
                    raise ContractError(
                        "không đọc được lựa chọn (stdin không có người). Agent: trình bảng lựa chọn cho "
                        "người dùng, rồi chạy lại với --mode embedded|separate, hoặc --station <đường> (trạm "
                        "ngoài repo), hoặc --yes (nhận trạm nhúng khi máy không đặt OPCOS_WORKSPACES).")
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
            raise ContractError("chế độ embedded cần biết bản clone repo: cài `pip install -e <repo>`, "
                                "hoặc bản sao kèm biến VOICE_STUDIO_REPO=<repo> (docs/INSTALL.md "
                                "mục 3); không thì chỉ dùng được separate (--station DIR).")
        return Choice("embedded", _env.embedded_station(repo)[0], why)
    if from_prev:
        raise ContractError(NEED_STATION)
    oc = _env.opcos_station()
    if oc:
        return Choice("separate", oc, f"trạm OpcOS: OPCOS_WORKSPACES đã đặt và {oc} là một trạm")
    ask_path = _ask_path_console if default_ask else ask
    suggest = _opcos_target()            # `<OPCOS_WORKSPACES>/voice` tuyệt đối, dù chưa mang dấu trạm
    if suggest:
        typed = ""
        if interactive:
            try:
                typed = _unquote(ask_path(STATION_CONFIRM.format(path=suggest)))
            except EOFError:
                typed = ""
        if typed:
            _reject_bare_choice(typed)
            return Choice("separate", _env._expand(typed), "người dùng chỉ đường trạm")
        contract.log(f"[init] separate: dùng {suggest} (OPCOS_WORKSPACES/voice). "
                     "Muốn nơi khác: --station <đường>.")
        return Choice("separate", suggest, f"OPCOS_WORKSPACES đã đặt: {suggest}")
    if interactive:
        try:
            typed = _unquote(ask_path(STATION_ASK_PATH))
        except EOFError:
            typed = ""
        if typed:
            return Choice("separate", _env._expand(typed), "người dùng chỉ đường trạm")
    raise ContractError(NEED_STATION)


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


# Dòng nhận diện hook do CHÍNH `init` cài (nằm trong `_hook_text`) — `uninstall` chỉ gỡ hook có nó.
HOOK_MARKER = "# voice-studio: chặn commit dữ liệu trạm"


def _hook_text():
    py = sys.executable.replace("\\", "/")
    return ("#!/bin/sh\n"
            "# voice-studio: chặn commit dữ liệu trạm (workspaces/), .env, studio.local.json và\n"
            "# chuỗi giống token. Cài bởi `voice-studio init` (chế độ embedded).\n"
            f"exec \"{py}\" -m voice_studio.precommit\n")


def _copy_env(repo, created):
    """`embedded`: dọn sẵn `<repo>/.env` từ `.env.example`, khoá quyền 600 trên POSIX.

    Không có bước này thì "clone là chạy" chỉ đúng một nửa: `.env` được `_env.env()` đọc,
    được `.gitignore` và hook chặn, được `doctor` kiểm — nhưng không ai tạo ra nó, nên người
    dùng phải tự biết là phải chép. Không đè file đã có (chạy lại bộ cài không ăn mất cấu
    hình của người ta).
    """
    src = os.path.join(repo, _env.ENV_EXAMPLE)
    dst = os.path.join(repo, _env.ENV_FILE)
    if os.path.exists(dst) or not os.path.isfile(src):
        return
    shutil.copyfile(src, dst)
    created.append(_env.ENV_FILE)
    if os.name != "nt":
        try:
            os.chmod(dst, 0o600)
        except OSError as e:               # hệ tệp không hỗ trợ (exFAT, chia sẻ mạng)
            contract.log(f"[init] không đặt được quyền 600 cho .env ({e}) — kiểm tay.")


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


def do_init(station=None, mode=None, existing=False, yes=False, dry_run=False, ask=None,
            non_interactive=False):
    choice = choose_mode(station=station, mode=mode, yes=yes, ask=ask, non_interactive=non_interactive)
    mode, st, why = choice
    then_migrate = choice.then_migrate           # explicit flag: the user chose to move the old embedded station
    repo = _env.repo_root()
    res = {"mode": mode, "station": st, "reason": why, "dry_run": bool(dry_run),
           "repo": repo, "created": [], "hook": None}
    if os.path.exists(st) and not os.path.isdir(st):
        raise ContractError(f"đường trạm trỏ vào một FILE, không phải thư mục: {st}")
    if existing and not os.path.isdir(st):
        raise ContractError(f"--existing nhưng không có thư mục trạm: {st}")
    voices = os.path.join(st, "omnivoice", "voices")
    res["profiles"] = (len([n for n in os.listdir(voices) if n.endswith(".wav")
                            and not n.startswith("_")]) if os.path.isdir(voices) else 0)
    if dry_run:
        if then_migrate:                         # xem trước: chưa dời, chưa ghi gì
            res["would_migrate"] = {"from": st, "to": then_migrate}
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
                try:
                    os.makedirs(d)
                except OSError as e:           # đường không dựng được (ổ không có, tên sai…) là lỗi cấu hình, không phải lỗi máy
                    base = _env.opcos_base()
                    from_var = bool(base) and os.path.normcase(st).startswith(os.path.normcase(base))
                    raise ContractError(
                        f"không tạo được thư mục trạm {st}: {e}." +
                        (" Kiểm giá trị OPCOS_WORKSPACES." if from_var else " Kiểm đường dẫn trạm."))
                created.append(sub + "/")
        bgm.init_library(os.path.join(st, "assets", "bgm"))
        _copy_template(st, created)
    path, data, changed, venv_exists = _station_json(st, mode, existing)
    if changed:
        _write_json(path, data)
        created.append(_env.STATION_FILE)
    res["venv_exists"] = venv_exists
    res["host_venv"] = None if venv_exists else host_venv(st, repo)
    res["default_profile"] = data.get("default_profile")
    if repo and os.path.isdir(repo):
        local_path = os.path.join(repo, _env.LOCAL_CONFIG)
        local = _env.read_json(local_path)[0]
        local.update({
            "mode": mode,
            # embedded: luôn ghi tên mới; bộ phân giải không tin chuỗi này (đi qua embedded_station)
            "station_path": _env.WORKSPACE if mode == "embedded" else st,
            "secrets": _env.ENV_FILE if mode == "embedded" else SECRET_STORE,
        })
        _write_json(local_path, local)
        if mode == "embedded":
            # Sau khi studio.local.json đã khai `mode: embedded` — trước đó `_env.env_file()`
            # còn trả None và một `.env` vừa chép ra sẽ không được ai đọc.
            _copy_env(repo, created)
            res["hook"] = _install_hook(repo)
    if then_migrate:
        _migrate_after_init(res, then_migrate, ask)
    return res


def _migrate_after_init(res, target, ask):
    """`init` chose to move the old embedded station: the station đã được dựng + ghi `embedded`. Kiểm đích TRƯỚC (không rỗng ⇒
    mã 2, trạm cũ vẫn dùng được), rồi đúng câu tóm tắt + y/N của `migrate`. `n`/Enter/EOF ⇒ giữ, mã 0."""
    plan = _migrate_plan(target, count=True)
    if not _confirm_move(plan, ask or _ask_line):
        res["moved"] = False
        contract.log(f"[init] giữ trạm trong repo {res['station']}; dời sau bằng: "
                     f"voice-studio migrate --to separate --station {target}")
        return
    moved = migrate_to_separate(plan["target"])
    res.update(mode="separate", station=moved["station"], moved=True, env_moved_to=moved["env_moved_to"])


def _print_init(res):
    log = contract.log
    tag = "(xem trước — chưa ghi gì) " if res["dry_run"] else ""
    log(f"[init] {tag}chế độ: {res['mode']} · trạm: {res['station']}")
    log(f"[init] lý do: {res['reason']}")
    if res["dry_run"]:
        if res.get("would_migrate"):
            log(f"[init] sẽ dời {res['would_migrate']['from']} → {res['would_migrate']['to']} "
                "(khi chạy thật: hỏi y/N trước khi dời)")
        return
    for c in res["created"]:
        log(f"  + {c}")
    for m in res.get("missing") or []:
        log(f"  ! chưa có {m}/ (--existing không tự tạo — `voice-studio init --station … ` không cờ để dựng)")
    if res.get("hook") == "installed":
        log("[init] đã cài hook pre-commit chặn commit workspaces/, .env, studio.local.json, token")
    hv = res.get("host_venv")
    if hv:
        who = f"dự án {hv['project']}" if hv.get("project") else "venv khác"
        log(f"\nvoice_studio đang chạy từ venv của {who}: {hv['prefix']}")
        log("  Dùng CHÍNH venv đó cho engine — KHÔNG tạo thêm <trạm>/omnivoice/.venv "
            "(bên gọi import voice_studio trong cùng tiến trình).")
        if hv["engine"]:
            log("  Engine (torch + omnivoice) đã có trong venv này — kiểm: voice-studio doctor")
        else:
            log("  Chưa có engine: cài torch rồi `pip install -e \"<repo agent-voice-studio>[engine]\"` "
                "VÀO venv này, theo INSTALL của dự án đó (agent-video-studio: mục 5b).")
        if hv["weights_cached"]:
            log(f"  Weights đã có trong cache ({hv['hf_cache']}) — không tải lại.")
        else:
            log("  Weights chưa có trong cache: lần tổng hợp đầu tải ~3,3 GB "
                "(OMNIVOICE_ONLINE=1 cho riêng lệnh đó).")
    elif not res.get("venv_exists"):
        log("\nBước tiếp theo — tạo venv engine và cài (init không làm thay):")
        for c in venv_commands(res["station"]):
            log("  " + c)
    if res["mode"] == "separate":
        log(f"\nNên đặt biến cho lịch chạy thấy trạm: VOICE_STATION={res['station']}")
        log(f"Bí mật để ở kho secret của máy ({SECRET_STORE}); biến chỉ giữ ĐƯỜNG DẪN.")
    else:
        log("\nĐiền biến của bạn vào <repo>/.env (chỉ đường dẫn + cấu hình, KHÔNG token).")


def init_main(argv=None):
    ap = argparse.ArgumentParser(
        prog="voice-studio init",
        description="Dựng cây trạm giọng + station.json. Không tạo venv, không tải model.")
    ap.add_argument("--station", help="trạm ngoài repo (chọn separate, không hỏi)")
    ap.add_argument("--mode", choices=MODES, help="chọn chế độ không cần hỏi")
    ap.add_argument("--yes", action="store_true",
                    help="nhận khuyến nghị, không hỏi: <OPCOS_WORKSPACES>/voice nếu máy đặt biến này "
                         "(trừ khi đã có trạm nhúng cũ có dữ liệu: giữ), không thì trạm nhúng trong repo")
    ap.add_argument("--non-interactive", action="store_true",
                    help="không có ai trả lời: KHÔNG hỏi — máy có OPCOS_WORKSPACES thì dùng <biến>/voice; "
                         "không có thì KHÔNG đoán: thiếu --yes/--mode/--station dừng với mã 2")
    ap.add_argument("--existing", action="store_true",
                    help="nhận một trạm đang chạy: chỉ ghi station.json, không rải file mẫu")
    ap.add_argument("--dry-run", action="store_true", help="chỉ báo sẽ làm gì, không ghi")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        res = do_init(station=a.station, mode=a.mode, existing=a.existing, yes=a.yes,
                      dry_run=a.dry_run, non_interactive=a.non_interactive)
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
        raise StationMissing(f"không có trạm giọng: {st} (chạy `voice-studio init`). {_env.OLD_DATA_HINT}")
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
        raise StationMissing(f"không có trạm giọng: {st}. {_env.OLD_DATA_HINT}")
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


MIGRATE_ASK_WHERE = """\
Dời trạm giọng từ {ws} ra ngoài repo. Chọn nơi dời (đường tuyệt đối; thư mục chưa có hoặc đang trống).
{hint}
Đích: """

MIGRATE_NEED_STATION = ("migrate cần biết nơi dời: chạy lại với --station DIR (đường tuyệt đối, thư "
                        "mục chưa có hoặc đang trống). Không còn đích mặc định, và không hỏi được "
                        "khi không có người trả lời. Chưa dời gì.")


def _migrate_source():
    repo = _env.repo_root()
    if not repo:
        raise ContractError("không xác định được repo (cài -e từ bản clone, hoặc đặt VOICE_STUDIO_REPO)")
    ws = _env.embedded_station(repo)[0]          # `<repo>/workspaces` (hoặc tên số ít cũ nếu chỉ có nó)
    if not os.path.isdir(ws):
        raise ContractError(f"không có {ws} — máy này không ở chế độ embedded")
    return repo, ws


def _human_size(n):
    if n < 1024:
        return f"{n} byte"
    for unit, div in (("KB", 1024), ("MB", 1024 ** 2), ("GB", 1024 ** 3)):
        if n < div * 1024 or unit == "GB":
            return f"{n / div:.1f} {unit}"


def _tree_stats(ws, env_file=None):
    """-> (số file, tổng byte) của cây `ws` (+ `env_file` nếu có). Đi cả cây: chỉ gọi khi cần HIỂN THỊ."""
    files = [os.path.join(dp, n) for dp, _d, fn in os.walk(ws) for n in fn]
    if env_file:
        files.append(env_file)
    size = 0
    for f in files:
        try:
            size += os.path.getsize(f)
        except OSError:
            pass
    return len(files), size


def _is_inside(path, root):
    p, r = (os.path.normcase(os.path.realpath(x)) for x in (path, root))
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def _migrate_plan(target, count=False):
    """Kiểm MỌI điều kiện trước khi dời byte nào (không tạo gì). `count` ⇒ thêm số file/byte sẽ dời
    (đi cả cây — chỉ bật khi cần hiển thị)."""
    repo, ws = _migrate_source()
    if not target:
        raise ContractError(MIGRATE_NEED_STATION)
    target = _path(target)
    if _is_inside(target, ws):
        raise ContractError(f"đích nằm trong chính trạm đang dời ({ws}): {target} — không thể dời một "
                            "thư mục vào bên trong nó. Chọn nơi ngoài trạm (--station). Chưa dời gì.")
    if os.path.exists(target) and not os.path.isdir(target):
        raise ContractError(f"đích trỏ vào một FILE, không phải thư mục: {target} — chọn thư mục "
                            "khác (--station). Chưa dời gì.")
    if os.path.exists(target) and os.listdir(target):
        raise ContractError(f"thư mục đích không rỗng: {target} — chọn chỗ khác (--station)")
    env_file = os.path.join(repo, ".env")
    sec = os.path.join(os.path.expanduser("~"), ".secret", SECRET_DIR_NAME)
    moved_env = os.path.join(sec, ".env") if os.path.isfile(env_file) else None
    if moved_env and os.path.exists(moved_env):          # kiểm TRƯỚC khi dời gì
        raise ContractError(f"{moved_env} đã có — gộp tay rồi xoá {env_file}, sau đó chạy lại")
    plan = {"repo": repo, "ws": ws, "target": target, "env_file": env_file, "sec": sec,
            "moved_env": moved_env}
    if count:
        plan["files"], plan["bytes"] = _tree_stats(ws, env_file if moved_env else None)
    return plan


def _ask_line(prompt):
    sys.stderr.write(prompt)
    sys.stderr.flush()
    return input()


def do_migrate(station=None, ask=None, non_interactive=False):
    """`migrate --to separate`: có `--station` thì dời thẳng; không thì HỎI nơi dời (gợi ý trạm
    OpcOS nếu có), hiện đường tuyệt đối + số file/dung lượng và xin xác nhận y/N. Không có người
    trả lời ⇒ ContractError (mã 2): không bao giờ đoán nơi dời."""
    if station:
        return migrate_to_separate(station)
    interactive = ask is not None or (not non_interactive and _stdin_is_tty())
    if not interactive:
        raise ContractError(MIGRATE_NEED_STATION)
    ask = ask or _ask_line
    _repo, ws = _migrate_source()
    suggest = _opcos_target()            # gợi ý duy nhất: `<OPCOS_WORKSPACES>/voice`; không có thì không gợi ý
    hint = (f"Gợi ý (Enter để nhận): {suggest}" if suggest
            else "Không có gợi ý sẵn (OPCOS_WORKSPACES chưa đặt). Enter để thôi.")
    try:
        ans = _unquote(ask(MIGRATE_ASK_WHERE.format(ws=ws, hint=hint)))
    except EOFError:
        raise ContractError(MIGRATE_NEED_STATION)
    target = _path(ans) if ans else suggest
    if not target:
        raise ContractError("đã huỷ: chưa chọn nơi dời. Chưa dời gì.")
    plan = _migrate_plan(target, count=True)
    if not _confirm_move(plan, ask):
        raise ContractError("đã huỷ theo lựa chọn: chưa dời gì.")
    return migrate_to_separate(target)


def _confirm_move(plan, ask):
    """Hiện tóm tắt (đường tuyệt đối, số file, dung lượng) và xin y/N. EOF = không."""
    summary = (f"Sẽ dời {plan['ws']} → {plan['target']}\n"
               f"  {plan['files']} file, {_human_size(plan['bytes'])}"
               + (f" (gồm .env → {plan['moved_env']})" if plan["moved_env"] else "") + "\n"
               "Sau khi dời, repo trỏ vào đích qua studio.local.json. Dời xong khó quay lại bằng một lệnh.\n"
               "Dời? [y/N]: ")
    try:
        return (ask(summary) or "").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def migrate_to_separate(target=None):
    plan = _migrate_plan(target)                 # không đếm file: đã có đích rõ thì khỏi đi cả cây
    repo, ws, target = plan["repo"], plan["ws"], plan["target"]
    env_file, sec, moved_env = plan["env_file"], plan["sec"], plan["moved_env"]
    had_empty_dir = os.path.isdir(target)
    if had_empty_dir:
        os.rmdir(target)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    try:
        _move_tree(ws, target)
    except BaseException:                        # mọi lỗi dời/chép (OSError, shutil.Error, ContractError…)
        if had_empty_dir and not os.path.exists(target):
            os.makedirs(target)                  # trả lại thư mục rỗng của người dùng
        raise                                    # rồi ném lại đúng lỗi gốc
    if moved_env:
        os.makedirs(sec, exist_ok=True)
        _move_file(env_file, moved_env)
    local_path = os.path.join(repo, _env.LOCAL_CONFIG)
    local = _env.read_json(local_path)[0]
    local.update({"mode": "separate", "station_path": target, "secrets": SECRET_STORE})
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
    res = {"repo": repo, "output": (r.stdout or "").strip(), "reinstall": None}
    if installed_copy(repo):
        # Bản sao (máy chạy lịch, docs/INSTALL.md mục 3): git pull KHÔNG đổi mã đang chạy.
        res["reinstall"] = f"\"{sys.executable}\" -m pip install \"{repo}[engine]\""
    return res


def installed_copy(repo):
    """Package đang chạy là bản sao cài vào site-packages (không `-e` từ `repo`)?"""
    pkg_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.normcase(os.path.realpath(pkg_repo)) != os.path.normcase(os.path.realpath(repo))


# ── uninstall ──────────────────────────────────────────────────────────────────────────

PACKAGE = "agent-voice-studio"
# Plugin do lệnh của CHÍNH host cài (repo không tự ghi cấu hình host) ⇒ ở đây chỉ IN lệnh gỡ.
HOST_UNINSTALL = (
    "claude plugin uninstall agent-voice-studio@agent-voice-studio   # Claude Code, nếu đã cài plugin",
    "codex plugin uninstall agent-voice-studio@agent-voice-studio    # Codex, nếu đã cài plugin",
    "Claude Desktop / Antigravity: xoá mục MCP `omnivoice-tts` nếu bạn đã tự thêm",
)


def _our_hook(repo):
    """Đường hook pre-commit nếu nó do `voice-studio init` cài (có HOOK_MARKER); không thì None."""
    if not repo:
        return None
    hook = os.path.join(repo, ".git", "hooks", "pre-commit")
    try:
        with open(hook, "r", encoding="utf-8", errors="replace") as f:
            return hook if HOOK_MARKER in f.read() else None
    except OSError:
        return None


def _pip_uninstall_cmd():
    return [sys.executable, "-m", "pip", "uninstall", "-y", PACKAGE]


def plan_uninstall(keep_package=False):
    """Kế hoạch gỡ — KHÔNG ghi gì. Gỡ phần mềm, GIỮ dữ liệu của người dùng."""
    repo = _env.repo_root()
    st, src = _env.resolve_station()
    kept = []
    if st and os.path.isdir(st):
        kept.append(f"trạm giọng {st} (nguồn: {src}) — giọng, nhạc nền, output, venv engine")
    if repo:
        for name in (_env.ENV_FILE, _env.LOCAL_CONFIG):
            if os.path.isfile(os.path.join(repo, name)):
                kept.append(os.path.join(repo, name))
    return {
        "remove_hook": _our_hook(repo),
        "remove_package": None if keep_package else PACKAGE,
        "pip": None if keep_package else " ".join(_pip_uninstall_cmd()),
        "kept": kept,
        "host_commands": list(HOST_UNINSTALL),
        "repo": repo,
    }


def do_uninstall(keep_package=False, dry_run=False):
    plan = plan_uninstall(keep_package)
    res = dict(plan, dry_run=bool(dry_run), removed=[])
    if dry_run:
        return res
    if plan["remove_hook"]:
        os.remove(plan["remove_hook"])
        res["removed"].append(plan["remove_hook"])
    if not keep_package:
        r = subprocess.run(_pip_uninstall_cmd(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        if r.returncode != 0:
            raise contract.EngineError(
                "pip uninstall không chạy được — dữ liệu chưa bị đụng. Tự chạy: "
                + res["pip"] + "\n" + (r.stderr or r.stdout).strip())
        res["removed"].append(PACKAGE)
    return res


def _print_uninstall(res):
    log = contract.log
    tag = "(xem trước — chưa đụng gì) " if res["dry_run"] else ""
    verb = "sẽ gỡ" if res["dry_run"] else "đã gỡ"
    if res["remove_hook"]:
        log(f"[uninstall] {tag}{verb} hook pre-commit của voice-studio: {res['remove_hook']}")
    if res["remove_package"]:
        log(f"[uninstall] {tag}{verb} package {res['remove_package']} khỏi {sys.executable}")
        log("            (gói khác cài cùng venv này và import voice_studio sẽ mất phần giọng)")
    for k in res["kept"]:
        log(f"[uninstall] GIỮ NGUYÊN {k}")
    log("\nPlugin/MCP do host cài — gỡ bằng lệnh của host nếu bạn đã cài:")
    for c in res["host_commands"]:
        log("  " + c)
    log("\nMuốn xoá hẳn dữ liệu: `voice-studio backup` trước, rồi tự xoá thư mục trạm.")


def _confirm_uninstall(keep_package):
    """Không `--yes`: có người thì hỏi y/N; không có người thì mã 2 (không đoán)."""
    _print_uninstall(do_uninstall(keep_package, dry_run=True))
    if not _stdin_is_tty():
        raise ContractError("cần người dùng đồng ý. Agent: trình kế hoạch trên cho người dùng, "
                            "rồi chạy lại với --yes (hoặc --dry-run để chỉ xem).")
    sys.stderr.write("Gỡ? [y/N]: ")
    sys.stderr.flush()
    try:
        ans = input().strip().lower()
    except EOFError:
        ans = ""
    if ans not in ("y", "yes", "c", "có"):
        raise ContractError("đã huỷ — chưa đụng gì")


def uninstall_main(argv=None):
    ap = argparse.ArgumentParser(
        prog="voice-studio uninstall",
        description="Gỡ phần mềm, GIỮ dữ liệu: bỏ hook pre-commit do init cài và `pip uninstall` "
                    "package. Trạm, giọng, .env, studio.local.json không bị đụng.")
    ap.add_argument("--dry-run", action="store_true", help="chỉ in sẽ làm gì")
    ap.add_argument("--yes", action="store_true", help="gỡ không hỏi lại")
    ap.add_argument("--keep-package", action="store_true",
                    help="chỉ gỡ hook, giữ package (vd venv dùng chung với gói khác)")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        if not a.dry_run and not a.yes:
            _confirm_uninstall(a.keep_package)
        res = do_uninstall(a.keep_package, dry_run=a.dry_run)
        _print_uninstall(res)
        return res
    return contract.run(fn, args, args.json)


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
                                 description="Chuyển trạm embedded (workspaces/) ra ngoài repo.")
    ap.add_argument("--to", required=True, choices=["separate"])
    ap.add_argument("--station", help="nơi dời tới (đường tuyệt đối). Thiếu thì HỎI; không có người "
                                      "trả lời thì dừng với mã 2 — không có đích mặc định")
    ap.add_argument("--non-interactive", action="store_true",
                    help="không có ai trả lời: không hỏi; thiếu --station thì dừng với mã 2")
    ap.add_argument("--json", action="store_true")
    args, code = contract.parse(ap, argv)
    if args is None:
        return code

    def fn(a):
        res = do_migrate(station=a.station, non_interactive=a.non_interactive)
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
        if res["reinstall"]:
            contract.log("[update] package là BẢN SAO — mã mới chưa vào venv. Cài lại (ngoài giờ "
                         "lịch chạy):\n  " + res["reinstall"])
        return res
    return contract.run(fn, args, args.json)
