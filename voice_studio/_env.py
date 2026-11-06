"""_env.py — MỘT nơi duy nhất trong package quyết định trạm giọng, kho giọng, BGM và ffmpeg nằm ở đâu.

Package sống trong repo; trạm giọng (venv, model, giọng cá nhân, nhạc nền, output) sống trên
máy người dùng. Hai bên không được giả định vị trí của nhau — mọi đường dẫn đi qua các hàm
dưới đây, đọc biến môi trường MỖI LẦN gọi (không đóng băng lúc import).

Biến hợp đồng (tên mới trước, tên cũ đọc được để tương thích):

    VOICE_STATION      gốc trạm giọng                 (mặc định <repo>/workspaces/)
    OMNIVOICE_DIR      tên cũ: THƯ MỤC ENGINE (= $VOICE_STATION/omnivoice); đọc được,
                       không cảnh báo ở đây — `voice-studio doctor` mới là chỗ nhắc đổi tên
    VOICES_DIR         kho profile giọng              (mặc định <engine>/voices)
    VOICE_BGM_DIR      thư viện nhạc nền              (mặc định $VOICE_STATION/assets/bgm)
    VOICE_BGM          file nhạc nền cho lần ghép hiện tại (rỗng = không trộn)
    VOICE_BGM_VOL      âm lượng nhạc nền              (mặc định 0.10)
    FFMPEG_DIR         thư mục chứa ffmpeg/ffprobe    (rỗng = tìm trên PATH)
    VOICE_STUDIO_WORK  scratch / output tạm            (mặc định $VOICE_STATION/out)

`NEWS_BGM`, `NEWS_BGM_VOL`, `NEWS_BGM_DIR` là tên cũ của ba biến BGM: vẫn đọc được trong
MỘT phiên bản, kèm DeprecationWarning, rồi sẽ bị bỏ.

Hai chế độ cài (F17) dùng chung MỘT thứ tự phân giải trạm — `resolve_station()`:

    --station (lệnh đặt VOICE_STATION trong tiến trình) → VOICE_STATION → OMNIVOICE_DIR (cha)
    → <repo>/studio.local.json ("station_path") → <repo>/workspaces/ (có hay chưa; `init` tạo; tên số ít cũ `workspace/` chỉ được nhận nếu đã là trạm)
    → chưa xác định (không repo)

`<repo>` là bản clone đã `pip install -e` (có `pyproject.toml` cạnh package); đặt
`VOICE_STUDIO_REPO` để trỏ tường minh. Cài dạng wheel thì không có repo ⇒ không có tầng repo,
và thiếu cả biến lẫn cấu hình thì `station_dir()` báo mã 3 (không tự tạo thư mục nào ở thư mục cá nhân).
`station.json` ở gốc trạm có thể khai `engine_dir`, `bgm_dir` (tương đối theo gốc trạm).

Máy có OpcOS: venv engine và mô hình dọn giọng được cài ở `runtime/` (hợp đồng `runtime-resource-v1`):

    $OPCOS_RUNTIME → $OPCOS_ROOT/runtime → (`~/OpcOS/paths.json` có ⇒ `~/OpcOS/runtime`) → không có

    R/venvs/agent-voice-studio/omnivoice   venv engine           (`engine_venv()`)
    R/venvs/agent-voice-studio/sep|cv      venv dọn giọng         (`clean/clean_voice.py`, tự chứa)
    R/engines/agent-voice-studio/clean     mô hình dọn giọng      (`models/`, `checkpoints/`)

Không có gốc nào (plugin cài lẻ, CI) thì dùng đích cũ trong trạm — không phải lỗi (`RT_NO_OPCOS`).

Biến cấu hình đi theo thứ tự riêng: biến môi trường thật → `<repo>/.env` (**chỉ** khi
`studio.local.json: mode = embedded`) → chưa đặt. Chế độ `separate` KHÔNG bao giờ tự nạp
`.env`: ở đó repo có thể là bản public của chính người dùng, và tự nạp một file nằm trong
repo là mở cửa cho nó. `.env` giữ ĐƯỜNG DẪN và cấu hình máy, không bao giờ giữ token —
khuôn tên biến ở `<repo>/.env.example`.
"""
import json
import os
import re
import shutil
import sys
import warnings
from pathlib import Path

