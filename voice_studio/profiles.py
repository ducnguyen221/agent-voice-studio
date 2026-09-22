"""profiles.py — kho "profile giọng" để cả một video/chương dùng MỘT giọng nhất quán.

Nguyên nhân gốc của lỗi "mỗi câu một giọng": chế độ thiết kế giọng (`instruct=...`) lấy mẫu
một người nói MỚI ở mỗi lần gọi `generate()`. Cách chữa là dựng MỘT `voice_clone_prompt`
từ một clip tham chiếu cố định rồi dùng lại cho mọi câu.

Một profile = `<voices>/<tên>.wav` (clip tham chiếu) + `<voices>/<tên>.txt` (lời của clip).
Tên bắt đầu bằng `_` là file quản lý (vd `_default.txt`), không phải profile.

Profile MẶC ĐỊNH — ba nhánh, theo thứ tự, không có tên nào viết cứng trong mã:
    1. `<voices>/_default.txt` (nếu tên trong đó còn tồn tại)
    2. biến môi trường `VOICE_DEFAULT_PROFILE` (nếu profile đó tồn tại)
    3. profile DUY NHẤT trong kho (chỉ khi kho có đúng một profile)
Không nhánh nào khớp ⇒ không có mặc định. Khi đó `ensure_default()` báo lỗi thay vì lùi
về một giọng tổng hợp ngẫu nhiên — giọng ngẫu nhiên chính là bệnh "lung tung" cần tránh.

Clone prompt có ba tầng cache, nhanh trước: RAM trong tiến trình → `<tên>.prompt.pt` cạnh
profile trên đĩa → dựng lại từ clip. Tầng đĩa làm lần gọi ĐẦU của một tiến trình mới rẻ hơn
khoảng 50 lần; nó chỉ là cache, hỏng thì im lặng dựng lại và ghi đè.

Kho giọng lấy từ `voice_studio._env.voices_dir()` (VOICES_DIR → trạm giọng), đọc lại mỗi
lần gọi; `set_voices_dir()` ghim cứng một thư mục cho cả tiến trình nếu cần.
"""
import os

from . import _env

FROZEN_SAMPLE_TEXT = (
    "Đây là giọng đọc mẫu, được dùng làm giọng mặc định nhất quán cho toàn bộ video thuyết minh.")

DEFAULT_ENV = "VOICE_DEFAULT_PROFILE"
_DEFAULT_FILE = "_default.txt"

_override_dir = None
_prompt_cache = {}          # (thư mục kho, tên) -> prompt

__all__ = [
    "VOICES_DIR", "FROZEN_SAMPLE_TEXT", "ProfileError",
    "voices_dir", "set_voices_dir", "list_profiles", "get_default", "set_default",
    "ensure_default", "get_clone_prompt", "save_profile_from_wav",
    "save_profile_from_instruct", "clear_cache",
]


class ProfileError(FileNotFoundError):
    """Không xác định được profile giọng để dùng. Là FileNotFoundError để code cũ bắt được."""


def voices_dir():
    return _override_dir or _env.voices_dir()


def set_voices_dir(path):
    """Ghim kho giọng cho cả tiến trình (None = quay lại đọc biến môi trường)."""
    global _override_dir
    _override_dir = os.path.abspath(os.path.expanduser(path)) if path else None


def __getattr__(name):
    # `VOICES_DIR` là thuộc tính "sống": code cũ đọc `profiles.VOICES_DIR` luôn thấy cấu hình hiện hành.
    if name == "VOICES_DIR":
        return voices_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def clear_cache():
    _prompt_cache.clear()


def _paths(name):
    d = voices_dir()
    return os.path.join(d, name + ".wav"), os.path.join(d, name + ".txt")


def _prompt_path(name):
    """Cache đĩa của clip prompt đã token hoá (omnivoice >= 0.2.0), nằm cạnh profile."""
    return os.path.join(voices_dir(), name + ".prompt.pt")


def _exists(name):
    return bool(name) and os.path.isfile(_paths(name)[0])


def _drop_prompt_cache(name):
    """Quên prompt của profile ở RAM *và* trên đĩa (gọi mỗi khi wav/txt của nó đổi)."""
    _prompt_cache.pop((voices_dir(), name), None)
    try:
        os.remove(_prompt_path(name))
    except OSError:
        pass


def list_profiles():
    d = voices_dir()
    if not os.path.isdir(d):
        return []
    return sorted(n[:-4] for n in os.listdir(d)
                  if n.endswith(".wav") and not n.startswith("_"))


def get_default():
    """Tên profile mặc định theo ba nhánh (xem docstring module), hoặc None."""
    f = os.path.join(voices_dir(), _DEFAULT_FILE)
    if os.path.isfile(f):
        with open(f, "r", encoding="utf-8") as fh:
            n = fh.read().strip()
        if _exists(n):
            return n
    n = (os.environ.get(DEFAULT_ENV) or "").strip()
    if _exists(n):
        return n
    names = list_profiles()
    if len(names) == 1:
        return names[0]
    return None


