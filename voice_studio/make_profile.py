"""make_profile.py — tạo MỘT profile giọng dùng lại được (clip mẫu + lời của nó) cho kho giọng.

    voice-studio make-profile --name demo --audio talk.mp3 --start 600.16 --dur 16.9
    voice-studio make-profile --name demo --video clip.mp4 --start 60 --dur 20 --text "…"
    voice-studio make-profile --name demo --instruct "female, young adult, moderate pitch"

ĐẠO ĐỨC: chỉ clone giọng của chính bạn, hoặc của người đã đồng ý rõ ràng cho việc này.
Không dựng profile giả giọng người thật để mạo danh.

Ba nguồn, đúng một nguồn mỗi lần:
  --audio / --video   cắt một đoạn ghi âm thật (ffmpeg → mono 24 kHz, có lead-in + đuôi im)
  --instruct          đóng băng MỘT giọng thiết kế từ từ khoá (không cần bản ghi)

Bài học đã trả giá, giữ nguyên từ bộ cũ:
  (1) ASR của transformers cần ffmpeg mới decode được tên file ⇒ truyền (waveform, sr).
  (2) Clip mẫu phải mở/đóng ĐÚNG ranh giới câu, có lead-in + đuôi im, lời kết bằng dấu câu —
      nếu không model nối âm tiết dở dang vào đầu MỌI audio sinh ra (stutter-leak).
  (3) KHÔNG tự đổi profile mặc định — nhiều pipeline ghim tên giọng, đổi mặc định là gãy
      dây chuyền. Muốn đặt mặc định thì truyền `--set-default`.
Thêm: tự kiểm stutter-leak bằng ASR ngược ngay sau khi dựng; clip rò bị cách ly
(`_quarantine_<tên>.*`) để không lọt vào danh sách giọng dùng được.

Mã thoát theo hợp đồng `voice_studio.contract`: 0 ok · 1 engine lỗi · 2 input sai (thiếu
nguồn, clip rò âm tiết — chọn mốc khác) · 3 chưa có engine.
"""
import argparse
import json
import os
import subprocess
import unicodedata

from . import _env, contract, engine, profiles
from .contract import ContractError, log

LEAD_IN = 0.15   # giây im lặng chừa trước câu đầu
TAIL = 0.40      # giây im lặng chừa sau câu cuối
SR = 24000

PROBES = ["Xin chào, đây là bản kiểm tra giọng đọc.",
          "Hôm nay chúng ta bắt đầu với một con số đáng chú ý."]


def extract(src, out_wav, start=0.0, dur=None, tail=TAIL):
    """Cắt clip mẫu: mono, 24 kHz. Có `start` > 0 thì lùi lead-in; có `dur` thì cộng đuôi im."""
    ss = max(0.0, float(start) - LEAD_IN) if start else 0.0
    cmd = [engine.ffmpeg(), "-y", "-v", "error", "-ss", f"{ss:.3f}"]
    if dur:
        cmd += ["-t", f"{float(dur) + (float(start) - ss) + tail:.3f}"]
    cmd += ["-i", src, "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", out_wav]
    os.makedirs(os.path.dirname(os.path.abspath(out_wav)) or ".", exist_ok=True)
    subprocess.run(cmd, check=True, capture_output=True)
    return out_wav


def transcribe_array(model, arr, sr):
    """ASR của engine trên mảng mẫu — KHÔNG truyền đường dẫn (bài học 1)."""
    model.load_asr_model()
    res = model._asr_pipe({"array": arr, "sampling_rate": sr},
                          return_timestamps=True, chunk_length_s=30)
    return (res.get("text") or "").strip()


def transcribe(model, wav_path):
    import soundfile as sf
    arr, sr = sf.read(wav_path, dtype="float32")
    if getattr(arr, "ndim", 1) > 1:
        arr = arr.mean(axis=1)
    return transcribe_array(model, arr, sr)


def _syllables(text):
    clean = "".join(c if (c.isalnum() or c.isspace()) else " " for c in text)
    return [w.lower() for w in clean.split() if w]