LOCAL_CONFIG = "studio.local.json"
STATION_NAME = "voice"                   # tên trạm = thư mục con `voice` trong OPCOS_WORKSPACES khi cài cạnh OpcOS
WORKSPACE = "workspaces"                 # trạm NHÚNG trong repo: chính `<repo>/workspaces` (nhãn nguồn phân giải)
LEGACY_WORKSPACE = "workspace"           # tên số ít cũ: chỉ còn được NHẬN, không bao giờ được tạo
STATION_FILE = "station.json"
ENV_FILE = ".env"
ENV_EXAMPLE = ".env.example"
# Hợp đồng F17 — tên chế độ dùng chung với `agent-marketing-team`, `agent-video-studio`.
MODES = ("embedded", "separate")

_LEGACY = {
    "VOICE_BGM": "NEWS_BGM",
    "VOICE_BGM_VOL": "NEWS_BGM_VOL",
    "VOICE_BGM_DIR": "NEWS_BGM_DIR",
}

# Ba tên KHÔNG BAO GIỜ được đọc từ `<repo>/.env`, vì cả ba đều quay ngược lại chính cái đã
# quyết định có đọc `.env` hay không:
#   VOICE_STUDIO_REPO — nói repo nằm đâu, mà `.env` nằm TRONG repo. Đọc là đệ quy vô hạn.
#   VOICE_STATION, OMNIVOICE_DIR — nói TRẠM NÀY nằm đâu. `.env` chỉ được nạp khi chế độ là
#     `embedded`, tức là trạm đã được chốt ở `<repo>/workspaces/`; để một dòng trong file đó
#     trỏ trạm đi nơi khác là tự tạo ra đúng cái "hai nguồn sự thật" mà cả bộ cài này sinh
#     ra để chặn. Trỏ trạm đi chỗ khác là việc của biến môi trường thật, hoặc của `migrate`.
_NEVER_FROM_DOTENV = frozenset({"VOICE_STUDIO_REPO", "VOICE_STATION", "OMNIVOICE_DIR"})


_warned = set()


def reset_deprecation_warnings():
    """Quên danh sách tên cũ đã cảnh báo — chỉ dùng trong test (mỗi test là một 'tiến trình')."""
    _warned.clear()


def _note_once(key, text):
    """Một dòng thông tin ra stderr, MỘT lần cho mỗi `key` trong mỗi tiến trình (stdout giữ cho JSON)."""
    if key not in _warned:
        _warned.add(key)
        print(text, file=sys.stderr, flush=True)


def _deprecated(old, new):
    """Cảnh báo tên cũ **một lần cho mỗi tên, mỗi tiến trình**."""
    if old not in _warned:
        _warned.add(old)
        warnings.warn(
            f"Biến {old} đã đổi tên thành {new}; tên cũ còn đọc được một phiên bản nữa.",
            DeprecationWarning, stacklevel=4)


def env(name):
    """Đọc biến `name`: `os.environ` → `<repo>/.env` (CHỈ chế độ embedded) → None.

    Bỏ khoảng trắng; rỗng coi như chưa đặt. Biến môi trường thật LUÔN thắng `.env`: máy đã
    đặt biến (máy chạy lịch) không được để một file lạc vào repo cướp cấu hình.

    Nếu `name` có tên cũ và chỉ tên cũ được đặt: trả giá trị tên cũ + DeprecationWarning
    **một lần cho mỗi tên, mỗi tiến trình**. Một lượt dựng video đọc các biến này nhiều lần;
    cảnh báo mỗi lần gọi chỉ làm log pipeline ồn lên chứ không nói thêm được gì.
    """
    val = (os.environ.get(name) or "").strip()
    if val:
        return val
    old = _LEGACY.get(name)
    if old:
        oval = (os.environ.get(old) or "").strip()
        if oval:
            _deprecated(old, name)
            return oval
    if name in _NEVER_FROM_DOTENV:
        return None
    dot = read_env_file()
    val = (dot.get(name) or "").strip()
    if val:
        return val
    if old:
        oval = (dot.get(old) or "").strip()
        if oval:
            _deprecated(old, name)
            return oval
    return None


