"""Cổng hồi quy: `engine.save()` không bao giờ để lại file tạm `.__tmp.wav`.

Sự cố thật đã trả giá: ffmpeg lỗi để lại một file tạm ~21 MB; một lệnh `git add -A`
trong pipeline commit luôn file đó, object git ghi ra bị hỏng và mọi lần push của
repo đích thất bại suốt hai ngày. Chuyển sang từ bộ test của engine gốc.
"""
import os
import shutil
import subprocess

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("soundfile")

from voice_studio import engine  # noqa: E402

SR = 16000


def test_no_tmp_leak_when_ffmpeg_fails(tmp_path, monkeypatch):
    """ffmpeg sập thì file tạm phải biến mất — và lỗi vẫn phải nổi lên."""
    audio = np.zeros(SR, dtype="float32")
    out = tmp_path / "all.mp3"
    tmp = str(out)[:-4] + ".__tmp.wav"

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "ffmpeg")

    monkeypatch.setattr(engine, "ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(engine.subprocess, "run", boom)
    with pytest.raises(subprocess.CalledProcessError):
        engine.save(audio, str(out), SR)
    assert not os.path.exists(tmp), "RÒ: .__tmp.wav còn sau khi ffmpeg lỗi"


def test_wav_written_without_ffmpeg(tmp_path, monkeypatch):
    def never(*a, **k):
        raise AssertionError("ghi .wav không được gọi ffmpeg")

    monkeypatch.setattr(engine.subprocess, "run", never)
    wav = engine.save(np.zeros(SR, dtype="float32"), str(tmp_path / "sub" / "x.wav"), SR)
    assert os.path.getsize(wav) > 0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="cần ffmpeg thật trên PATH")
def test_mp3_happy_path_cleans_temp(tmp_path):
    tone = (0.2 * np.sin(2 * np.pi * 440 * np.arange(SR) / SR)).astype("float32")
    mp3 = engine.save(tone, str(tmp_path / "all.mp3"), SR)
    assert os.path.getsize(mp3) > 0
    assert not os.path.exists(mp3[:-4] + ".__tmp.wav")
