"""
classic.py — dựng profile theo LỐI CŨ (một clip mẫu duy nhất), làm mốc đối chứng cho voicelab.

Đây KHÔNG phải bản sao của make_voice_from_recording.py. Nó kế thừa 3 bài học đã trả giá
của bộ cũ và thêm phần bộ cũ không có:

  (1) ASR của transformers cần ffmpeg mới decode được filename -> truyền (waveform, sr).
  (2) Clip mẫu phải mở/đóng ĐÚNG ranh giới câu, +lead-in +tail, transcript kết bằng dấu câu,
      nếu không model sẽ nối âm tiết dở dang vào đầu MỌI audio sinh ra (stutter-leak, 06/2026).
  (3) KHÔNG đụng default profile — nhiều pipeline đang pin tên giọng, đổi default là gãy dây chuyền.

Thêm mới: tự kiểm stutter-leak bằng round-trip ASR ngay sau khi dựng, thay vì đợi phát hiện
ở sản phẩm cuối.

  python classic.py --audio "recordings/talk.mp3" --start 600.16 --dur 16.92 \
                    --name demo-voice
"""
import argparse
import json
import os
import subprocess
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ASR có thể phải tải lần đầu; các lần sau đọc cache.
os.environ.setdefault("OMNIVOICE_ONLINE", "1")
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ["TRANSFORMERS_OFFLINE"] = "0"

from _env import bootstrap
# Engine song tren may nguoi dung, khong nam trong repo -> khong duoc doan vi tri.
OMNI_DIR, VOICES = bootstrap()

import numpy as np
import soundfile as sf
import mcp_server as ov
import voice_profiles as vp

LEAD_IN = 0.15   # giây im lặng chừa trước câu đầu
TAIL = 0.40      # giây im lặng chừa sau câu cuối
SR = 24000       # khớp narrator / speaker-b / speaker-c đang chạy tốt


def extract(src, start, dur, out_wav, tail=TAIL):
    """Cắt clip mẫu: mono, 24 kHz, có lead-in và tail để chống stutter-leak."""
    ss = max(0.0, start - LEAD_IN)
    tt = dur + LEAD_IN + tail
    subprocess.run(
        [ov._ffmpeg_exe(), "-y", "-v", "error", "-ss", f"{ss:.3f}", "-t", f"{tt:.3f}",
         "-i", src, "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", out_wav],
        check=True, capture_output=True)
    return out_wav


def transcribe(model, wav_path):
    """ASR trả transcript. Truyền (waveform, sr) — KHÔNG truyền path (bài học (1))."""
    model.load_asr_model()
    arr, sr = sf.read(wav_path, dtype="float32")
    if getattr(arr, "ndim", 1) > 1:
        arr = arr.mean(axis=1)
    res = model._asr_pipe({"array": arr, "sampling_rate": sr},
                          return_timestamps=True, chunk_length_s=30)
    return (res.get("text") or "").strip()


def _syllables(text):
    """Tách âm tiết tiếng Việt, bỏ dấu câu, hạ chữ thường — để so đầu/cuối."""
    clean = "".join(c if (c.isalnum() or c.isspace()) else " " for c in text)
    return [w.lower() for w in clean.split() if w]


