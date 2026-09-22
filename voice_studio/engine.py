"""engine.py — lõi chạy giọng quanh OmniVoice (k2-fsa): nạp model, seed, tổng hợp, ghi file, chuẩn hoá.

Hợp đồng công khai (ghim bằng `API_VERSION`):

    load(device=None)                          -> model (nạp MỘT lần mỗi tiến trình)
    pick_device(device=None)                   -> "cuda:N" | "mps" | "cpu"
    seed_all(seed)
    synth(text, prompt=None, *, language, speed, seed, instruct, model) -> (wav, sr)
    save(audio, out_path, sr)                  -> đường dẫn tuyệt đối (.wav, hoặc .mp3 qua ffmpeg)
    normalize(a, target_db=None)               -> float32 đã chuẩn RMS
    ffmpeg()                                   -> đường dẫn ffmpeg

Không import torch/omnivoice ở cấp module: `import voice_studio.engine` rẻ, chạy được trên
máy chưa cài engine (test, CI, `doctor`).

MẠNG: mặc định CHẠY OFFLINE (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) vì weights đã
nằm trong cache. Đặt `OMNIVOICE_ONLINE=1` để cho phép tải lần đầu.

THIẾT BỊ: `cuda → mps → cpu`; ép bằng tham số hoặc `OMNIVOICE_DEVICE`.

ĐỘ CHÍNH XÁC: `cuda → fp16`, `mps → fp16`, `cpu → fp32`; ép bằng `OMNIVOICE_DTYPE`
(`float16`/`float32`, hoặc `auto` = mặc định). fp16 trên CPU bị từ chối — torch chạy CPU half
bằng đường mô phỏng, chậm hơn fp32 chứ không nhanh hơn.

Vì sao mps mặc định fp16: đo trên M1 16 GB (spike 2026-09-20), khúc văn đúng cỡ pipeline thật
cắt ra, fp16 cho RTF ≈ 1,77 so với fp32 ≈ 2,31 — nhanh hơn ~23 %, và đó là khác biệt giữa một
lượt đọc dài xong lúc 05:00 hay 06:10. Chất lượng nghe của fp16 phải do người nghe duyệt, mã
này không khẳng định thay.

Trên macOS đặt sẵn (nếu chưa có) hai biến:
  · `PYTORCH_ENABLE_MPS_FALLBACK=1` — phép toán nào MPS chưa hỗ trợ (thường là phần tokenizer
    âm thanh) tự chạy trên CPU thay vì làm sập cả lượt.
  · `HF_DEACTIVATE_ASYNC_LOAD=1` — transformers 5.17 nạp weights song song gây segfault khi
    dtype là fp16 trên MPS (đo trong spike). Tắt nạp bất đồng bộ là đổi vài giây khởi động
    lấy một lượt không sập.
[chưa kiểm trên Apple Silicon thật từ máy này — số đo lấy từ spike; Windows không có MPS.]
"""
import os
import subprocess
import sys

from . import API_VERSION, _env, profiles

MODEL_ID = os.environ.get("OMNIVOICE_MODEL", "k2-fsa/OmniVoice")
DEFAULT_LANGUAGE = "Vietnamese"

# Từ khoá hợp lệ cho `instruct` (thiết kế giọng) của OmniVoice — bộ tiếng Anh.
VOICE_OPTIONS = {
    "gender": ["female", "male"],
    "age": ["child", "teenager", "young adult", "middle-aged", "elderly"],
    "pitch": ["very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch", "whisper"],
    "accent": ["american accent", "australian accent", "british accent", "canadian accent",
               "chinese accent", "indian accent", "japanese accent", "korean accent",
               "portuguese accent", "russian accent"],
}

__all__ = [
    "API_VERSION", "MODEL_ID", "VOICE_OPTIONS", "TARGET_RMS_DB",
    "apply_offline_env", "pick_device", "pick_dtype", "load", "unload", "loaded_device",
    "seed_all", "synth", "save", "normalize", "ffmpeg",
]

_model = None
_model_device = None


