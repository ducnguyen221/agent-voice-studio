"""Lớp tương thích tên cũ (`compat`) + 8 tool MCP, với engine GIẢ.

`compat` là thứ shim ở trạm sẽ `import *` — chữ ký cũ phải giữ nguyên, kể cả hành vi lùi về
`instruct` khi không có profile. MCP: tool gọi thẳng như hàm; `build_server()` đăng ký đủ 8 tool.
"""
import os
import sys
import types

import pytest

from voice_studio import av, compat, engine, mcp_server, profiles

pytest.importorskip("numpy")
pytest.importorskip("soundfile")


# ── compat ─────────────────────────────────────────────────────────────────────────────

def test_compat_exports_legacy_names():
    for name in ("_get_model", "_synth", "_save", "_mux", "_mix_bgm", "_ffmpeg_exe",
                 "_video_duration", "normalize_rms"):
        assert name in compat.__all__ and callable(getattr(compat, name)), name
    assert compat.VOICE_OPTIONS is engine.VOICE_OPTIONS and compat.MODEL_ID == engine.MODEL_ID


def test_compat_synth_uses_named_profile(station, fake_engine):
    m = compat._get_model()
    assert m is fake_engine and compat._model is fake_engine
    a = compat._synth(m, "Xin chào", "Vietnamese", "female", 1.0, "demo")
    assert len(a) > 0
    assert fake_engine.calls[-1]["voice_clone_prompt"] is not None
    assert "instruct" not in fake_engine.calls[-1]


def test_compat_synth_falls_back_to_instruct_like_before(tmp_path, monkeypatch, fake_engine):
    """Hành vi CŨ có chủ đích: không profile nào ⇒ dùng instruct (API mới thì báo lỗi)."""
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "trong"))
    compat._synth(compat._get_model(), "x", "Vietnamese", "male, low pitch", 1.0, None)
    assert fake_engine.calls[-1]["instruct"] == "male, low pitch"


def test_compat_mux_and_mix_forward_to_av(monkeypatch):
    seen = []
    monkeypatch.setattr(av, "mux", lambda v, w, o, mode="fit", **k: seen.append(("mux", mode)))
    monkeypatch.setattr(av, "mix_bgm", lambda p, **k: seen.append(("mix", p)))
    compat._mux("v.mp4", "a.wav", "o.mp4", mode="shortest")
    compat._mix_bgm("o.mp4")
    assert seen == [("mux", "shortest"), ("mix", "o.mp4")]


def test_compat_normalize_rms_is_engine_normalize():
    import numpy as np
    a = (0.01 * np.ones(2000)).astype("float32")
    assert np.allclose(compat.normalize_rms(a), engine.normalize(a))


# ── MCP tools ──────────────────────────────────────────────────────────────────────────

def test_eight_tools_are_plain_documented_functions():
    assert len(mcp_server.TOOLS) == 8
    for name in mcp_server.TOOLS:
        fn = getattr(mcp_server, name)
        assert callable(fn) and (fn.__doc__ or "").strip(), name


def test_build_server_registers_all_tools(monkeypatch):
    registered = []

    class FastMCP:
        def __init__(self, name):
            self.name = name

        def tool(self):
            def deco(fn):
                registered.append(fn.__name__)
                return fn
            return deco
    pkg = types.ModuleType("mcp")
    srv = types.ModuleType("mcp.server")
    fm = types.ModuleType("mcp.server.fastmcp")
    fm.FastMCP = FastMCP
    for n, m in (("mcp", pkg), ("mcp.server", srv), ("mcp.server.fastmcp", fm)):
        monkeypatch.setitem(sys.modules, n, m)
    server = mcp_server.build_server()
    assert server.name == mcp_server.SERVER_NAME
    assert registered == list(mcp_server.TOOLS)


def test_synthesize_speech_with_profile(station, fake_engine, tmp_path):
    out = tmp_path / "a.wav"
    msg = mcp_server.synthesize_speech("Xin chào", str(out), voice_profile="demo")
    assert msg.startswith("OK") and "voice: demo" in msg and out.is_file()


def test_synthesize_speech_unknown_profile_is_error_not_other_voice(station, fake_engine, tmp_path):
    msg = mcp_server.synthesize_speech("x", str(tmp_path / "a.wav"), voice_profile="khong-co")
    assert msg.startswith("ERROR") and fake_engine.calls == []


def test_narrate_video_tool(station, fake_engine, tmp_path, monkeypatch):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"v")
    monkeypatch.setattr(av, "video_duration", lambda p: 2.0)
    monkeypatch.setattr(av, "mux", lambda v, w, o, mode="fit", **k: open(o, "wb").write(b"x"))
    msg = mcp_server.narrate_video(str(video), "x", str(tmp_path / "f.mp4"), voice_profile="demo")
    assert msg.startswith("OK — narrated") and "mode=fit" in msg
    assert not os.path.exists(str(tmp_path / "f.mp4") + ".__voice.wav")
    assert mcp_server.narrate_video(str(video), "x", "o.mp4", mode="loop").startswith("ERROR")


def test_clone_voice_tool(station, fake_engine, tmp_path):
    from conftest import write_wav
    ref = write_wav(tmp_path / "ref.wav")
    msg = mcp_server.clone_voice("x", str(tmp_path / "c.wav"), ref, "lời mẫu")
    assert msg.startswith("OK — cloned") and fake_engine.calls[-1]["ref_audio"] == ref
    assert mcp_server.clone_voice("x", "c.wav", str(tmp_path / "khong.wav")).startswith("ERROR")


def test_profile_management_tools(station, fake_engine, tmp_path):
    from conftest import write_wav
    assert mcp_server.list_voice_profiles()["profiles"] == ["demo", "other"]
    assert mcp_server.set_default_voice("khong-co").startswith("ERROR")
    assert mcp_server.set_default_voice("other").startswith("OK")
    assert mcp_server.list_voice_profiles()["default"] == "other"
    ref = write_wav(tmp_path / "moi.wav")
    assert mcp_server.make_voice_profile("moi", ref_audio=ref).startswith("ERROR")   # thiếu lời
    msg = mcp_server.make_voice_profile("moi", ref_audio=ref, ref_text="Lời.", set_default=False)
    assert msg.startswith("OK") and "moi" in profiles.list_profiles()
    assert mcp_server.make_voice_profile("frozen", instruct="female, low pitch").startswith("OK")
    assert mcp_server.make_voice_profile("rong").startswith("ERROR")


def test_options_and_status_without_torch(station, monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    opts = mcp_server.list_voice_options()
    assert set(opts["valid_keywords"]) == {"gender", "age", "pitch", "accent"}
    st = mcp_server.get_status()
    assert st["model_loaded"] is False and str(st["device_available"]).startswith("unavailable")
