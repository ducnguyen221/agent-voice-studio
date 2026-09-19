"""_env.py — cầu nối cho các alias trong `studio/`: đưa gốc repo vào sys.path, rồi hỏi package.

Mọi quyết định "trạm/kho giọng/thư mục làm việc nằm ở đâu" giờ nằm ở MỘT chỗ:
`voice_studio._env` (VOICE_STATION → OMNIVOICE_DIR → ~/.voice). File này chỉ còn để các
script cũ `python studio/<tên>.py …` chạy được khi chưa `pip install` package — không giữ
logic riêng, không dò đường theo vị trí engine nữa.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from voice_studio import _env as _pkg_env  # noqa: E402


def engine_dir():
    return _pkg_env.engine_dir()


def voices_dir(engine=None):
    return _pkg_env.voices_dir()


def work_dir():
    return _pkg_env.work_dir()


def bootstrap():
    """Tương thích chữ ký cũ: trả (thư mục engine, kho giọng)."""
    return engine_dir(), voices_dir()
