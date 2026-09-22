"""classic.py — ALIAS giữ đường gọi cũ; mã thật ở `voice_studio.make_profile`.

Gọi mới: `voice-studio make-profile --audio … --start … --dur … --name …`. File này chỉ còn để lệnh/tài liệu cũ `python studio/classic.py …` chạy tiếp.
"""
import sys

import _env  # noqa: F401 — đưa gốc repo vào sys.path khi chạy trực tiếp từ thư mục studio/
from voice_studio.make_profile import *  # noqa: F401,F403
from voice_studio.make_profile import main

if __name__ == "__main__":
    sys.exit(main())