def _fold(s):
    """Bỏ dấu thanh để so khớp lỏng (ASR hay sai dấu)."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def check_stutter_leak(model, name, ref_text):
    """Sinh thử 2 câu; âm tiết đầu bản sinh trùng âm tiết cuối clip mẫu ⇒ RÒ. Trả (ok, lời)."""
    import numpy as np
    ref_syl = _syllables(ref_text)
    if not ref_syl:
        return False, "transcript rỗng"
    tail_syl = _fold(ref_syl[-1])
    prompt = profiles.get_clone_prompt(model, name)
    leaked = []
    for i, p in enumerate(PROBES):
        # Ghim seed: không có nó thì cùng một clip lúc báo đạt lúc báo rò.
        engine.seed_all(42 + i)
        audio = model.generate(text=p, language="Vietnamese",
                               voice_clone_prompt=prompt, normalize_text=False)[0]
        heard = transcribe_array(model, np.asarray(audio, dtype="float32"), model.sampling_rate)
        h = _syllables(heard)
        first = _fold(h[0]) if h else ""
        want = _fold(_syllables(p)[0])
        if first and first != want and first == tail_syl:
            leaked.append((p, heard))
    if leaked:
        return False, f"RÒ âm tiết '{ref_syl[-1]}' vào đầu bản sinh ({len(leaked)}/{len(PROBES)} câu)"
    return True, "sạch"


def _quarantine(name):
    d = profiles.voices_dir()
    for ext in (".wav", ".txt", ".prompt.pt"):
        f = os.path.join(d, name + ext)
        if os.path.isfile(f):
            os.replace(f, os.path.join(d, "_quarantine_" + name + ext))
    profiles.clear_cache()


def build_parser(prog="voice-studio make-profile"):
    ap = argparse.ArgumentParser(
        prog=prog, description="Tạo một profile giọng dùng lại được. CHỈ clone giọng có sự đồng ý.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--audio", help="File ghi âm nguồn (wav/mp3/m4a…).")
    src.add_argument("--video", help="Lấy tiếng từ file video này.")
    src.add_argument("--instruct", help="Đóng băng một giọng thiết kế (từ khoá OmniVoice).")
    ap.add_argument("--name", required=True, help="Tên profile (chữ thường, gạch ngang).")
    ap.add_argument("--start", type=float, default=0.0, help="Giây bắt đầu (ranh giới câu).")
    ap.add_argument("--dur", type=float, default=None, help="Độ dài clip (giây); bỏ trống = tới hết.")
    ap.add_argument("--tail", type=float, default=TAIL,
                    help="Đuôi im (giây) — phải NHỎ HƠN khe lặng thật sau câu cuối.")
    ap.add_argument("--text", default="", help="Lời của clip (bỏ trống = chạy ASR).")
    ap.add_argument("--set-default", action="store_true", help="Đặt làm profile mặc định.")
    ap.add_argument("--no-check", action="store_true", help="Bỏ bước kiểm stutter-leak.")
    ap.add_argument("--json", action="store_true", help="Một dòng JSON cuối stdout.")
    return ap


def make(args):
    name = (args.name or "").strip()
    if not name or name.startswith("_") or any(c in name for c in "/\\:"):
        raise ContractError(f"tên profile không hợp lệ: '{args.name}'")
    method = "instruct" if args.instruct else "recording"
    meta = {"name": name, "method": method}

    if args.instruct:
        model = engine.load()
        profiles.save_profile_from_instruct(model, args.instruct, name,
                                            set_as_default=args.set_default)
        meta["instruct"] = args.instruct
        ok = True
    else:
        src = args.audio or args.video
        if not os.path.isfile(src):
            raise ContractError(f"không thấy file nguồn: {src}")
        clip = _env.lab_dir(name, "src.wav")
        log(f"[make-profile] cắt {args.dur or 'tới hết'}s @ {args.start:.2f}s → {clip}")
        extract(src, clip, args.start, args.dur, args.tail)
        model = None
        ref_text = (args.text or "").strip()
        if not ref_text:
            model = engine.load()
            log("[make-profile] ASR …")
            ref_text = transcribe(model, clip)
        if not ref_text:
            raise ContractError("không có lời cho clip (ASR rỗng) — truyền --text")
        if ref_text[-1] not in ".!?…":
            ref_text += "."      # bài học (2)
        profiles.save_profile_from_wav(clip, ref_text, name, set_as_default=args.set_default)
        meta.update({"source": {"file": os.path.basename(src), "start": args.start,
                                "dur": args.dur}, "ref_text": ref_text})
        ok, msg = True, "bỏ qua"
        if not args.no_check:
            model = model or engine.load()
            ok, msg = check_stutter_leak(model, name, ref_text)
        meta["stutter_leak"] = msg
        log(f"[make-profile] kiểm stutter-leak: {msg}")

    meta["stutter_leak_ok"] = ok
    os.makedirs(_env.lab_dir(name), exist_ok=True)
    with open(_env.lab_dir(name, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    if not ok:
        _quarantine(name)
        raise ContractError(f"clip mẫu bị rò âm tiết — đã cách ly '_quarantine_{name}.*'; "
                            f"chọn mốc cắt khác")
    log(f"[make-profile] đã lưu '{name}'. Mặc định: {profiles.get_default()}")
    return {"profile": name, "method": method, "default": profiles.get_default(),
            "voices_dir": profiles.voices_dir(), "ref_text": meta.get("ref_text")}


def main(argv=None):
    ap = build_parser()
    args, code = contract.parse(ap, argv)
    if args is None:
        return code
    return contract.run(make, args, as_json=args.json)


if __name__ == "__main__":
    import sys
    sys.exit(main())
