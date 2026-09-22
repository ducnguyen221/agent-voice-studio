"""split.py — ALIAS giữ đường gọi cũ; mã thật ở `voice_studio.lab.split`.

Gọi mới: `voice-studio lab split …`. File này chỉ còn để lệnh/tài liệu cũ `python studio/split.py …` chạy tiếp.
"""
import sys

import _env  # noqa: F401 — đưa gốc repo vào sys.path khi chạy trực tiếp từ thư mục studio/
from voice_studio.lab.split import *  # noqa: F401,F403
from voice_studio.lab.split import main

if __name__ == "__main__":
    sys.exit(main())
