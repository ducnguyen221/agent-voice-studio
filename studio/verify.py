"""
verify.py — cổng kiểm tự động cho clip mẫu (DESIGN.md mục 9).

Không có người ngồi nghe duyệt, nên máy phải tự nghe: dựng thử prompt từ clip, sinh 2 câu
chuẩn, ASR ngược lại, rồi chấm. Clip mẫu hỏng thì HỎNG MỌI THỨ sinh ra từ nó — bắt ở đây
rẻ hơn bắt ở sản phẩm cuối rất nhiều.

Dùng như thư viện (build.py gọi) hoặc chạy trực tiếp để soi một clip:
  python verify.py --wav clip.wav
"""
import argparse
import os
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from _env import bootstrap
# Engine song tren may nguoi dung, khong nam trong repo -> khong duoc doan vi tri.
OMNI_DIR, VOICES = bootstrap()

import numpy as np
import soundfile as sf

PEAK_MAX_DB = -0.5     # cao hơn -> nghi clipping
RMS_MIN_DB = -34.0     # thấp hơn -> quá nhỏ
F0_FAIL_MAX = 0.35     # tỉ lệ frame mất cao độ -> nghi còn nhạc / hai người nói chồng
MIN_WORDS = 8
CER_MAX = 0.25
TAIL_WIN = 0.25        # xét 250 ms cuối clip
TAIL_QUIET_DB = 18.0   # đuôi phải thấp hơn RMS toàn clip ít nhất ngần này

PROBES = [
    "Xin chào, đây là bản kiểm tra giọng đọc.",
    "Hôm nay chúng ta bắt đầu với một con số đáng chú ý.",
]


def _fold(s):
    """Bỏ dấu thanh + hạ chữ thường — ASR hay sai dấu, so khớp lỏng cho công bằng."""
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower())
                if unicodedata.category(c) != "Mn")
    return "".join(c for c in s if c.isalnum() or c.isspace())


def cer(ref, hyp):
    """Character error rate trên chuỗi đã bỏ dấu, khoảng trắng gộp."""
    a = " ".join(_fold(ref).split())
    b = " ".join(_fold(hyp).split())
    if not a:
        return 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)


def asr(model, arr, sr):
    model.load_asr_model()
    res = model._asr_pipe({"array": np.asarray(arr, dtype="float32"), "sampling_rate": sr},
                          return_timestamps=True, chunk_length_s=30)
    return (res.get("text") or "").strip()


def transcribe_file(model, wav):
    arr, sr = sf.read(wav, dtype="float32")
    if getattr(arr, "ndim", 1) > 1:
        arr = arr.mean(axis=1)
    return asr(model, arr, sr)


def check(model, wav, ref_text=None, f0_fail=None, verbose=False):
    """Chạy đủ 6 cổng. Trả (ok: bool, ref_text: str, lý_do: list[str])."""
    reasons = []
    arr, sr = sf.read(wav, dtype="float32")
    if getattr(arr, "ndim", 1) > 1:
        arr = arr.mean(axis=1)

    peak_db = 20 * np.log10(np.max(np.abs(arr)) + 1e-12)
    rms_db = 20 * np.log10(np.sqrt(np.mean(arr ** 2)) + 1e-12)
    if peak_db >= PEAK_MAX_DB:
        reasons.append(f"clipping (peak {peak_db:.1f} dB)")
    if rms_db < RMS_MIN_DB:
        reasons.append(f"quá nhỏ (RMS {rms_db:.1f} dB)")
    if f0_fail is not None and f0_fail > F0_FAIL_MAX:
        reasons.append(f"F0 hỏng {f0_fail:.0%}")

    # Đuôi clip phải im — đây mới là thứ gây stutter-leak (clip dứt giữa từ).
    # Bản đầu kiểm bằng "transcript có kết thúc bằng dấu câu không", nhưng đó là đo THÓI QUEN
    # CHẤM CÂU CỦA WHISPER chứ không phải đo clip: Whisper tiếng Việt thường bỏ dấu chấm cuối,
    # nên cổng đó loại oan cả cụm trung tính. Đo thẳng vào audio thì đúng thứ cần đo.
    ntail = max(1, int(TAIL_WIN * sr))
    if arr.size > ntail:
        tail_db = 20 * np.log10(np.sqrt(np.mean(arr[-ntail:] ** 2)) + 1e-12)
        if tail_db > rms_db - TAIL_QUIET_DB:
            reasons.append(f"đuôi không im (tail {tail_db:.1f} vs RMS {rms_db:.1f} dB)")

    if ref_text is None:
        ref_text = transcribe_file(model, wav)
    ref_text = (ref_text or "").strip()
    if len(ref_text.split()) < MIN_WORDS:
        reasons.append(f"transcript quá ngắn ({len(ref_text.split())} từ)")
    if ref_text and ref_text[-1] not in ".!?…":
        ref_text += "."   # ranh giới câu do đuôi-im bảo đảm; dấu chấm chỉ để khớp luật ref_text

    if reasons:   # hỏng phần rẻ rồi thì khỏi tốn GPU chạy round-trip
        return False, ref_text, reasons

    prompt = model.create_voice_clone_prompt(ref_audio=wav, ref_text=ref_text)
    tail = _fold(ref_text).split()
    tail = tail[-1] if tail else ""
    import torch
    for i, p in enumerate(PROBES):
        torch.manual_seed(42 + i)
        torch.cuda.manual_seed_all(42 + i)
        out = model.generate(text=p, language="Vietnamese",
                             voice_clone_prompt=prompt, normalize_text=False)[0]
        heard = asr(model, out, model.sampling_rate)
        e = cer(p, heard)
        if e > CER_MAX:
            reasons.append(f"CER {e:.2f} ('{heard[:40]}')")
        h = _fold(heard).split()
        w = _fold(p).split()
        if h and w and h[0] != w[0] and h[0] == tail:
            reasons.append(f"stutter-leak: '{h[0]}' rò vào đầu câu")
        if verbose:
            print(f"    probe{i+1} CER={e:.2f}  {heard[:60]!r}")

    return (not reasons), ref_text, reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    args = ap.parse_args()
    import mcp_server as ov
    m = ov._get_model()
    ok, text, why = check(m, args.wav, verbose=True)
    print(f"transcript: {text!r}")
    print("KẾT QUẢ:", "ĐẠT" if ok else "LOẠI — " + "; ".join(why))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