def apply_offline_env():
    """Mặc định offline; `OMNIVOICE_ONLINE=1` cho phép tải weights."""
    if os.environ.get("OMNIVOICE_ONLINE") != "1":
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    if sys.platform == "darwin":
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        # transformers 5.17 + fp16 trên MPS: nạp weights song song segfault (đo trong spike).
        os.environ.setdefault("HF_DEACTIVATE_ASYNC_LOAD", "1")


apply_offline_env()


def _mps_available(torch):
    mps = getattr(getattr(torch, "backends", None), "mps", None)
    try:
        return bool(mps is not None and mps.is_available())
    except Exception:
        return False


def pick_device(device=None):
    """Chọn thiết bị: tham số → `OMNIVOICE_DEVICE` → cuda → mps → cpu.

    Ép một thiết bị không có trên máy ⇒ RuntimeError (không lặng lẽ lùi về CPU chậm gấp chục lần).
    """
    import torch
    want = (device or os.environ.get("OMNIVOICE_DEVICE") or "").strip().lower()
    if want:
        kind = want.split(":", 1)[0]
        if kind not in ("cuda", "mps", "cpu"):
            raise ValueError(f"thiết bị không hợp lệ '{want}' — chỉ nhận cuda[:N], mps, cpu")
        if kind == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError(f"đã ép '{want}' nhưng máy không có CUDA")
            return want if ":" in want else "cuda:0"
        if kind == "mps" and not _mps_available(torch):
            raise RuntimeError("đã ép 'mps' nhưng máy không có MPS (Apple Silicon)")
        return kind
    if torch.cuda.is_available():
        return "cuda:0"
    if _mps_available(torch):
        return "mps"
    return "cpu"


_DTYPE_ALIASES = {
    "float16": "float16", "fp16": "float16", "half": "float16",
    "float32": "float32", "fp32": "float32", "float": "float32", "full": "float32",
}


def pick_dtype(device, dtype=None):
    """Chọn độ chính xác cho thiết bị: tham số → `OMNIVOICE_DTYPE` → mặc định theo thiết bị.

    Mặc định: `cuda`/`mps` → float16, `cpu` → float32.
    Trả về **tên** kiểu (chuỗi) chứ không phải đối tượng torch, để gọi được khi chưa có torch.
    """
    want = (dtype or os.environ.get("OMNIVOICE_DTYPE") or "").strip().lower()
    kind = (device or "cpu").split(":", 1)[0]
    if want and want != "auto":
        name = _DTYPE_ALIASES.get(want)
        if name is None:
            raise ValueError(
                f"OMNIVOICE_DTYPE không hợp lệ '{want}' — chỉ nhận float16, float32, auto")
        if name == "float16" and kind == "cpu":
            raise RuntimeError(
                "đã ép float16 trên CPU — torch chạy CPU half bằng đường mô phỏng nên CHẬM hơn "
                "float32; bỏ OMNIVOICE_DTYPE hoặc đặt float32")
        return name
    return "float32" if kind == "cpu" else "float16"


def load(device=None):
    """Nạp model OmniVoice một lần mỗi tiến trình; gọi lại trả bản đã nạp.

    Gọi với thiết bị khác thiết bị đang nạp ⇒ nạp lại trên thiết bị mới.
    """
    global _model, _model_device
    dev = pick_device(device) if (device or _model is None) else _model_device
    if _model is not None and dev == _model_device:
        return _model
    apply_offline_env()
    import torch
    from omnivoice import OmniVoice
    dtype = getattr(torch, pick_dtype(dev))
    _model = OmniVoice.from_pretrained(MODEL_ID, device_map=dev, dtype=dtype)
    _model_device = dev
    return _model


def unload():
    """Bỏ model khỏi tiến trình (test, hoặc giải phóng VRAM giữa hai việc nặng)."""
    global _model, _model_device
    _model, _model_device = None, None


def loaded_device():
    return _model_device


def seed_all(seed):
    """Ghim seed cho mọi backend đang có.

    Engine KHÔNG tái lập nếu không ghim seed — phép so không seed là đang đo nhiễu.
    Lưu ý: cùng seed trên CUDA và MPS KHÔNG cho cùng waveform (khác kernel, khác thứ tự
    cộng dấu phẩy động). Tái lập chỉ có nghĩa trên CÙNG một loại thiết bị.
    """
    import random
    import torch
    seed = int(seed)
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed % (2 ** 32))
    except Exception:
        pass
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if _mps_available(torch) and hasattr(torch, "mps"):
        torch.mps.manual_seed(seed)