def set_default(name):
    if not _exists(name):
        raise FileNotFoundError(f"không có profile giọng '{name}' (thiếu {name}.wav)")
    d = voices_dir()
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, _DEFAULT_FILE), "w", encoding="utf-8") as f:
        f.write(name)
    return name


def ensure_default(model=None, instruct=None, name=None):
    """Trả một profile dùng được, KHÔNG BAO GIỜ lùi về giọng tổng hợp ngẫu nhiên.

    `name` (nếu đưa và tồn tại) thắng; sau đó là profile mặc định. `model`/`instruct` giữ
    trong chữ ký để tương thích với code cũ, không dùng.
    """
    if name:
        if _exists(name):
            return name
        raise ProfileError(f"không có profile giọng '{name}' trong {voices_dir()}")
    d = get_default()
    if d:
        return d
    names = list_profiles()
    if names:
        hint = (f"Kho có {len(names)} profile ({', '.join(names)}) nhưng chưa chọn mặc định: "
                f"ghi tên vào {os.path.join(voices_dir(), _DEFAULT_FILE)}, "
                f"hoặc đặt biến {DEFAULT_ENV}, hoặc truyền tên profile khi gọi.")
    else:
        hint = (f"Kho giọng {voices_dir()} chưa có profile nào. Tạo một profile trước "
                f"(clone từ bản ghi có sự đồng ý, hoặc đóng băng một giọng từ `instruct`), "
                f"rồi đặt {DEFAULT_ENV} nếu kho có nhiều profile.")
    raise ProfileError(hint + " Không render bằng giọng tổng hợp ngẫu nhiên.")


def save_profile_from_wav(src_wav, ref_text, name, set_as_default=True):
    """Tạo profile bằng cách clone một bản ghi thật (trộn về mono, giữ sample rate).

    Chỉ clone giọng của chính mình, hoặc người đã đồng ý.
    """
    import soundfile as sf
    if not os.path.isfile(src_wav):
        raise FileNotFoundError(src_wav)
    os.makedirs(voices_dir(), exist_ok=True)
    data, sr = sf.read(src_wav)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    wav, txt = _paths(name)
    sf.write(wav, data, sr)
    with open(txt, "w", encoding="utf-8") as f:
        f.write((ref_text or "").strip())
    _drop_prompt_cache(name)
    if set_as_default:
        set_default(name)
    return name


def save_profile_from_instruct(model, instruct, name, sample_text=None, set_as_default=True,
                               language="Vietnamese"):
    """Đóng băng MỘT giọng tổng hợp nhất quán từ `instruct` (không cần bản ghi)."""
    import soundfile as sf
    os.makedirs(voices_dir(), exist_ok=True)
    sample_text = (sample_text or FROZEN_SAMPLE_TEXT).strip()
    audio = model.generate(text=sample_text, language=language, instruct=instruct)[0]
    wav, txt = _paths(name)
    sf.write(wav, audio, model.sampling_rate)
    with open(txt, "w", encoding="utf-8") as f:
        f.write(sample_text)
    _drop_prompt_cache(name)
    if set_as_default:
        set_default(name)
    return name


def _load_cached_prompt(name, wav):
    """Prompt trên đĩa của `name`, hoặc None nếu thiếu/cũ/không đọc được.

    Cũ = clip tham chiếu (hoặc lời của nó) mới hơn cache — profile thu lại thì không bao giờ
    được phục vụ bằng prompt lỗi thời.
    """
    pt = _prompt_path(name)
    if not os.path.isfile(pt):
        return None
    try:
        cached_at = os.path.getmtime(pt)
        newest_src = os.path.getmtime(wav)
        txt = _paths(name)[1]
        if os.path.isfile(txt):
            newest_src = max(newest_src, os.path.getmtime(txt))
        if newest_src > cached_at:
            return None
        from omnivoice.models.omnivoice import VoiceClonePrompt
        return VoiceClonePrompt.load(pt)
    except Exception:
        # File hỏng, hoặc prompt ghi bởi bản omnivoice khác định dạng — dựng lại.
        return None


def get_clone_prompt(model, name=None):
    """Clone prompt dùng lại được cho profile `name` (hoặc mặc định). None nếu không có profile nào."""
    name = name or get_default()
    if not name:
        return None
    key = (voices_dir(), name)
    if key in _prompt_cache:
        return _prompt_cache[key]
    wav, txt = _paths(name)
    if not os.path.isfile(wav):
        raise FileNotFoundError(f"profile giọng '{name}' thiếu {wav}")

    prompt = _load_cached_prompt(name, wav)
    if prompt is None:
        ref_text = None
        if os.path.isfile(txt):
            with open(txt, "r", encoding="utf-8") as f:
                ref_text = f.read().strip() or None
        prompt = model.create_voice_clone_prompt(ref_audio=wav, ref_text=ref_text)
        try:    # cố gắng hết sức: kho giọng chỉ-đọc không được làm hỏng việc tổng hợp
            prompt.save(_prompt_path(name))
        except Exception:
            pass

    _prompt_cache[key] = prompt
    return prompt