def _expand(p):
    return os.path.abspath(os.path.expanduser(p))


def repo_root():
    """Gốc bản clone repo nếu package được cài `-e` từ đó (hoặc VOICE_STUDIO_REPO); không thì None."""
    r = env("VOICE_STUDIO_REPO")
    if r:
        return _expand(r)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if (os.path.isfile(os.path.join(here, "pyproject.toml"))
            and os.path.isdir(os.path.join(here, "voice_studio"))):
        return here
    return None


def read_json(path):
    """-> (dict, lỗi|None). File không có ⇒ ({}, None); JSON hỏng ⇒ ({}, thông báo)."""
    if not path or not os.path.isfile(path):
        return {}, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return {}, f"{path}: {e}"
    if not isinstance(data, dict):
        return {}, f"{path}: không phải object JSON"
    return data, None


def local_config(repo=None):
    """Nội dung `<repo>/studio.local.json` (lựa chọn chế độ cài), {} nếu không có."""
    repo = repo or repo_root()
    return read_json(os.path.join(repo, LOCAL_CONFIG))[0] if repo else {}


def mode(repo=None):
    """Chế độ cài đã chọn: `embedded` · `separate` · None (chưa chạy `voice-studio init`)."""
    m = (local_config(repo).get("mode") or "").strip()
    return m if m in MODES else None


# ── biến cấu hình: os.environ → <repo>/.env (CHỈ chế độ embedded) ───────────────────────

def env_file(repo=None):
    """`<repo>/.env` khi và CHỈ KHI chế độ là `embedded` và file có thật; không thì None."""
    repo = repo or repo_root()
    if not repo or mode(repo) != "embedded":
        return None
    f = os.path.join(repo, ENV_FILE)
    return f if os.path.isfile(f) else None


