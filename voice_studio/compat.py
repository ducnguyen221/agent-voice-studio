"""compat.py — tên và chữ ký CŨ của lớp bọc engine, để pipeline đang chạy đổi sang package không sửa dòng nào.

Trạm giọng cũ có một module MCP đơn khối mà các app (dựng tin, đọc truyện) import thẳng và
gọi hàm "riêng tư" của nó: `_get_model()`, `_synth(model, text, language, instruct, speed,
voice_profile)`, `_save`, `_mux`, `_mix_bgm`, `_ffmpeg_exe`, `_video_duration`,
`normalize_rms`. Shim ở trạm chỉ cần `from voice_studio.compat import *`.

Khác biệt DUY NHẤT có chủ đích so với API mới: `_synth` giữ hành vi cũ — không tìm được
profile nào thì LÙI về giọng thiết kế từ `instruct`. API mới (`engine.synth`) thì báo lỗi
thay vì lùi, vì giọng ngẫu nhiên mỗi lần gọi là đúng bệnh "mỗi câu một giọng". Code mới
dùng `voice_studio.engine`, đừng dùng module này.
"""
from . import av, engine, profiles

MODEL_ID = engine.MODEL_ID
VOICE_OPTIONS = engine.VOICE_OPTIONS
TARGET_RMS_DB = engine.TARGET_RMS_DB

__all__ = [
    "MODEL_ID", "VOICE_OPTIONS", "TARGET_RMS_DB",
    "_get_model", "_synth", "_save", "_mux", "_mix_bgm", "_ffmpeg_exe", "_video_duration",
    "normalize_rms",
]


def __getattr__(name):
    # `_model` cũ là biến toàn cục của module; đọc nó phải thấy model đang nạp thật.
    if name == "_model":
        return engine._model
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get_model():
    return engine.load()


def _synth(model, text, language, instruct, speed, voice_profile=None):
    """Chữ ký cũ: một clip; profile (hoặc mặc định) nếu có, không thì lùi về `instruct`."""
    try:
        prompt = profiles.get_clone_prompt(model, voice_profile)
    except Exception:
        prompt = None
    if prompt is not None:
        return model.generate(text=text, language=language, voice_clone_prompt=prompt,
                              speed=speed)[0]
    return model.generate(text=text, language=language, instruct=instruct, speed=speed)[0]


def normalize_rms(a, target_db=None, peak_ceil=0.97):
    return engine.normalize(a, target_db=target_db, peak_ceil=peak_ceil)


def _save(audio, out_path, sr):
    return engine.save(audio, out_path, sr)


def _ffmpeg_exe():
    return av.ffmpeg_exe()


def _video_duration(path):
    return av.video_duration(path)


def _mux(video_path, voice_wav, out_path, mode="fit"):
    av.mux(video_path, voice_wav, out_path, mode=mode)


def _mix_bgm(path):
    av.mix_bgm(path)
