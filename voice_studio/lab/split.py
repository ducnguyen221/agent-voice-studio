"""
split.py — tách một profile đa biến thể thành NHIỀU profile độc lập.

  voice-studio lab split --from narrator --prefix solo

Mỗi marker thành một profile lối cũ (`voices/<prefix>-<marker>.wav` + `.txt`), dùng được
ngay với mọi pipeline hiện có mà không cần biết gì về manifest hay marker.

Vì sao tách: một profile nhiều biến thể hợp khi muốn ĐỔI sắc thái GIỮA bài; nhiều profile
độc lập hợp khi muốn CHỌN một giọng cho cả bài và so sánh chúng với nhau. Hai cách không
loại trừ nhau — profile gốc vẫn nguyên, đây chỉ là bản trích ra.
"""
import argparse
import json
import os
import shutil
import sys

from .. import _env, engine, profiles


def _voices():
    """Kho giọng hiện hành — đọc lại mỗi lần, không đóng băng lúc import."""
    return profiles.voices_dir()


from . import vlab



def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True, help="Profile nguồn, vd narrator.")
    ap.add_argument("--prefix", required=True, help="Tiền tố tên profile mới, vd solo.")
    ap.add_argument("--only", nargs="*", default=[], help="Chỉ tách các marker này.")
    ap.add_argument("--force", action="store_true",
                    help="Cho phép ghi đè profile cùng tên đã tồn tại.")
    args = ap.parse_args(argv)

    prof = vlab.load_profile(args.src)
    if prof is None:
        sys.exit(f"[split] '{args.src}' không có manifest — không phải profile đa biến thể.")

    markers = args.only or list(prof["variants"])
    made, skipped = [], []

    # Kiểm TRƯỚC toàn bộ rồi mới ghi: không để tách được nửa chừng rồi mới báo lỗi.
    for m in markers:
        if m not in prof["variants"]:
            sys.exit(f"[split] '{args.src}' không có marker '{m}'. "
                     f"Có: {', '.join(prof['variants'])}")
        dst = os.path.join(_voices(), f"{args.prefix}-{m}.wav")
        if os.path.isfile(dst) and not args.force:
            sys.exit(f"[split] DỪNG: '{args.prefix}-{m}' đã tồn tại ({dst}).\n"
                     f"        Đổi --prefix, hoặc thêm --force nếu muốn đè.")

    for m in markers:
        v = prof["variants"][m]
        src_wav = os.path.join(_voices(), v["wav"].replace("/", os.sep))
        src_txt = os.path.splitext(src_wav)[0] + ".txt"
        if not os.path.isfile(src_wav):
            print(f"[split] bỏ '{m}': thiếu {src_wav}")
            skipped.append(m)
            continue
        name = f"{args.prefix}-{m}"
        shutil.copyfile(src_wav, os.path.join(_voices(), name + ".wav"))
        if os.path.isfile(src_txt):
            shutil.copyfile(src_txt, os.path.join(_voices(), name + ".txt"))
        else:
            with open(os.path.join(_voices(), name + ".txt"), "w", encoding="utf-8") as f:
                f.write(v.get("text", "").strip())
        pt = os.path.join(_voices(), name + ".prompt.pt")   # cache cũ đã lỗi thời
        if os.path.isfile(pt):
            os.remove(pt)
        made.append(name)
        print(f"[split] {name:<40} <- {os.path.basename(v['source']['file'])[:30]} "
              f"@{v['source']['start']:.1f}s")

    # Sổ tay: profile nào ra từ marker nào, để sau còn lần ngược.
    idx = {"from": args.src, "prefix": args.prefix,
           "profiles": {f"{args.prefix}-{m}": prof["variants"][m]["source"]
                        for m in markers if f"{args.prefix}-{m}" in made}}
    p = _env.lab_dir(args.src, "split-index.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

    print(f"[split] tạo {len(made)} profile. Bỏ qua: {skipped or '(không)'}")
    print(f"[split] sổ tay -> {p}")
    print(f"[split] default KHÔNG đổi, '{args.src}' giữ nguyên.")


if __name__ == "__main__":
    sys.exit(main())
