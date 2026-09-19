"""Test `voice_studio.av` với ffmpeg GIẢ: một script chỉ ghi lại argv và tạo file đích.

Không cần ffmpeg thật, không cần video thật. Thứ được kiểm là LỆNH — cờ nào được truyền
trong từng tình huống (giọng dài hơn video, video dài hơn giọng, có/không nhạc nền).
"""
import json
import os
import stat
import sys
import warnings

import pytest

from voice_studio import av

FAKE = r'''
import json, os, sys
with open(os.environ["FAKE_FFMPEG_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
if os.environ.get("FAKE_FFMPEG_FAIL") == "1":
    sys.exit(1)
with open(sys.argv[-1], "wb") as f:
    f.write(b"fake-output")
'''


@pytest.fixture
def fake_ffmpeg(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "fake_ffmpeg.py"
    script.write_text(FAKE, encoding="utf-8")
    if os.name == "nt":
        (bindir / "ffmpeg.cmd").write_text(
            f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        sh = bindir / "ffmpeg"
        sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        sh.chmod(sh.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "ffmpeg-calls.jsonl"
    monkeypatch.setenv("FFMPEG_DIR", str(bindir))
    monkeypatch.setenv("FAKE_FFMPEG_LOG", str(log))

    def calls():
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    return calls


@pytest.fixture
def media(tmp_path, monkeypatch):
    video = tmp_path / "in.mp4"
    voice = tmp_path / "voice.wav"
    video.write_bytes(b"v")
    voice.write_bytes(b"a")
    durations = {"video": 10.0, "audio": 10.0}
    monkeypatch.setattr(av, "video_duration", lambda p: durations["video"])
    monkeypatch.setattr(av, "audio_duration", lambda p: durations["audio"])
    return video, voice, durations, tmp_path / "out" / "final.mp4"


def _value_after(argv, flag):
    return argv[argv.index(flag) + 1]


def test_ffmpeg_dir_is_honoured(fake_ffmpeg, tmp_path):
    assert os.path.dirname(av.ffmpeg_exe()) == str(tmp_path / "bin")


def test_mux_equal_lengths_copies_video(fake_ffmpeg, media):
    video, voice, d, out = media
    av.mux(str(video), str(voice), str(out))
    (argv,) = fake_ffmpeg()
    assert _value_after(argv, "-c:v") == "copy" and "-shortest" in argv
    assert argv[-1] == str(out) and out.exists()


def test_mux_voice_longer_holds_last_frame(fake_ffmpeg, media):
    video, voice, d, out = media
    d["audio"] = 12.0
    av.mux(str(video), str(voice), str(out))
    (argv,) = fake_ffmpeg()
    assert "tpad=stop_mode=clone:stop_duration=2.000" in _value_after(argv, "-filter_complex")
    assert _value_after(argv, "-c:v") == "libx264"
    assert _value_after(argv, "-t") == "12.000"


def test_mux_video_longer_pads_silence(fake_ffmpeg, media):
    video, voice, d, out = media
    d["video"] = 15.0
    av.mux(str(video), str(voice), str(out))
    (argv,) = fake_ffmpeg()
    assert "apad" in _value_after(argv, "-filter_complex")
    assert _value_after(argv, "-t") == "15.000"


def test_mux_shortest_mode(fake_ffmpeg, media):
    video, voice, d, out = media
    d["video"] = 15.0
    av.mux(str(video), str(voice), str(out), mode="shortest")
    (argv,) = fake_ffmpeg()
    assert "-shortest" in argv and "-filter_complex" not in argv


def test_mux_rejects_unknown_mode(fake_ffmpeg, media):
    video, voice, d, out = media
    with pytest.raises(ValueError):
        av.mux(str(video), str(voice), str(out), mode="stretch")


def test_no_bgm_by_default(fake_ffmpeg, media):
    video, voice, d, out = media
    av.mux(str(video), str(voice), str(out))
    assert len(fake_ffmpeg()) == 1


def test_bgm_from_voice_bgm_env(fake_ffmpeg, media, tmp_path, monkeypatch):
    video, voice, d, out = media
    music = tmp_path / "bed.mp3"
    music.write_bytes(b"m")
    monkeypatch.setenv("VOICE_BGM", str(music))
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)      # tên mới: không cảnh báo
        av.mux(str(video), str(voice), str(out))
    mux_call, bgm_call = fake_ffmpeg()
    assert _value_after(bgm_call, "-stream_loop") == "-1"
    assert str(music) in bgm_call
    fc = _value_after(bgm_call, "-filter_complex")
    assert "volume=0.100" in fc and "amix=inputs=2:duration=first:normalize=0" in fc
    assert out.read_bytes() == b"fake-output"
    assert not os.path.exists(str(out) + ".__bgm.mp4")


def test_bgm_volume_env(fake_ffmpeg, media, tmp_path, monkeypatch):
    video, voice, d, out = media
    music = tmp_path / "bed.mp3"
    music.write_bytes(b"m")
    monkeypatch.setenv("VOICE_BGM", str(music))
    monkeypatch.setenv("VOICE_BGM_VOL", "0.25")
    av.mux(str(video), str(voice), str(out))
    assert "volume=0.250" in _value_after(fake_ffmpeg()[1], "-filter_complex")


def test_legacy_news_bgm_warns_but_still_works(fake_ffmpeg, media, tmp_path, monkeypatch):
    video, voice, d, out = media
    music = tmp_path / "bed.mp3"
    music.write_bytes(b"m")
    monkeypatch.setenv("NEWS_BGM", str(music))
    monkeypatch.setenv("NEWS_BGM_VOL", "0.3")
    with pytest.warns(DeprecationWarning, match="VOICE_BGM"):
        av.mux(str(video), str(voice), str(out))
    bgm_call = fake_ffmpeg()[1]
    assert str(music) in bgm_call
    assert "volume=0.300" in _value_after(bgm_call, "-filter_complex")


def test_legacy_news_bgm_dir_with_style(fake_ffmpeg, media, tmp_path, monkeypatch):
    video, voice, d, out = media
    lib = tmp_path / "legacy-bgm"
    lib.mkdir()
    (lib / "calm.mp3").write_bytes(b"m")
    (lib / "bgm-library.json").write_text(json.dumps(
        {"volume": 0.1, "default": "calm", "styles": [{"name": "calm"}]}), encoding="utf-8")
    monkeypatch.setenv("NEWS_BGM_DIR", str(lib))
    with pytest.warns(DeprecationWarning, match="VOICE_BGM_DIR"):
        av.mux(str(video), str(voice), str(out), bgm="calm")
    assert str(lib / "calm.mp3") in fake_ffmpeg()[1]


def test_explicit_bgm_beats_env_and_none_disables(fake_ffmpeg, media, tmp_path, monkeypatch):
    video, voice, d, out = media
    env_music, arg_music = tmp_path / "env.mp3", tmp_path / "arg.mp3"
    env_music.write_bytes(b"m")
    arg_music.write_bytes(b"m")
    monkeypatch.setenv("VOICE_BGM", str(env_music))
    av.mux(str(video), str(voice), str(out), bgm=str(arg_music))
    assert str(arg_music) in fake_ffmpeg()[1]
    av.mux(str(video), str(voice), str(out), bgm=False)          # tắt hẳn dù env có đặt
    assert len(fake_ffmpeg()) == 3


def test_bgm_failure_keeps_original_and_no_temp(fake_ffmpeg, tmp_path, monkeypatch):
    target = tmp_path / "final.mp4"
    target.write_bytes(b"original")
    music = tmp_path / "bed.mp3"
    music.write_bytes(b"m")
    monkeypatch.setenv("FAKE_FFMPEG_FAIL", "1")
    assert av.mix_bgm(str(target), bgm=str(music)) is False
    assert target.read_bytes() == b"original"
    assert not os.path.exists(str(target) + ".__bgm.mp4")