def synth(text, prompt=None, *, language=DEFAULT_LANGUAGE, speed=1.0, seed=None,
          instruct=None, model=None):
    """Tổng hợp một đoạn, trả `(wav, sample_rate)`.

    `prompt`: clone prompt đã dựng, HOẶC tên profile (chuỗi), HOẶC None.
    None + có `instruct` ⇒ chế độ thiết kế giọng (mỗi lần gọi một người nói khác — chỉ dùng
    cho thử nghiệm). None + không `instruct` ⇒ profile mặc định; không có ⇒ ProfileError.
    """
    m = model or load()
    if isinstance(prompt, str):
        prompt = profiles.get_clone_prompt(m, prompt)
    elif prompt is None and not instruct:
        prompt = profiles.get_clone_prompt(m, None)
        if prompt is None:
            profiles.ensure_default()           # ném ProfileError kèm hướng dẫn sửa
    if seed is not None:
        seed_all(seed)
    if prompt is not None:
        out = m.generate(text=text, language=language, voice_clone_prompt=prompt, speed=speed)
    else:
        out = m.generate(text=text, language=language, instruct=instruct, speed=speed)
    return out[0], m.sampling_rate


# ── CHUẨN HOÁ ÂM LƯỢNG ───────────────────────────────────────────────────────────────────
# Đo thật: cùng MỘT câu render bằng 7 profile giọng cho RMS -20.3 .. -30.2 dB = chênh 9.9 dB,
# vì mỗi clip mẫu thu ở một mức gain khác nhau. Pipeline đổi giọng theo ngày nên người nghe
# gặp đúng triệu chứng "lúc to lúc nhỏ". Chuẩn ở tầng engine để mọi app dùng chung.
# CỐ Ý chuẩn theo KHỐI (cả bài / cả chương), KHÔNG theo từng câu: chuẩn từng câu san phẳng
# chỗ to chỗ nhỏ tự nhiên của người nói = giọng đều nhưng vô hồn, đúng thứ đang tránh.
TARGET_RMS_DB = float(os.environ.get("OMNIVOICE_TARGET_RMS_DB", "-20.0"))


def normalize(a, target_db=None, peak_ceil=0.97):
    """Đưa waveform về mức RMS cố định, không bao giờ để clip. Trả mảng float32."""
    import numpy as np
    if a is None or len(a) == 0:
        return a
    target_db = TARGET_RMS_DB if target_db is None else target_db
    voiced = a[np.abs(a) > 1e-4]
    if len(voiced) < 100:               # gần như im lặng: đừng khuếch đại nhiễu nền
        return a
    cur_db = 20 * np.log10(np.sqrt((voiced ** 2).mean()) + 1e-12)
    out = a * (10 ** ((target_db - cur_db) / 20))
    peak = float(np.max(np.abs(out)))
    if peak > peak_ceil:
        out = out * (peak_ceil / peak)
    return out.astype(np.float32)


def ffmpeg():
    """ffmpeg dùng cho việc ghi mp3/ghép video (FFMPEG_DIR → PATH → imageio-ffmpeg)."""
    return _env.ffmpeg_exe()


def save(audio, out_path, sr):
    """Ghi `.wav`, hoặc chuyển sang `.mp3` nếu đường dẫn kết thúc bằng `.mp3`."""
    import soundfile as sf
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    if not out_path.lower().endswith(".mp3"):
        sf.write(out_path, audio, sr)
        return out_path
    tmp = out_path[:-4] + ".__tmp.wav"
    sf.write(tmp, audio, sr)
    # `finally`: file tạm bị bỏ lại là hàng chục MB rác mà một lệnh `git add -A` sẽ vui vẻ
    # commit — đó chính là cách một repo đã ăn object hỏng và mất hai ngày push.
    try:
        subprocess.run([ffmpeg(), "-y", "-i", tmp, "-codec:a", "libmp3lame", "-q:a", "2", out_path],
                       check=True, capture_output=True)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return out_path
