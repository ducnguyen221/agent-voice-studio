"""mcp_server.py — đưa engine giọng cho agent AI dưới dạng tool MCP (chạy offline sau lần tải đầu).

Đăng ký với harness bằng python CỦA VENV ENGINE:

    <venv>/python -m voice_studio.mcp_server

8 tool (tên giữ nguyên như lớp bọc cũ để agent đang dùng không phải học lại):

    synthesize_speech    text → file audio (profile / mặc định; không có thì mới dùng `instruct`)
    clone_voice          text → audio theo một clip tham chiếu (một lần, không lưu profile)
    narrate_video        video câm + text → MP4 có giọng (combo với trình dựng video)
    make_voice_profile   tạo profile dùng lại được (clone bản ghi / đóng băng `instruct`)
    list_voice_profiles / set_default_voice   quản lý kho giọng
    list_voice_options   từ khoá hợp lệ cho `instruct` (agent đọc trước)
    get_status           thiết bị, model đã nạp chưa, chế độ offline

Tool là hàm Python thường ở cấp module — test gọi thẳng, không cần gói `mcp`. `build_server()`
mới import FastMCP và đăng ký chúng. Model nạp một lần, lười, ở lần tổng hợp đầu tiên.
"""
import os

from . import API_VERSION, av, compat, engine, profiles

SERVER_NAME = "omnivoice-tts"      # giữ tên cũ: cấu hình MCP hiện có của người dùng trỏ tên này
DEFAULT_INSTRUCT = "female, young adult, moderate pitch"

TOOLS = ("synthesize_speech", "clone_voice", "narrate_video", "make_voice_profile",
         "list_voice_profiles", "set_default_voice", "list_voice_options", "get_status")


def _check_profile(voice_profile):
    """Profile ĐƯỢC NÊU TÊN mà không có ⇒ báo lỗi, không lặng lẽ đổi sang giọng khác."""
    if voice_profile and voice_profile not in profiles.list_profiles():
        return f"ERROR: không có profile giọng '{voice_profile}' trong {profiles.voices_dir()}"
    return None


def synthesize_speech(text: str, output_path: str, instruct: str = DEFAULT_INSTRUCT,
                      language: str = "Vietnamese", speed: float = 1.0,
                      voice_profile: str = "") -> str:
    """Generate speech audio from text and save it locally (offline).

    Args:
        text: The text to speak. Supports non-verbal tags like [laughter].
        output_path: Where to save the audio, ending in `.wav` or `.mp3`.
        instruct: Voice-design keywords from `list_voice_options`, joined by ", ". Used ONLY when
            no voice profile applies; instruct mode samples a DIFFERENT voice on every call.
        language: Spoken-language name, e.g. "Vietnamese", "English".
        speed: Speaking-rate factor (1.0 = normal).
        voice_profile: Saved voice profile for a consistent voice. Empty = default profile,
            else fall back to `instruct`.

    Returns: the absolute path of the saved audio + duration.
    """
    err = _check_profile(voice_profile)
    if err:
        return err
    m = engine.load()
    audio = compat._synth(m, text, language, instruct, speed, voice_profile or None)
    path = engine.save(audio, output_path, m.sampling_rate)
    dur = len(audio) / m.sampling_rate
    used = voice_profile or profiles.get_default() or f"instruct:{instruct}"
    return f"OK — saved {path} ({dur:.1f}s @ {m.sampling_rate} Hz, voice: {used}, lang: {language})"


def clone_voice(text: str, output_path: str, ref_audio: str, ref_text: str = "",
                language: str = "Vietnamese", speed: float = 1.0) -> str:
    """Generate speech that matches a reference voice sample (one-off cloning, nothing saved).

    ETHICS: only clone a voice you are authorized to use. Do not impersonate real people.

    Args:
        text: Text to speak in the cloned voice.
        output_path: Save path, `.wav` or `.mp3`.
        ref_audio: Short reference audio file (the voice to mimic).
        ref_text: Transcript of ref_audio (improves quality; optional).
        language: Spoken-language name.
        speed: Speaking-rate factor.
    """
    if not os.path.isfile(ref_audio):
        return f"ERROR: ref_audio not found: {ref_audio}"
    m = engine.load()
    audio = m.generate(text=text, language=language, ref_audio=ref_audio,
                       ref_text=(ref_text or None), speed=speed)[0]
    path = engine.save(audio, output_path, m.sampling_rate)
    dur = len(audio) / m.sampling_rate
    return (f"OK — cloned -> {path} ({dur:.1f}s @ {m.sampling_rate} Hz, "
            f"ref: {os.path.basename(ref_audio)})")


