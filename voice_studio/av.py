"""av.py — ghép giọng đọc vào video câm và trộn nhạc nền dưới giọng, bằng ffmpeg.

    mux(video, voice_wav, out, mode="fit", bgm=None, volume=None)
    mix_bgm(path, bgm=None, volume=None) -> True nếu đã trộn
    video_duration(path) / audio_duration(path) -> giây
    ffmpeg_exe()

NHẠC NỀN — `bgm` nhận:
    None   → theo biến `VOICE_BGM` (đường dẫn file; rỗng = không trộn) — như pipeline cũ
    False  → tắt hẳn, kể cả khi biến có đặt
    đường dẫn file có thật → dùng file đó
    tên style → tra thư viện `voice_studio.bgm` (VOICE_BGM_DIR)
Âm lượng: tham số → `VOICE_BGM_VOL` → âm lượng của thư viện (nếu chọn theo style) → 0.10.
Giọng giữ nguyên âm lượng (`amix normalize=0`); nhạc lặp vô hạn nhưng bị chặn ở độ dài
giọng/video (`duration=first`). ffmpeg lỗi khi trộn ⇒ GIỮ file gốc, không để file tạm.

Tên biến cũ `NEWS_BGM`, `NEWS_BGM_VOL`, `NEWS_BGM_DIR` vẫn đọc được một phiên bản (kèm
DeprecationWarning).
"""
import os
import re
import subprocess

from . import _env

MODES = ("fit", "shortest")
DEFAULT_BGM_VOLUME = 0.10

__all__ = ["mux", "mix_bgm", "video_duration", "audio_duration", "ffmpeg_exe", "MODES"]


def ffmpeg_exe():
    """Ưu tiên ffmpeg đầy đủ của hệ thống (nhiều filter hơn); lùi về bản đóng gói (chạy offline)."""
    return _env.ffmpeg_exe()


def audio_duration(path):
    import soundfile as sf
    return sf.info(path).duration


def video_duration(path):
    """Thời lượng video (giây): ffprobe nếu có, không thì đọc dòng `Duration:` của ffmpeg."""
    ffprobe = _env.ffprobe_exe()
    if ffprobe:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nokey=1:noprint_wrappers=1", path],
                           capture_output=True, text=True)
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    r = subprocess.run([ffmpeg_exe(), "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr or "")
    if m:
        h, mn, s = m.groups()
        return int(h) * 3600 + int(mn) * 60 + float(s)
    raise RuntimeError(f"không đo được thời lượng của {path}")


def mux(video_path, voice_wav, out_path, mode="fit", bgm=None, volume=None):
    """Ghép video câm + track giọng thành `out_path` (mp4), rồi trộn nhạc nền nếu có.

    mode="fit"      → độ dài = max(video, giọng): giữ khung cuối nếu giọng dài hơn,
                      đệm im lặng nếu video dài hơn.
    mode="shortest" → cắt theo cái ngắn hơn.
    """
    if mode not in MODES:
        raise ValueError(f"mode phải là một trong {MODES}, nhận '{mode}'")
    ff = ffmpeg_exe()
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    vdur = video_duration(video_path)
    adur = audio_duration(voice_wav)
    if mode == "shortest" or abs(vdur - adur) < 0.10:
        cmd = [ff, "-y", "-i", video_path, "-i", voice_wav,
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out_path]
    elif adur > vdur:   # giọng dài hơn: giữ khung hình cuối cho khớp
        hold = adur - vdur
        cmd = [ff, "-y", "-i", video_path, "-i", voice_wav,
               "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={hold:.3f}[v]",
               "-map", "[v]", "-map", "1:a:0",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
               "-t", f"{adur:.3f}", out_path]
    else:               # video dài hơn: đệm im lặng để hoạt ảnh chạy hết
        cmd = [ff, "-y", "-i", video_path, "-i", voice_wav,
               "-filter_complex", "[1:a]apad[a]",
               "-map", "0:v:0", "-map", "[a]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-t", f"{vdur:.3f}", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    mix_bgm(out_path, bgm=bgm, volume=volume)
    return out_path


def _resolve_bgm(bgm):
    """-> (đường dẫn nhạc | None, âm lượng gợi ý của thư viện | None)."""
    if bgm is False:
        return None, None
    if bgm is None:
        return _env.env("VOICE_BGM"), None
    bgm = str(bgm).strip()
    if not bgm:
        return None, None
    if os.path.isfile(bgm):
        return bgm, None
    from . import bgm as bgm_lib
    lib = bgm_lib.library()
    return lib.path_of(lib.resolve(bgm)), lib.volume


def _volume(volume, lib_volume):
    if volume is not None:
        return float(volume)
    raw = _env.env("VOICE_BGM_VOL")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return lib_volume if lib_volume is not None else DEFAULT_BGM_VOLUME


def mix_bgm(path, bgm=None, volume=None):
    """Trộn một lớp nhạc nền lặp DƯỚI track giọng có sẵn của `path` (ghi đè tại chỗ).

    Trả True nếu đã trộn; False nếu không có nhạc, thiếu file, hoặc ffmpeg lỗi (file gốc giữ nguyên).
    """
    music, lib_volume = _resolve_bgm(bgm)
    if not music or not os.path.isfile(music) or not os.path.isfile(path):
        return False
    vol = _volume(volume, lib_volume)
    tmp = path + ".__bgm.mp4"
    cmd = [ffmpeg_exe(), "-y", "-i", path, "-stream_loop", "-1", "-i", music,
           "-filter_complex",
           f"[1:a]volume={vol:.3f}[bg];[0:a][bg]amix=inputs=2:duration=first:normalize=0[a]",
           "-map", "0:v:0", "-map", "[a]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", tmp]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
