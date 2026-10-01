"""Extra `[clone]` ghim faster-whisper + av THEO CẶP, và cặp đó CHẠY được (Mac mini 01/10/2026).

`clone = ["faster-whisper", ...]` không ghim `av` ⇒ pip kéo PyAV 19, bản đã bỏ tham số
`metadata_errors` mà `faster_whisper.audio.decode_audio` truyền: import vẫn ngon, gọi thì
`TypeError`. Hai cổng:

    · cấu hình: `pyproject.toml` khai đúng khoảng ghim (đọc bằng regex — Python 3.10 chưa có
      `tomllib`);
    · hành vi: `decode_audio` trên wav 1 giây. Chưa cài `[clone]` thì skip — trừ khi
      `VOICE_STUDIO_REQUIRE_CLONE=1` (CI job `clone-runtime` đặt), khi đó thiếu là đỏ.
"""
import os
import re
import struct
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _clone_extra():
    t = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"^clone\s*=\s*\[(.*?)\]", t, re.M | re.S)
    assert m, "pyproject.toml thiếu extra `clone`"
    return re.findall(r'"([^"]+)"', m.group(1))


def test_clone_extra_pins_faster_whisper_and_av_as_a_pair():
    goi = _clone_extra()
    assert "faster-whisper>=1.2,<1.3" in goi, goi
    assert "av>=15,<19" in goi, "PyAV 19 bỏ `metadata_errors` — trần phải <19"


def test_decode_audio_really_runs(tmp_path):
    try:
        import av
        from faster_whisper.audio import decode_audio
    except ImportError as e:
        if os.environ.get("VOICE_STUDIO_REQUIRE_CLONE") == "1":
            pytest.fail(f"VOICE_STUDIO_REQUIRE_CLONE=1 mà chưa cài [clone]: {e}")
        pytest.skip("chưa cài extra [clone]")
    f = tmp_path / "1s.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<16000h", *([0] * 16000)))
    a = decode_audio(str(f), sampling_rate=16000)
    assert 15000 <= len(a) <= 17000
    assert 15 <= int(av.__version__.split(".")[0]) < 19, av.__version__
