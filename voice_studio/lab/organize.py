"""
organize.py — sắp xếp thư mục voices/ theo từng profile, và archive file cũ.

  voice-studio lab organize --keep narrator narrator voice-b voice-c speaker-b "speaker-c"
  voice-studio lab organize --keep ... --apply      # không có --apply = chỉ xem nhấp nháy, không đụng gì

## Vì sao KHÔNG chuyển .wav vào thư mục con

`voice_studio.profiles` đọc đúng `voices/<tên>.wav` + `<tên>.txt`, và các pipeline cùng tác vụ định kỳ
thường pin cứng TÊN GIỌNG. Chuyển hai file đó vào thư mục con là gãy mọi thứ đang tiêu thụ
giọng — mà lỗi sẽ nổ lúc chạy tự động ban đêm chứ không nổ lúc mình đang ngồi trước máy.

Nên bố cục là: **hai file hợp đồng ở phẳng, mọi thứ khác vào thư mục riêng của profile.**

    voices/
        narrator.wav  .txt  .prompt.pt     <- hợp đồng với hệ cũ
        narrator/
            README.md                      <- nguồn, mốc cắt, số đo, lịch sử
            ref.wav                        <- bản sao clip mẫu (đọc/nghe không sợ đụng bản gốc)
            demo/                          <- output demo
        _archive/<ngày>/               <- file không còn dùng, KHÔNG xoá thẳng
        narrator.variants/                <- biến thể của profile đa sắc thái (giữ nguyên)

`list_profiles()` chỉ quét `*.wav` nên thư mục con không lọt vào danh sách giọng.

Archive chứ không xoá: kho giọng không nằm trong git, xoá là mất vĩnh viễn.
"""
import argparse
import datetime
import json
import os
import shutil
import sys

from .. import _env, engine, profiles


def _voices():
    """Kho giọng hiện hành — đọc lại mỗi lần, không đóng băng lúc import."""
    return profiles.voices_dir()

CONTRACT = (".wav", ".txt", ".prompt.pt")


def profile_names():
    """Tên các profile hệ cũ nhìn thấy = *.wav không bắt đầu bằng '_'."""
    return sorted(n[:-4] for n in os.listdir(_voices())
                  if n.endswith(".wav") and not n.startswith("_")
                  and os.path.isfile(os.path.join(_voices(), n)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", nargs="+", required=True, help="Profile giữ lại.")
    ap.add_argument("--apply", action="store_true", help="Thực thi (mặc định chỉ xem trước).")
    args = ap.parse_args(argv)

    keep = set(args.keep)
    stamp = datetime.date.today().isoformat()
    arch = os.path.join(_voices(), "_archive", stamp)
    dry = not args.apply
    tag = "[xem trước]" if dry else "[thực thi]"

    have = profile_names()
    missing = keep - set(have)
    if missing:
        sys.exit(f"[organize] DỪNG: không thấy profile {sorted(missing)}. "
                 f"Có: {have}")

    plan_arch, plan_dir = [], []

    # 1) profile không nằm trong --keep -> archive
    for n in have:
        if n not in keep:
            plan_arch += [n + e for e in CONTRACT
                          if os.path.isfile(os.path.join(_voices(), n + e))]

    # 2) file rác/tạm bắt đầu bằng '_' (trừ _default.txt và thư mục _archive)
    for fn in sorted(os.listdir(_voices())):
        full = os.path.join(_voices(), fn)
        if not os.path.isfile(full) or not fn.startswith("_"):
            continue
        if fn == "_default.txt":
            continue
        plan_arch.append(fn)

    # 3) thư mục riêng cho từng profile giữ lại
    for n in sorted(keep):
        plan_dir.append(n)

    print(f"[organize] {tag} archive {len(plan_arch)} file -> _archive/{stamp}/")
    for fn in plan_arch:
        print(f"           - {fn}")
    print(f"[organize] {tag} tạo {len(plan_dir)} thư mục profile")

    if dry:
        print("[organize] chưa đụng gì. Thêm --apply để thực thi.")
        return

    os.makedirs(arch, exist_ok=True)
    for fn in plan_arch:
        src = os.path.join(_voices(), fn)
        if os.path.isfile(src):
            shutil.move(src, os.path.join(arch, fn))

    for n in plan_dir:
        d = os.path.join(_voices(), n)
        os.makedirs(os.path.join(d, "demo"), exist_ok=True)
        wav = os.path.join(_voices(), n + ".wav")
        if os.path.isfile(wav):
            shutil.copyfile(wav, os.path.join(d, "ref.wav"))

    # sổ tay: ai đó (hoặc chính mình sau này) mở _archive ra phải biết vì sao nó ở đó
    with open(os.path.join(arch, "_README.md"), "w", encoding="utf-8") as f:
        f.write(f"# Archive {stamp}\n\n"
                f"File chuyển vào đây khi sắp xếp lại `voices/`.\n"
                f"Profile giữ lại lúc đó: {', '.join(sorted(keep))}\n\n"
                f"KHÔNG xoá thẳng vì kho giọng không nằm trong git — mất là mất hẳn.\n"
                f"Muốn khôi phục: chuyển ngược file `<tên>.wav` + `.txt` ra `voices/`.\n")
    with open(os.path.join(_voices(), "_layout.json"), "w", encoding="utf-8") as f:
        json.dump({"organized_at": stamp, "keep": sorted(keep),
                   "archived": plan_arch,
                   "note": "wav/txt phải ở PHẲNG — kho profile đọc voices/<tên>.wav"},
                  f, ensure_ascii=False, indent=2)
    print(f"[organize] xong. Còn lại: {profile_names()}")


if __name__ == "__main__":
    sys.exit(main())
