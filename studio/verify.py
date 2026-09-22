"""verify.py — ALIAS giữ đường gọi cũ; mã thật ở `voice_studio.lab.verify`.

Gọi mới: `voice-studio verify --wav clip.wav`. File này chỉ còn để lệnh/tài liệu cũ `python studio/verify.py …` chạy tiếp.
"""
import sys

import _env  # noqa: F401 — đưa gốc repo vào sys.path khi chạy trực tiếp từ thư mục studio/
from voice_studio.lab.verify import *  # noqa: F401,F403
from voice_studio.lab.verify import main

if __name__ == "__main__":
    sys.exit(main())
