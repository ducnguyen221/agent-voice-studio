"""speak.py — ALIAS giữ đường gọi cũ; mã thật ở `voice_studio.speak`.

Gọi mới: `voice-studio speak --text … --profile … --out …`. File này chỉ còn để lệnh/tài liệu cũ `python studio/speak.py …` chạy tiếp.
"""
import sys

import _env  # noqa: F401 — đưa gốc repo vào sys.path khi chạy trực tiếp từ thư mục studio/
from voice_studio.speak import *  # noqa: F401,F403
from voice_studio.speak import main

if __name__ == "__main__":
    sys.exit(main())