def narrate_video(video_path: str, text: str, output_path: str,
                  instruct: str = DEFAULT_INSTRUCT, language: str = "Vietnamese",
                  speed: float = 1.0, mode: str = "fit", voice_profile: str = "") -> str:
    """Add an AI voiceover to a SILENT video and write a finished narrated MP4.

    Args:
        video_path: Silent input video (e.g. a rendered animation).
        text: Narration script. Supports non-verbal tags like [laughter], [breath].
        output_path: Final narrated video path (.mp4).
        instruct: Voice-design keywords, used only when no voice profile applies.
        language: Spoken-language name (default "Vietnamese").
        speed: Speaking-rate factor.
        mode: "fit" = final length max(video, voice) (hold last frame / pad silence);
            "shortest" = trim to the shorter one.
        voice_profile: Saved voice profile; empty = default profile, else `instruct`.
    """
    if not os.path.isfile(video_path):
        return f"ERROR: video_path not found: {video_path}"
    if mode not in av.MODES:
        return f"ERROR: mode must be one of {av.MODES}"
    err = _check_profile(voice_profile)
    if err:
        return err
    m = engine.load()
    audio = compat._synth(m, text, language, instruct, speed, voice_profile or None)
    out_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp_wav = out_path + ".__voice.wav"
    engine.save(audio, tmp_wav, m.sampling_rate)
    try:
        vdur = av.video_duration(video_path)
        adur = len(audio) / m.sampling_rate
        av.mux(video_path, tmp_wav, out_path, mode=mode)
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)
    used = voice_profile or profiles.get_default() or f"instruct:{instruct}"
    return (f"OK — narrated video -> {out_path} "
            f"(video {vdur:.1f}s + voice {adur:.1f}s, mode={mode}, voice: {used}, lang: {language})")


def make_voice_profile(name: str, ref_audio: str = "", ref_text: str = "",
                       instruct: str = "", set_default: bool = True) -> str:
    """Create a reusable VOICE PROFILE so every clip uses the SAME voice.

    Provide exactly one source:
      - ref_audio + ref_text: clone a RECORDING (~15-20 s of clean speech + its transcript).
        Only record/clone voices you are authorized to use.
      - instruct: FREEZE one consistent synthetic voice from design keywords.

    Args:
        name: Profile name (lowercase, dashes).
        ref_audio: Reference recording (wav/mp3/m4a). Use with ref_text.
        ref_text: Transcript of ref_audio.
        instruct: Design keywords to freeze a voice.
        set_default: Make this the default voice used when no profile is named.
    """
    if ref_audio:
        if not os.path.isfile(ref_audio):
            return f"ERROR: ref_audio not found: {ref_audio}"
        if not ref_text.strip():
            return "ERROR: ref_text (transcript of the recording) is required when cloning a recording."
        profiles.save_profile_from_wav(ref_audio, ref_text, name, set_as_default=set_default)
        src = f"cloned from recording {os.path.basename(ref_audio)}"
    elif instruct:
        profiles.save_profile_from_instruct(engine.load(), instruct, name, set_as_default=set_default)
        src = f"frozen from instruct '{instruct}'"
    else:
        return "ERROR: provide either (ref_audio + ref_text) or instruct."
    return f"OK — voice profile '{name}' created ({src}){' [default]' if set_default else ''}."


def list_voice_profiles() -> dict:
    """List saved voice profiles and which one is the current default."""
    return {"profiles": profiles.list_profiles(), "default": profiles.get_default(),
            "dir": profiles.voices_dir()}


def set_default_voice(name: str) -> str:
    """Set the default voice profile used when none is named."""
    try:
        profiles.set_default(name)
        return f"OK — default voice is now '{name}'."
    except FileNotFoundError as e:
        return f"ERROR: {e}"


def list_voice_options() -> dict:
    """Return the valid `instruct` keywords for voice design + usage notes. Call this first."""
    return {
        "valid_keywords": engine.VOICE_OPTIONS,
        "how_to_combine": 'Join chosen keywords with ", " — e.g. "female, young adult, moderate pitch".',
        "notes": [
            "Use ONLY keywords listed above; other words (e.g. 'warm', 'clear') are rejected.",
            "There is NO 'vietnamese accent' — pick gender/age/pitch; the Vietnamese sound comes "
            "from language='Vietnamese'.",
            "instruct mode gives a different voice on every call; for consistency create a voice "
            "profile (make_voice_profile) and pass voice_profile.",
            "Output: a path ending in .wav (raw) or .mp3 (compressed via ffmpeg).",
        ],
        "examples": [
            'synthesize_speech(text="Xin chào", output_path="out.mp3", voice_profile="demo")',
            'synthesize_speech(text="Hello", output_path="en.wav", '
            'instruct="male, middle-aged, british accent", language="English")',
        ],
    }


def get_status() -> dict:
    """Report runtime status: device, whether the model is loaded, sample rate, offline mode."""
    status = {"model_id": engine.MODEL_ID, "voice_studio": API_VERSION,
              "model_loaded": engine._model is not None, "device": engine.loaded_device(),
              "sample_rate": getattr(engine._model, "sampling_rate", None),
              "offline": os.environ.get("HF_HUB_OFFLINE") == "1",
              "voices_dir": profiles.voices_dir(), "default_profile": profiles.get_default()}
    try:
        status["device_available"] = engine.pick_device()
    except Exception as e:      # noqa: BLE001 — trạng thái phải trả được cả khi thiếu torch
        status["device_available"] = f"unavailable: {e}"
    return status


def build_server():
    """Tạo FastMCP server và đăng ký 8 tool (import `mcp` ở đây, không ở cấp module)."""
    from mcp.server.fastmcp import FastMCP
    server = FastMCP(SERVER_NAME)
    for name in TOOLS:
        server.tool()(globals()[name])
    return server


def main():
    build_server().run()


if __name__ == "__main__":
    main()
