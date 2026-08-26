"""
speak.py — CLI tổng hợp giọng có marker.

  python speak.py --file intro.txt --profile demo-voice --out A.mp3
  python speak.py --text "[hao-hung] Con số này gấp ba lần!" --profile narrator --out B.mp3

Profile không có manifest thì marker bị gỡ và đọc bằng một giọng duy nhất — nhờ vậy
cùng một file kịch bản chạy được cho cả nhánh cũ lẫn nhánh voicelab, so sánh mới công bằng.
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from _env import bootstrap
# Engine song tren may nguoi dung, khong nam trong repo -> khong duoc doan vi tri.
OMNI_DIR, VOICES = bootstrap()

import mcp_server as ov
import vlab


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="Text cần đọc (có thể chứa marker).")
    g.add_argument("--file", help="File .txt chứa text cần đọc.")
    ap.add_argument("--profile", required=True, help="Tên profile.")
    ap.add_argument("--out", required=True, help="File audio ra (.wav hoặc .mp3).")
    ap.add_argument("--lang", default="Vietnamese")
    ap.add_argument("--speed", type=float, default=None,
                    help="Ép speed cho MỌI nhịp (bỏ qua speed trong manifest).")
    ap.add_argument("--seed", type=int, default=vlab.SEED,
                    help="Seed ghim để render tái lập được. -1 = chạy tự do.")
    args = ap.parse_args()

    text = args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    text = (text or "").strip()
    if not text:
        ap.error("text rỗng")

    model = ov._get_model()
    audio, sr, log = vlab.synth(model, text, args.profile, language=args.lang,
                                speed=args.speed,
                                seed=(None if args.seed < 0 else args.seed))
    if audio.size == 0:
        print("[speak] không sinh được gì.")
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    ov._save(audio, args.out, sr)
    print(f"[speak] {log['spans']} nhịp / {log['sentences']} câu, "
          f"{audio.size/sr:.2f}s -> {args.out}")


if __name__ == "__main__":
    main()