def read_env_file(repo=None):
    """Đọc `<repo>/.env` thành dict. Định dạng tối giản, CỐ Ý không hỗ trợ gì thêm:
    `TEN=giá trị` mỗi dòng, bỏ qua dòng trống và dòng `#`, bỏ `export ` đầu dòng, gỡ một
    lớp nháy bao ngoài. Không nội suy `$BIEN`, không nối dòng — mỗi tính năng thêm là một
    cách nữa để một file text trở thành mã chạy được.

    Đọc lại MỖI LẦN gọi (không cache): người dùng sửa `.env` rồi chạy lệnh ngay là chuyện
    thường, và một cache ở đây nghĩa là họ sửa xong mà không có gì đổi.
    """
    f = env_file(repo)
    if not f:
        return {}
    out = {}
    try:
        text = open(f, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        if s.startswith("export "):
            s = s[len("export "):]
        name, _, value = s.partition("=")
        name, value = name.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name:
            out[name] = value
    return out


def has_marker(path):
    """Thư mục có phải một trạm giọng không: có station.json hoặc omnivoice/voices/."""
    return bool(path) and (os.path.isfile(os.path.join(path, STATION_FILE)) or
                           os.path.isdir(os.path.join(path, "omnivoice", "voices")))


def opcos_base():
    """Giá trị `OPCOS_WORKSPACES` thành đường TUYỆT ĐỐI (`~` mở rộng, tương đối thì theo cwd lúc
    gọi); biến vắng hoặc rỗng ⇒ None. ĐÂY LÀ NƠI DUY NHẤT đọc biến này: `os.environ` thật, không
    qua `env()`/`.env` của repo — nó là con trỏ cấp máy."""
    base = (os.environ.get("OPCOS_WORKSPACES") or "").strip()
    if not base:
        return None
    return os.path.abspath(os.path.expanduser(base))


def opcos_dir(station="voice"):
    """`<OPCOS_WORKSPACES>/<station>` tuyệt đối, DÙ thư mục đó đã mang dấu trạm hay chưa; biến vắng ⇒ None."""
    base = opcos_base()
    return os.path.join(base, station) if base else None


def opcos_station(station="voice"):
    """Trạm OpcOS `<OPCOS_WORKSPACES>/<station>` nếu biến đặt, khác rỗng và thư mục đó MANG DẤU
    trạm; không thì None. Chỉ `init`/`doctor` gọi — `resolve_station()` không bao giờ đọc nó.

    Không tạo, không ghi, không cảnh báo; biến trỏ file thì không có thư mục con → None.
    """
    path = opcos_dir(station)
    return path if path and has_marker(path) else None


def embedded_station(repo):
    """-> (đường, nguồn) của trạm NHÚNG trong `repo`: `<repo>/workspaces`. Chỉ khi nó chưa có mà tên số ít
    cũ `<repo>/workspace` đã là một trạm thì nhận tên cũ (và nhắc đổi tên MỘT lần mỗi tiến trình); có cả
    hai thì ưu tiên `workspaces` và nhắc. Không tạo, không ghi gì ra đĩa."""
    new = os.path.join(repo, WORKSPACE)
    old = os.path.join(repo, LEGACY_WORKSPACE)
    if os.path.isdir(new):
        if has_marker(old):
            _note_once("layout-both", f"[voice-studio] có cả {old} (tên cũ) và {new}; đang dùng {new}. "
                       f"Chuyển dữ liệu cần giữ sang {WORKSPACE}/ rồi xoá {LEGACY_WORKSPACE}/.")
        return new, WORKSPACE
    if has_marker(old):
        _note_once("layout-old", f"[voice-studio] trạm nhúng đang ở tên cũ {old}; nên đổi tên thành {new} "
                   f"(thư mục `{WORKSPACE}`). Vẫn dùng được như cũ, không tự dời.")
        return old, LEGACY_WORKSPACE
    return new, WORKSPACE


UNSET = "unset"
# Câu chung cho mọi thông báo "chưa có trạm" và cho `doctor`: người còn giọng ở nơi khác đừng tưởng mất.
# KHÔNG nêu tên thư mục nào — chỉ chỉ cách trỏ vào nơi họ đang giữ dữ liệu.
OLD_DATA_HINT = "Có dữ liệu cũ ở nơi khác? Dùng `--station <đường>` để trỏ vào đó."
UNSET_HINT = ("chưa xác định được trạm giọng: bản cài này không nằm trong một bản clone repo "
              "và chưa đặt VOICE_STATION. Đặt VOICE_STATION=<thư mục trạm> (hoặc truyền "
              "--station), rồi chạy `voice-studio init --station <thư mục trạm>`. " + OLD_DATA_HINT)


def resolve_station():
    """-> (gốc trạm | None, nguồn). Đọc lại mỗi lần gọi. Thứ tự:

        VOICE_STATION → OMNIVOICE_DIR (cha) → <repo>/studio.local.json → <repo>/workspaces/ (nếu chưa có mà
        `<repo>/workspace/` cũ đã là trạm thì nhận tên cũ + nhắc đổi tên) → <repo>/workspaces/ (chưa
        có; `init` sẽ tạo) → (None, `unset`)

    Không đặt gì thì trạm là THƯ MỤC TRONG REPO (bị git bỏ qua), không bao giờ là một thư mục
    ẩn dưới thư mục cá nhân. Cài dạng wheel (không có repo) mà
    chưa đặt gì ⇒ `unset` — `station_dir()` báo mã 3 kèm cách đặt, thay vì tự đẻ thư mục.
    """
    st = env("VOICE_STATION")
    if st:
        return _expand(st), "VOICE_STATION"
    eng = env("OMNIVOICE_DIR")
    if eng:
        return os.path.dirname(_expand(eng)), "OMNIVOICE_DIR"
    repo = repo_root()
    if repo:
        cfg = local_config(repo)
        sp = (cfg.get("station_path") or "").strip()
        if sp and cfg.get("mode") != "separate" and not os.path.isabs(os.path.expanduser(sp)) \
                and sp.replace("\\", "/").strip("/") in (WORKSPACE, LEGACY_WORKSPACE):
            # Giá trị `init` embedded (bản cũ ghi `workspace`, bản mới `workspaces`) KHÔNG được tin theo
            # chữ: đổi tên thư mục theo gợi ý không được làm mất trạm, và có cả hai thì phải theo luật chung.
            return embedded_station(repo)
        if sp:
            sp = os.path.expanduser(sp)
            return (sp if os.path.isabs(sp) else os.path.abspath(os.path.join(repo, sp))), LOCAL_CONFIG
    if repo and os.path.isdir(repo):
        return embedded_station(repo)
    return None, UNSET


def station_dir():
    """Gốc trạm giọng theo `resolve_station()`; chưa xác định được ⇒ StationMissing (mã 3)."""
    st = resolve_station()[0]
    if st is None:
        from .contract import StationMissing
        raise StationMissing(UNSET_HINT)
    return st


def station_info(station=None):
    """Nội dung `station.json` của trạm ({} nếu chưa có hoặc hỏng)."""
    return read_json(os.path.join(station or station_dir(), STATION_FILE))[0]


def _from_station(key, default_rel):
    st = station_dir()
    rel = station_info(st).get(key) or default_rel
    rel = os.path.expanduser(str(rel))
    return rel if os.path.isabs(rel) else os.path.join(st, *rel.replace("\\", "/").split("/"))


def engine_dir():
    """Thư mục engine (venv + voices): OMNIVOICE_DIR nếu đó là nguồn trạm; không thì
    `station.json: engine_dir` → <trạm>/omnivoice."""
    st, src = resolve_station()
    if src == "OMNIVOICE_DIR":
        return _expand(env("OMNIVOICE_DIR"))
    return _from_station("engine_dir", "omnivoice")


# ── runtime/ của OpcOS (hợp đồng runtime-resource-v1 + runtime-layout-v2) ──────────────────────

RUNTIME_REPO_KEY = "agent-voice-studio"
RUNTIME_CATEGORIES = ("mcp", "engines", "tools", "venvs", "scripts", "bin", "maintenance", "state",
                      "logs", "cache", "backups", "_archive")
NEEDS_FILE = "opcos-runtime.json"
RESOURCE_MANIFEST = ".opcos-resource.json"
# slugPattern + windowsReservedPattern + slugMaxLength của runtime-layout-v2.json
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_WIN_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", re.IGNORECASE)
_SLUG_MAX = 64
# Ngân sách đường dài (`dir_rel`, `file_rel`) khi venv engine KHÔNG cài theo khoá: `pip install torch` không ghim
# kéo torch >= 2.13, thư mục giấy phép lồng sâu ~160 ký tự (phép đo PV-T22: gốc > ~88 ký tự là gãy WinError 206)
# ⇒ dùng số đo PLAN TK5 cho venv torch 2.13 (sep/cv): 186/197. Số 109/150 của `opcos-runtime.json` chỉ đúng với
# torch 2.12 mà khoá `locks/omnivoice-windows.txt` ghim, tức venv do `opcos-runtime` dựng (có tệp khai sinh).
DEFAULT_PATH_BUDGET = (186, 197)


def _bad_key(what, value, why):
    return ValueError(f"RT_BAD_KEY {what} {value!r}: {why}")


def _check_slug(what, value):
    if (not isinstance(value, str) or not _SLUG.match(value) or len(value) > _SLUG_MAX
            or _WIN_RESERVED.match(value)):
        raise _bad_key(what, value, f"phải khớp {_SLUG.pattern}, dài ≤ {_SLUG_MAX}, "
                                    "không phải tên dành riêng của Windows")


def runtime_root(env=None, home=None, isfile=None):
    """Gốc runtime R theo hợp đồng, hoặc None khi máy không có OpcOS (`RT_NO_OPCOS` — không phải lỗi).

        $OPCOS_RUNTIME → $OPCOS_ROOT/runtime → (`<home>/OpcOS/paths.json` có ⇒ `<home>/OpcOS/runtime`) → None

    `env` (dict, mặc định `os.environ`), `home` (mặc định thư mục cá nhân) và `isfile` (mặc định
    `os.path.isfile`) chỉ để test thuần. Biến rỗng/khoảng trắng coi như chưa đặt. Không tạo gì.
    """
    environ = os.environ if env is None else env

    def get(name):
        return (environ.get(name) or "").strip()

    if get("OPCOS_RUNTIME"):
        return Path(get("OPCOS_RUNTIME"))
    if get("OPCOS_ROOT"):
        return Path(get("OPCOS_ROOT")) / "runtime"
    base = Path(home if home is not None else os.path.expanduser("~")) / "OpcOS"
    if (isfile or os.path.isfile)(base / "paths.json"):
        return base / "runtime"
    return None


def _resource_path(category, repo_key, resource_key, env=None, home=None, isfile=None):
    """`R/<category>/<repoKey>/<resourceKey>` hoặc None (không có R). Khoá sai ⇒ ValueError("RT_BAD_KEY …")
    — kiểm TRƯỚC khi tìm R, để khoá sai báo lỗi cả trên máy không có OpcOS."""
    if category not in RUNTIME_CATEGORIES:
        raise _bad_key("category", category, "không thuộc 12 category của runtime-layout-v2")
    _check_slug("repoKey", repo_key)
    if repo_key == "shared":
        raise _bad_key("repoKey", repo_key, "`shared` dành riêng cho tài nguyên dùng chung")
    _check_slug("resourceKey", resource_key)
    root = runtime_root(env=env, home=home, isfile=isfile)
    return None if root is None else root / category / repo_key / resource_key


def runtime_resource(category, resource_key, env=None, home=None, isfile=None):
    """Đích tài nguyên RIÊNG của repo này: `R/<category>/agent-voice-studio/<resource_key>`; None nếu máy
    không có OpcOS (dùng đích cũ). Không kiểm tồn tại — chỗ gọi tự `is_dir()`."""
    return _resource_path(category, RUNTIME_REPO_KEY, resource_key, env=env, home=home, isfile=isfile)


def opcos_runtime_cli(windows=None, env=None, home=None, isfile=None):
    """Lệnh gọi CLI `opcos-runtime` (dạng argv, chưa kèm lệnh con), hoặc None khi không có R hay không
    có tệp vỏ — nghĩa là chưa cài công cụ, KHÔNG phải lỗi.

    Tệp vỏ ở `<R>/../system/operations/runtime/opcos-runtime.ps1` (Windows, chạy qua PowerShell) hoặc `.sh`.
    """
    root = runtime_root(env=env, home=home, isfile=isfile)
    if root is None:
        return None
    windows = (os.name == "nt") if windows is None else windows
    name = "opcos-runtime.ps1" if windows else "opcos-runtime.sh"
    script = root.parent / "system" / "operations" / "runtime" / name
    if not (isfile or os.path.isfile)(script):
        return None
    return ["powershell", "-NoProfile", "-File", str(script)] if windows else ["bash", str(script)]


def venv_path_budget(key="omnivoice", repo=None):
    """(`dir_rel`, `file_rel`) của venv `key` khai trong `<repo>/opcos-runtime.json`; không khai/không có tệp
    thì `DEFAULT_PATH_BUDGET` (186/197). Dùng cho phép kiểm đường dài của `doctor` (FR3.8)."""
    repo = repo or repo_root()
    doc = read_json(os.path.join(repo, NEEDS_FILE))[0] if repo else {}
    for n in doc.get("needs") or []:
        if isinstance(n, dict) and n.get("category") == "venvs" and n.get("key") == key:
            p = n.get("paths") or {}
            if isinstance(p.get("dir_rel"), int) and isinstance(p.get("file_rel"), int):
                return p["dir_rel"], p["file_rel"]
    return DEFAULT_PATH_BUDGET


def engine_path_budget(venv, repo=None):
    """Ngân sách đường dài của venv engine `venv`: có `.opcos-resource.json` (cài theo khoá, torch ghim) ⇒ số
    khai trong `opcos-runtime.json` (109/150); không có (venv tự dựng, torch không ghim) ⇒ 186/197 — xem
    `DEFAULT_PATH_BUDGET`."""
    if venv and (Path(venv) / RESOURCE_MANIFEST).is_file():
        return venv_path_budget("omnivoice", repo)
    return DEFAULT_PATH_BUDGET


def engine_venv(st=None):
    """Venv engine thật đang dùng (Path). Thứ tự:

        `station.json: venv` tuyệt đối VÀ tồn tại → `R/venvs/agent-voice-studio/omnivoice` nếu tồn tại
        → `<engine_dir>/.venv`

    `venv` tương đối trong station.json (giá trị mẫu `omnivoice/.venv`) không tính: nó chỉ ghi lại đích
    cũ. `st` = gốc trạm (mặc định trạm đang phân giải); engine dir của `st` lấy từ station.json của nó.
    """
    info = station_info(st) if st else station_info()
    mine = os.path.expanduser(str(info.get("venv") or "").strip())
    if mine and os.path.isabs(mine) and os.path.isdir(mine):
        return Path(mine)
    rt = runtime_resource("venvs", "omnivoice")
    if rt is not None and rt.is_dir():
        return rt
    if st:
        rel = os.path.expanduser(str(info.get("engine_dir") or "omnivoice"))
        eng = rel if os.path.isabs(rel) else os.path.join(st, *rel.replace("\\", "/").split("/"))
        return Path(eng) / ".venv"
    return Path(engine_dir()) / ".venv"


def voices_dir():
    """Kho profile giọng: VOICES_DIR → <engine>/voices."""
    v = env("VOICES_DIR")
    return _expand(v) if v else os.path.join(engine_dir(), "voices")


def bgm_dir():
    """Thư viện nhạc nền: VOICE_BGM_DIR (tên cũ NEWS_BGM_DIR) → station.json: bgm_dir →
    <trạm>/assets/bgm."""
    d = env("VOICE_BGM_DIR")
    return _expand(d) if d else _from_station("bgm_dir", "assets/bgm")


def work_dir():
    """Thư mục làm việc/scratch: VOICE_STUDIO_WORK → $VOICE_STATION/out.

    CỐ Ý nằm ở trạm, không bao giờ trong repo hay trong package đã cài: output ở đây là
    audio giọng thật, một lệnh `git add` ẩu là đẩy nó lên public.
    """
    w = env("VOICE_STUDIO_WORK")
    return _expand(w) if w else os.path.join(station_dir(), "out")


def lab_dir(*parts):
    """Chỗ làm việc của bộ công cụ dựng giọng (đào clip, dựng profile): <work>/lab/…"""
    return os.path.join(work_dir(), "lab", *parts)


def _tool(name):
    d = env("FFMPEG_DIR")
    if d:
        found = shutil.which(name, path=_expand(d))
        if found:
            return found
    return shutil.which(name)


def ffmpeg_exe():
    """ffmpeg: FFMPEG_DIR → PATH → bản đóng gói của imageio-ffmpeg (nếu có) → lỗi kèm hướng dẫn."""
    found = _tool("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    raise RuntimeError(
        "Không tìm thấy ffmpeg. Cài ffmpeg (Windows: winget install Gyan.FFmpeg; "
        "macOS: brew install ffmpeg) hoặc đặt FFMPEG_DIR trỏ tới thư mục chứa nó.")


def ffprobe_exe():
    """ffprobe nếu có (không bắt buộc — thiếu thì đo thời lượng bằng ffmpeg)."""
    return _tool("ffprobe")
