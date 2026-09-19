"""reftext_punct.py — chèn dấu ngắt vào lời (`<tên>.txt`) của profile tại ĐÚNG chỗ clip mẫu ngừng thật.

    voice-studio reftext demo other-voice            # chỉ xem đề xuất
    voice-studio reftext demo --apply                # ghi + xoá cache prompt

Vì sao cần (đo thật): clone dùng lời mẫu để căn với clip mẫu. Bốn profile đo được có clip
ngừng 8–15 lần nhưng lời chỉ có 1–5 dấu câu ⇒ mô hình học rằng cả đoạn là một hơi liền ⇒
đọc đều, ngắt bừa ("ngang cứng", "nghỉ như hết câu giữa hai chữ liền nhau").

NGUYÊN TẮC: KHÔNG đổi một chữ nào của lời mẫu — chỉ thêm dấu. Sửa chữ mà không nghe được
audio là đoán mò, đoán sai còn hại hơn để nguyên. Có kiểm cứng: chữ bị đổi ⇒ dừng.

Mốc ngắt lấy từ word-timestamp của faster-whisper (khoảng trống THẬT giữa hai từ), rồi khớp
về đúng từ trong lời mẫu bằng difflib. Cách căn theo tỉ lệ ký tự đã bị loại: nó đặt dấu vào
giữa cụm ("chúng, ta") — sai ngữ pháp còn tệ hơn không có dấu.

Phụ thuộc thêm: `faster-whisper` (chỉ cho bước đo khoảng lặng).
"""
import argparse
import difflib
import os
import re
import sys
import unicodedata

from . import contract, profiles

MIN_GAP = 0.12          # ngắn hơn mức này là nhịp tự nhiên trong cụm, không phải chỗ ngắt
LONG_GAP = 0.45         # dài hơn mức này coi như hết câu -> dấu chấm
_PUNCT = ",.;:!?"


def _norm(w):
    w = unicodedata.normalize("NFC", w.strip().lower())
    return re.sub(r"[^\w]", "", w, flags=re.UNICODE)


def whisper_gaps(wav_path):
    """-> (danh sách từ whisper [(từ, start, end)], [(chỉ_số_từ, độ_dài_gap)])."""
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(wav_path, language="vi", word_timestamps=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            words.append((w.word.strip(), w.start, w.end))
    gaps = []
    for i in range(len(words) - 1):
        g = words[i + 1][1] - words[i][2]
        if g >= MIN_GAP:
            gaps.append((i, g))
    return words, gaps


def apply_gaps(ref_text, words, gaps):
    """Đưa mốc ngắt của whisper về đúng chỉ số từ trong lời mẫu (không đổi chữ).

    Trả (lời mới, số dấu thêm, tỉ lệ khớp lời mẫu ↔ whisper).
    """
    ref = ref_text.split()
    a = [_norm(w) for w in ref]
    b = [_norm(w[0]) for w in words]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    b2a = {}
    for i, j, n in sm.get_matching_blocks():
        for k in range(n):
            b2a[j + k] = i + k
    added = 0
    for gi, g in gaps:
        ai = b2a.get(gi)
        if ai is None or ai >= len(ref) - 1:
            continue
        if ref[ai][-1] in _PUNCT:
            continue
        ref[ai] += "." if g >= LONG_GAP else ","
        added += 1
    out = " ".join(ref)
    if out and out[-1] not in _PUNCT:
        out += "."
    return out, added, sm.ratio()


def same_words(old, new):
    return [_norm(w) for w in old.split()] == [_norm(w) for w in new.split()]


def process(name, apply=False, gaps_fn=whisper_gaps):
    """Đề xuất (và ghi nếu `apply`) lời mới cho một profile. Trả dict báo cáo."""
    d = profiles.voices_dir()
    wav, txt = os.path.join(d, name + ".wav"), os.path.join(d, name + ".txt")
    if not (os.path.isfile(wav) and os.path.isfile(txt)):
        return {"profile": name, "status": "missing"}
    with open(txt, encoding="utf-8") as f:
        old = f.read().strip()
    words, gaps = gaps_fn(wav)
    new, added, ratio = apply_gaps(old, words, gaps)
    if not same_words(old, new):
        raise contract.EngineError(f"{name}: CHỮ BỊ ĐỔI — dừng, công cụ này chỉ được thêm dấu")
    nw = max(1, len(old.split()))
    rep = {"profile": name, "status": "applied" if apply else "preview", "match": round(ratio, 3),
           "pauses": len(gaps), "added": added,
           "punct_per_100w": [round(sum(old.count(c) for c in _PUNCT) / nw * 100, 1),
                              round(sum(new.count(c) for c in _PUNCT) / nw * 100, 1)],
           "new_text": new}
    if apply:
        with open(txt, "w", encoding="utf-8", newline="\n") as f:
            f.write(new + "\n")
        pt = os.path.join(d, name + ".prompt.pt")
        if os.path.isfile(pt):
            os.remove(pt)           # BẮT BUỘC: cache prompt phải dựng lại từ lời mới
        profiles.clear_cache()
    return rep


def build_parser(prog="voice-studio reftext"):
    ap = argparse.ArgumentParser(prog=prog, description="Thêm dấu ngắt vào lời mẫu theo khoảng lặng thật.")
    ap.add_argument("names", nargs="+", help="Tên profile.")
    ap.add_argument("--apply", action="store_true", help="Ghi lời mới (mặc định chỉ xem).")
    ap.add_argument("--json", action="store_true")
    return ap


def _run(args):
    reports = []
    for n in args.names:
        rep = process(n, apply=args.apply)
        reports.append(rep)
        if rep["status"] == "missing":
            contract.log(f"{n}: THIẾU FILE — bỏ qua")
            continue
        contract.log(f"=== {n} === khớp {rep['match']:.0%} | chỗ ngừng thật {rep['pauses']} | "
                     f"thêm {rep['added']} dấu | dấu/100 từ {rep['punct_per_100w'][0]} → "
                     f"{rep['punct_per_100w'][1]}")
        contract.log(f"  MỚI: {rep['new_text'][:160]}")
    return {"profiles": reports}


def main(argv=None):
    args, code = contract.parse(build_parser(), argv)
    if args is None:
        return code
    return contract.run(_run, args, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