def _fold(s):
    """Bỏ dấu thanh để so khớp lỏng (ASR hay sai dấu)."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def check_stutter_leak(model, name, ref_text):
    """Sinh thử 2 câu; nếu âm tiết đầu bản sinh trùng âm tiết cuối clip mẫu -> RÒ.

    Đây chính là con bug 06/2026: clip mẫu kết thúc giữa cụm khiến model 'nối tiếp'
    âm tiết dở dang vào đầu mọi audio sinh ra.
    """
    ref_syl = _syllables(ref_text)
    if not ref_syl:
        return True, "transcript rỗng"
    tail_syl = _fold(ref_syl[-1])

    probes = ["Xin chào, đây là bản kiểm tra giọng đọc.",
              "Hôm nay chúng ta bắt đầu với một con số đáng chú ý."]
    prompt = vp.get_clone_prompt(model, name)
    leaked = []
    import torch
    for i, p in enumerate(probes):
        # Ghim seed: không có nó thì cùng một clip lúc báo đạt lúc báo rò, và phép kiểm
        # không tái lập được thì không phải phép kiểm.
        torch.manual_seed(42 + i)
        torch.cuda.manual_seed_all(42 + i)
        audio = model.generate(text=p, language="Vietnamese",
                               voice_clone_prompt=prompt, normalize_text=False)[0]
        heard = transcribe_array(model, np.asarray(audio, dtype="float32"), model.sampling_rate)
        h = _syllables(heard)
        first = _fold(h[0]) if h else ""
        want = _fold(_syllables(p)[0])
        if first and first != want and first == tail_syl:
            leaked.append((p, heard))
    if leaked:
        return False, f"RÒ âm tiết '{ref_syl[-1]}' vào đầu bản sinh ({len(leaked)}/2 câu)"
    return True, "sạch"


def transcribe_array(model, arr, sr):
    model.load_asr_model()
    res = model._asr_pipe({"array": arr, "sampling_rate": sr},
                          return_timestamps=True, chunk_length_s=30)
    return (res.get("text") or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True, help="File ghi âm nguồn.")
    ap.add_argument("--start", type=float, required=True, help="Giây bắt đầu (ranh giới câu).")
    ap.add_argument("--dur", type=float, required=True, help="Độ dài clip (giây).")
    ap.add_argument("--name", required=True, help="Tên profile, vd demo-voice.")
    ap.add_argument("--text", default="", help="Transcript viết tay (bỏ qua ASR).")
    ap.add_argument("--tail", type=float, default=TAIL,
                    help="Đuôi im (giây). Phải NHỎ HƠN khe lặng thực sau câu cuối, "
                         "nếu không clip sẽ nuốt âm đầu câu kế tiếp.")
    args = ap.parse_args()

    if not os.path.isfile(args.audio):
        ap.error(f"không thấy file: {args.audio}")

    work = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")
    os.makedirs(work, exist_ok=True)
    src_clip = os.path.join(work, f"{args.name}_src.wav")

    print(f"[classic] cắt {args.dur:.2f}s @ {args.start:.2f}s "
          f"(+{LEAD_IN}s đầu, +{args.tail}s đuôi) ...")
    extract(args.audio, args.start, args.dur, src_clip, args.tail)

    model = ov._get_model()
    ref_text = args.text.strip()
    if not ref_text:
        print("[classic] ASR ...")
        ref_text = transcribe(model, src_clip)
    print(f"[classic] transcript: {ref_text!r}")

    # Bài học (2): transcript phải kết bằng dấu câu, nếu không -> nguy cơ stutter-leak.
    if ref_text and ref_text[-1] not in ".!?…":
        ref_text += "."
        print("[classic] (đã thêm dấu chấm cuối transcript)")

    # Bài học (3): KHÔNG đụng default.
    vp.save_profile_from_wav(src_clip, ref_text, args.name, set_as_default=False)
    print(f"[classic] đã lưu profile '{args.name}'. default vẫn là: {vp.get_default()}")

    ok, msg = check_stutter_leak(model, args.name, ref_text)
    print(f"[classic] kiểm stutter-leak: {msg}")

    meta = {"name": args.name, "method": "classic-single-clip",
            "source": {"file": os.path.basename(args.audio),
                       "start": args.start, "dur": args.dur},
            "ref_text": ref_text, "stutter_leak_ok": ok}
    with open(os.path.join(work, f"{args.name}.meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if not ok:
        # Không để profile hỏng nằm lại trong voices/: nó sẽ hiện trong list_profiles()
        # và có ngày bị ai đó (hoặc một agent) chọn dùng.
        for ext in (".wav", ".txt", ".prompt.pt"):
            f = os.path.join(vp.VOICES_DIR, args.name + ext)
            if os.path.isfile(f):
                os.rename(f, os.path.join(vp.VOICES_DIR, "_quarantine_" + args.name + ext))
        print(f"[classic] CẢNH BÁO: clip mẫu bị rò âm tiết — nên chọn mốc khác.")
        print(f"[classic] profile hỏng đã chuyển sang '_quarantine_{args.name}.*', "
              f"KHÔNG nằm trong danh sách giọng dùng được.")
        sys.exit(1)


if __name__ == "__main__":
    main()
