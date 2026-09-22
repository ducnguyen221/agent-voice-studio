"""`voice-studio make-profile` (gộp dựng-từ-bản-ghi + lối classic + đóng băng instruct), `clone`, `reftext`.

ffmpeg GIẢ chép nguyên file `-i` sang file đích (đủ để soundfile đọc lại), model GIẢ có ASR giả.
"""
import os
import stat
import sys

import pytest

from conftest import last_json, write_wav
from voice_studio import clone_from_media, cli, profiles, reftext_punct

pytest.importorskip("numpy")
pytest.importorskip("soundfile")

FAKE_COPY = r'''
import shutil, sys
a = sys.argv[1:]
shutil.copyfile(a[a.index("-i") + 1], a[-1])
'''


@pytest.fixture
def copy_ffmpeg(tmp_path, monkeypatch):
    bindir = tmp_path / "ffbin"
    bindir.mkdir()
    script = bindir / "ff.py"
    script.write_text(FAKE_COPY, encoding="utf-8")
    if os.name == "nt":
        (bindir / "ffmpeg.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        sh = bindir / "ffmpeg"
        sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        sh.chmod(sh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FFMPEG_DIR", str(bindir))
    monkeypatch.setenv("VOICE_STUDIO_WORK", str(tmp_path / "work"))


def run(capsys, *argv):
    rc = cli.main(list(argv))
    out, err = capsys.readouterr()
    return rc, out, err


def test_from_recording_with_text_no_check(station, fake_engine, copy_ffmpeg, tmp_path, capsys):
    src = write_wav(tmp_path / "ghi-am.wav", seconds=2.0)
    rc, out, _ = run(capsys, "make-profile", "--audio", src, "--start", "0.5", "--dur", "1",
                     "--name", "moi", "--text", "Lời mẫu không dấu cuối", "--no-check", "--json")
    assert rc == 0, out
    res = last_json(out)
    assert res["profile"] == "moi" and res["method"] == "recording"
    vd = station / "omnivoice" / "voices"
    assert (vd / "moi.wav").is_file()
    assert (vd / "moi.txt").read_text(encoding="utf-8").endswith(".")      # bài học (2)
    assert not (vd / "_default.txt").exists()                               # bài học (3)
    assert (tmp_path / "work" / "lab" / "moi" / "meta.json").is_file()      # nháp ngoài repo


def test_set_default_is_explicit(station, fake_engine, copy_ffmpeg, tmp_path, capsys):
    src = write_wav(tmp_path / "g.wav")
    rc, _, _ = run(capsys, "make-profile", "--audio", src, "--name", "moi", "--text", "Lời.",
                   "--no-check", "--set-default")
    assert rc == 0 and profiles.get_default() == "moi"


def test_asr_fills_transcript_and_leak_check_passes(station, fake_engine, copy_ffmpeg, tmp_path, capsys):
    fake_engine.asr_text = "Xin chào đây là bản kiểm tra giọng đọc"
    src = write_wav(tmp_path / "g.wav")
    rc, out, err = run(capsys, "make-profile", "--video", src, "--name", "moi", "--json")
    assert rc == 0, err
    assert last_json(out)["ref_text"] == "Xin chào đây là bản kiểm tra giọng đọc."
    assert "sạch" in err


def test_stutter_leak_quarantines_profile(station, fake_engine, copy_ffmpeg, tmp_path, capsys):
    """ASR nghe ra âm tiết CUỐI clip mẫu ở đầu bản sinh ⇒ rò ⇒ mã 2 + cách ly, không để lọt."""
    fake_engine.asr_text = "ngay xin chào"            # clip mẫu kết thúc bằng "ngay"
    src = write_wav(tmp_path / "g.wav")
    rc, out, _ = run(capsys, "make-profile", "--audio", src, "--name", "ro",
                     "--text", "Hôm nay trời đẹp ngay", "--json")
    assert rc == 2 and "rò" in last_json(out)["error"]
    vd = station / "omnivoice" / "voices"
    assert not (vd / "ro.wav").exists() and (vd / "_quarantine_ro.wav").exists()
    assert "ro" not in profiles.list_profiles()


def test_instruct_freeze(station, fake_engine, capsys):
    rc, out, _ = run(capsys, "make-profile", "--instruct", "female, low pitch", "--name", "dong-bang",
                     "--json")
    assert rc == 0 and last_json(out)["method"] == "instruct"
    assert "dong-bang" in profiles.list_profiles()
    assert fake_engine.calls[-1]["instruct"] == "female, low pitch"


@pytest.mark.parametrize("bad", ["_an", "a/b", ""])
def test_bad_names_rejected(station, fake_engine, bad, capsys):
    rc, _, _ = run(capsys, "make-profile", "--instruct", "female", "--name", bad)
    assert rc == 2


def test_missing_source_file_is_2(station, fake_engine, capsys, tmp_path):
    rc, _, _ = run(capsys, "make-profile", "--audio", str(tmp_path / "khong.wav"), "--name", "x")
    assert rc == 2


# ── clone từ media ─────────────────────────────────────────────────────────────────────

def test_clone_requires_consent(station, capsys, tmp_path):
    src = write_wav(tmp_path / "g.wav")
    rc, out, _ = run(capsys, "clone", "--file", src, "--name", "x", "--json")
    assert rc == 2 and "--consent" in last_json(out)["error"]


def test_pick_segment_prefers_clean_then_fallback():
    long_filler = "ừ " + "a" * 90
    long_clean = "b" * 90
    texts = {60: "ngắn", 90: long_filler, 120: long_clean}
    pick = clone_from_media.pick_segment(lambda o: f"seg{int(o)}", lambda w: texts[int(w[3:])],
                                         [60, 90, 120])
    assert pick == ("seg120", long_clean)
    pick = clone_from_media.pick_segment(lambda o: f"seg{int(o)}", lambda w: texts[int(w[3:])],
                                         [60, 90])
    assert pick == ("seg90", long_filler)                       # không có đoạn sạch → lùi
    assert clone_from_media.pick_segment(lambda o: "s", lambda w: "ngắn", [1]) == (None, "")


def test_pick_segment_skips_offsets_past_the_end():
    def cut(o):
        if o > 100:
            raise RuntimeError("quá độ dài file")
        return "seg"
    assert clone_from_media.pick_segment(cut, lambda w: "c" * 90, [200, 50]) == ("seg", "c" * 90)


# ── reftext ────────────────────────────────────────────────────────────────────────────

WORDS = [("hôm", 0.0, 0.2), ("nay", 0.2, 0.4), ("chúng", 0.9, 1.1), ("ta", 1.1, 1.2),
         ("học", 1.35, 1.5), ("bài", 1.5, 1.7), ("mới", 1.7, 1.9)]


def test_apply_gaps_only_adds_punctuation():
    gaps = [(1, 0.5), (3, 0.15)]                                  # sau "nay" (dài), sau "ta" (ngắn)
    new, added, ratio = reftext_punct.apply_gaps("Hôm nay chúng ta học bài mới", WORDS, gaps)
    assert new == "Hôm nay. chúng ta, học bài mới."
    assert added == 2 and ratio == 1.0
    assert reftext_punct.same_words("Hôm nay chúng ta học bài mới", new)


def test_reftext_apply_rewrites_and_drops_prompt_cache(station):
    vd = station / "omnivoice" / "voices"
    (vd / "demo.txt").write_text("Hôm nay chúng ta học bài mới", encoding="utf-8")
    (vd / "demo.prompt.pt").write_bytes(b"cu")
    fake_gaps = lambda wav: (WORDS, [(1, 0.5)])                   # noqa: E731
    rep = reftext_punct.process("demo", apply=False, gaps_fn=fake_gaps)
    assert rep["status"] == "preview" and (vd / "demo.prompt.pt").exists()
    rep = reftext_punct.process("demo", apply=True, gaps_fn=fake_gaps)
    assert rep["status"] == "applied"
    assert (vd / "demo.txt").read_text(encoding="utf-8").strip() == "Hôm nay. chúng ta học bài mới."
    assert not (vd / "demo.prompt.pt").exists()
    assert reftext_punct.process("khong-co")["status"] == "missing"
