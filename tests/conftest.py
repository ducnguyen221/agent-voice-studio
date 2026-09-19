"""Cấu hình chung cho test của package `voice_studio`.

Mọi test ở đây chạy KHÔNG cần model, KHÔNG cần GPU, KHÔNG cần torch: phần nặng được
thay bằng module giả. Hai việc làm chung cho mọi test:

1. Đưa gốc repo vào `sys.path` để `import voice_studio` chạy được cả khi chưa cài package.
2. Xoá sạch các biến môi trường hợp đồng trước MỖI test — máy của người chạy test có thể
   đang đặt `VOICE_STATION`, `OMNIVOICE_DIR`, `NEWS_BGM`… và test không được phép đọc
   nhầm trạm thật của máy đó.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CONTRACT_VARS = (
    "VOICE_STATION", "OMNIVOICE_DIR", "VOICES_DIR", "VOICE_DEFAULT_PROFILE",
    "OMNIVOICE_DEVICE", "OMNIVOICE_ONLINE", "OMNIVOICE_MODEL", "OMNIVOICE_TARGET_RMS_DB",
    "VOICE_BGM", "VOICE_BGM_VOL", "VOICE_BGM_DIR",
    "NEWS_BGM", "NEWS_BGM_VOL", "NEWS_BGM_DIR",
    "FFMPEG_DIR", "VOICE_STUDIO_WORK",
)


@pytest.fixture(autouse=True)
def _clean_contract_env(monkeypatch, tmp_path):
    for name in CONTRACT_VARS:
        monkeypatch.delenv(name, raising=False)
    # Trạm mặc định (~/.voice) cũng không được là trạm thật của máy chạy test.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    yield
