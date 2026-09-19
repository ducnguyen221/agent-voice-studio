"""build.py — ALIAS giữ đường gọi cũ; mã thật ở `voice_studio.lab.build`.

Gọi mới: `voice-studio lab build …`. File này chỉ còn để lệnh/tài liệu cũ `python studio/build.py …` chạy tiếp.
"""
import sys

import _env  # noqa: F401 — đưa gốc repo vào sys.path khi chạy trực tiếp từ thư mục studio/
from voice_studio.lab.build import *  # noqa: F401,F403
from voice_studio.lab.build import main

if __name__ == "__main__":
    sys.exit(main())
