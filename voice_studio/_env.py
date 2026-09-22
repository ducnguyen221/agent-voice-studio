"""_env.py — MỘT nơi duy nhất trong package quyết định trạm giọng, kho giọng, BGM và ffmpeg nằm ở đâu.

Package sống trong repo; trạm giọng (venv, model, giọng cá nhân, nhạc nền, output) sống trên
máy người dùng. Hai bên không được giả định vị trí của nhau — mọi đường dẫn đi qua các hàm
dưới đây, đọc biến môi trường MỖI LẦN gọi (không đóng băng lúc import).

Biến hợp đồng (tên mới trước, tên cũ đọc được để tương thích):

    VOICE_STATION      gốc trạm giọng                 (mặc định ~/.voice)
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
    → <repo>/studio.local.json ("station_path") → <repo>/workspace/ nếu có → ~/.voice

`<repo>` là bản clone đã `pip install -e` (có `pyproject.toml` cạnh package); đặt
`VOICE_STUDIO_REPO` để trỏ tường minh. Cài dạng wheel thì không có repo ⇒ bỏ hai tầng giữa.
`station.json` ở gốc trạm có thể khai `engine_dir`, `bgm_dir` (tương đối theo gốc trạm).

Biến cấu hình đi theo thứ tự riêng: biến môi trường thật → `<repo>/.env` (**chỉ** khi
`studio.local.json: mode = embedded`) → chưa đặt. Chế độ `separate` KHÔNG bao giờ tự nạp
`.env`: ở đó repo có thể là bản public của chính người dùng, và tự nạp một file nằm trong
repo là mở cửa cho nó. `.env` giữ ĐƯỜNG DẪN và cấu hình máy, không bao giờ giữ token —
khuôn tên biến ở `<repo>/.env.example`.
"""
import json
import os
import shutil
import warnings

LOCAL_CONFIG = "studio.local.json"
WORKSPACE = "workspace"
STATION_FILE = "station.json"
ENV_FILE = ".env"
ENV_EXAMPLE = ".env.example"
# Hợp đồng F17 — tên chế độ dùng chung với `agent-marketing-studio`, `agent-video-studio`.
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
#     `embedded`, tức là trạm đã được chốt ở `<repo>/workspace/`; để một dòng trong file đó
#     trỏ trạm đi nơi khác là tự tạo ra đúng cái "hai nguồn sự thật" mà cả bộ cài này sinh
#     ra để chặn. Trỏ trạm đi chỗ khác là việc của biến môi trường thật, hoặc của `migrate`.
_NEVER_FROM_DOTENV = frozenset({"VOICE_STUDIO_REPO", "VOICE_STATION", "OMNIVOICE_DIR"})


_warned = set()


def reset_deprecation_warnings():
    """Quên danh sách tên cũ đã cảnh báo — chỉ dùng trong test (mỗi test là một 'tiến trình')."""
    _warned.clear()


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


def default_station():
    return os.path.join(os.path.expanduser("~"), ".voice")


def has_marker(path):
    """Thư mục có phải một trạm giọng không: có station.json hoặc omnivoice/voices/."""
    return bool(path) and (os.path.isfile(os.path.join(path, STATION_FILE)) or
                           os.path.isdir(os.path.join(path, "omnivoice", "voices")))


def resolve_station():
    """-> (gốc trạm, nguồn). Nguồn ∈ VOICE_STATION · OMNIVOICE_DIR · studio.local.json ·
    workspace · default. Đọc lại mỗi lần gọi."""
    st = env("VOICE_STATION")
    if st:
        return _expand(st), "VOICE_STATION"
    eng = env("OMNIVOICE_DIR")
    if eng:
        return os.path.dirname(_expand(eng)), "OMNIVOICE_DIR"
    repo = repo_root()
    if repo:
        sp = (local_config(repo).get("station_path") or "").strip()
        if sp:
            sp = os.path.expanduser(sp)
            return (sp if os.path.isabs(sp) else os.path.abspath(os.path.join(repo, sp))), LOCAL_CONFIG
        ws = os.path.join(repo, WORKSPACE)
        if os.path.isdir(ws):
            return ws, WORKSPACE
    return default_station(), "default"


def station_dir():
    """Gốc trạm giọng theo thứ tự F17.3 (xem docstring module)."""
    return resolve_station()[0]


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
