"""
_env.py — MỘT nơi duy nhất quyết định engine nằm ở đâu.

Bộ script này sống trong repo, còn engine TTS và kho giọng sống trên máy người dùng.
Hai thứ đó không được phép giả định vị trí của nhau.

Thứ tự tìm engine:
    1. biến môi trường  OMNIVOICE_DIR
    2. dò lên từ thư mục hiện tại và từ vị trí script (tìm thư mục có voice_profiles.py)
    3. vài vị trí mặc định thông dụng
    4. báo lỗi kèm hướng dẫn — KHÔNG đoán bừa

Vì sao KHÔNG dùng symlink hay `pip install -e`:
    symlink trên Windows cần Developer Mode; junction thì tạo ra BẢN THỨ HAI của cùng
    một đường dẫn mã, và output sẽ rơi vào trong repo — một lệnh `git add` ẩu là đẩy
    giọng thật lên public. `pip install -e` thì trói script vào một venv cụ thể, trong
    khi nó cần chạy bằng chính venv của engine.
"""
import os
import sys

_MARKER = "voice_profiles.py"     # file nhận diện thư mục engine
_MAX_UP = 4


def _looks_like_engine(p):
    return bool(p) and os.path.isfile(os.path.join(p, _MARKER))


def _walk_up(start):
    p = os.path.abspath(start)
    for _ in range(_MAX_UP):
        if _looks_like_engine(p):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return None


def find_engine(explicit=None):
    """Trả thư mục engine, hoặc ném RuntimeError kèm hướng dẫn cụ thể."""
    for cand in (explicit, os.environ.get("OMNIVOICE_DIR")):
        if cand:
            cand = os.path.expanduser(cand)
            if _looks_like_engine(cand):
                return cand
            raise RuntimeError(
                f"OMNIVOICE_DIR trỏ tới '{cand}' nhưng ở đó không có {_MARKER}.\n"
                f"Kiểm lại đường dẫn, hoặc bỏ biến đi để tự dò."
            )

    for start in (os.getcwd(), os.path.dirname(os.path.abspath(__file__))):
        found = _walk_up(start)
        if found:
            return found

    home = os.path.expanduser("~")
    for d in ("omnivoice", ".omnivoice", os.path.join("voice", "omnivoice")):
        cand = os.path.join(home, d)
        if _looks_like_engine(cand):
            return cand

    raise RuntimeError(
        "Không tìm thấy engine OmniVoice.\n"
        "Đặt biến môi trường trỏ tới thư mục có voice_profiles.py:\n"
        "    Windows : setx OMNIVOICE_DIR \"C:\\duong\\dan\\toi\\omnivoice\"\n"
        "    macOS/Linux: export OMNIVOICE_DIR=/duong/dan/toi/omnivoice\n"
        "Xem GUIDE.md mục Cài đặt."
    )


def engine_dir():
    return find_engine()


def voices_dir(engine=None):
    """Kho giọng. Mặc định <engine>/voices; đổi được bằng VOICES_DIR."""
    v = os.environ.get("VOICES_DIR")
    if v:
        return os.path.expanduser(v)
    return os.path.join(engine or engine_dir(), "voices")


def work_dir():
    """Thư mục làm việc cho output tạm.

    Mặc định `./out` cạnh thư mục hiện tại — CỐ Ý không đặt trong repo, để output
    (audio giọng thật) không bao giờ nằm trong cây git.
    """
    w = os.environ.get("VOICE_STUDIO_WORK")
    return os.path.expanduser(w) if w else os.path.join(os.getcwd(), "out")


def bootstrap():
    """Cắm engine vào sys.path rồi trả (engine, voices). Gọi ở đầu mỗi script."""
    eng = engine_dir()
    if eng not in sys.path:
        sys.path.insert(0, eng)
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    return eng, voices_dir(eng)
