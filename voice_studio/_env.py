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

Thứ tự đầy đủ của chế độ cài hai kiểu (`--station` → biến → studio.local.json →
<repo>/workspace/ → ~/.voice) do `voice-studio init` bổ sung vào đúng file này sau.
"""
import os
import shutil
import warnings

_LEGACY = {
    "VOICE_BGM": "NEWS_BGM",
    "VOICE_BGM_VOL": "NEWS_BGM_VOL",
    "VOICE_BGM_DIR": "NEWS_BGM_DIR",
}


def env(name):
    """Đọc biến `name` (bỏ khoảng trắng; rỗng coi như chưa đặt).

    Nếu `name` có tên cũ và chỉ tên cũ được đặt: trả giá trị tên cũ + DeprecationWarning.
    """
    val = (os.environ.get(name) or "").strip()
    if val:
        return val
    old = _LEGACY.get(name)
    if old:
        oval = (os.environ.get(old) or "").strip()
        if oval:
            warnings.warn(
                f"Biến {old} đã đổi tên thành {name}; tên cũ còn đọc được một phiên bản nữa.",
                DeprecationWarning, stacklevel=3)
            return oval
    return None


def _expand(p):
    return os.path.abspath(os.path.expanduser(p))


def station_dir():
    """Gốc trạm giọng: VOICE_STATION → cha của OMNIVOICE_DIR → ~/.voice."""
    st = env("VOICE_STATION")
    if st:
        return _expand(st)
    eng = env("OMNIVOICE_DIR")
    if eng:
        return os.path.dirname(_expand(eng))
    return os.path.join(os.path.expanduser("~"), ".voice")


def engine_dir():
    """Thư mục engine (venv + voices): $VOICE_STATION/omnivoice → OMNIVOICE_DIR → ~/.voice/omnivoice."""
    st = env("VOICE_STATION")
    if st:
        return os.path.join(_expand(st), "omnivoice")
    eng = env("OMNIVOICE_DIR")
    if eng:
        return _expand(eng)
    return os.path.join(station_dir(), "omnivoice")


def voices_dir():
    """Kho profile giọng: VOICES_DIR → <engine>/voices."""
    v = env("VOICES_DIR")
    return _expand(v) if v else os.path.join(engine_dir(), "voices")


def bgm_dir():
    """Thư viện nhạc nền: VOICE_BGM_DIR (tên cũ NEWS_BGM_DIR) → $VOICE_STATION/assets/bgm."""
    d = env("VOICE_BGM_DIR")
    return _expand(d) if d else os.path.join(station_dir(), "assets", "bgm")


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
