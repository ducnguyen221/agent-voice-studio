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
    "FFMPEG_DIR", "VOICE_STUDIO_WORK", "VOICE_CLEAN_DIR", "HF_HOME", "HF_HUB_CACHE",
    "STUDIO_PORT", "VOICE_STUDIO_REPO",
)


@pytest.fixture(autouse=True)
def _clean_contract_env(monkeypatch, tmp_path):
    for name in CONTRACT_VARS:
        monkeypatch.delenv(name, raising=False)
    # Trạm mặc định (~/.voice) cũng không được là trạm thật của máy chạy test.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    # Bản clone đang chạy test có thể có workspace/ hoặc studio.local.json thật (chế độ
    # embedded của người phát triển) — trỏ "repo" sang một thư mục tạm rỗng.
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(tmp_path / "no-repo"))
    yield


# ── Engine GIẢ dùng chung cho test CLI / MCP / make-profile ─────────────────────────────
# torch + omnivoice giả đặt vào sys.modules; model giả sinh sóng sin ngắn, ghi lại mọi lần gọi.

import types  # noqa: E402

SR = 24000


class FakePrompt:
    def __init__(self, ref_audio=None, ref_text=None):
        self.ref_audio, self.ref_text = ref_audio, ref_text

    def save(self, path):
        with open(path, "wb") as f:
            f.write(b"fake-prompt")


class FakeModel:
    sampling_rate = SR

    def __init__(self):
        self.calls = []
        self.fail = False
        self.asr_text = ""

    def generate(self, **kw):
        import numpy as np
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("CUDA out of memory (giả)")
        n = max(1, len(kw.get("text", ""))) * 240
        t = np.arange(n, dtype="float32") / SR
        return [0.2 * np.sin(2 * np.pi * 220 * t).astype("float32")]

    def create_voice_clone_prompt(self, ref_audio=None, ref_text=None):
        return FakePrompt(ref_audio, ref_text)

    def load_asr_model(self):
        pass

    def _asr_pipe(self, data, **kw):
        return {"text": self.asr_text}


def _fake_torch():
    t = types.ModuleType("torch")
    t.float16, t.float32 = "fp16", "fp32"
    t.manual_seed = lambda s: None
    t.cuda = types.SimpleNamespace(is_available=lambda: False, manual_seed_all=lambda s: None,
                                   get_device_name=lambda i: "none")
    t.mps = types.SimpleNamespace(manual_seed=lambda s: None)
    t.backends = types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False))
    return t


@pytest.fixture
def fake_engine(monkeypatch):
    """Cài torch + omnivoice giả; trả model giả mà `engine.load()` sẽ trả về."""
    from voice_studio import engine, profiles
    model = FakeModel()
    ov = types.ModuleType("omnivoice")

    class OmniVoice:
        @classmethod
        def from_pretrained(cls, *a, **k):
            return model
    ov.OmniVoice = OmniVoice
    monkeypatch.setitem(sys.modules, "torch", _fake_torch())
    monkeypatch.setitem(sys.modules, "omnivoice", ov)
    engine.unload()
    profiles.clear_cache()
    yield model
    engine.unload()
    profiles.clear_cache()


def write_wav(path, seconds=1.0, amp=0.2):
    import numpy as np
    import soundfile as sf
    t = np.arange(int(SR * seconds), dtype="float32") / SR
    sf.write(str(path), (amp * np.sin(2 * np.pi * 180 * t)).astype("float32"), SR)
    return str(path)


@pytest.fixture
def station(tmp_path, monkeypatch):
    """Trạm giọng tạm: <st>/omnivoice/voices/ có 2 profile trung tính, chưa chọn mặc định."""
    st = tmp_path / "station"
    voices = st / "omnivoice" / "voices"
    voices.mkdir(parents=True)
    for name in ("demo", "other"):
        write_wav(voices / f"{name}.wav")
        (voices / f"{name}.txt").write_text("Đây là lời mẫu trung tính.", encoding="utf-8")
    monkeypatch.setenv("VOICE_STATION", str(st))
    from voice_studio import profiles
    profiles.set_voices_dir(None)
    profiles.clear_cache()
    return st


def last_json(text):
    """Dòng JSON cuối (không rỗng) của stdout — đúng cách bên gọi đọc hợp đồng."""
    import json
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines, "stdout rỗng — hợp đồng đòi một dòng JSON cuối"
    return json.loads(lines[-1])
