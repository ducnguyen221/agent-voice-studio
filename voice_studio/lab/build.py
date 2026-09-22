"""
build.py — dựng profile đa sắc thái từ clip ứng viên đã đào (DESIGN.md mục 8).

  voice-studio lab build --name narrator --mode new
  voice-studio lab build --name speaker-b-style2 --mode add        # nạp thêm marker, không phá cũ

Chế độ `add` viết ngay từ đầu dù đợt đầu chưa cần: giọng thứ hai chắc chắn cần nạp thêm marker từ
file "Đánh Nhau" ở đợt sau, và vá về sau là đúng cái bệnh vá-đi-vá-lại.
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


import soundfile as sf
from . import verify as V
from . import vlab



def _now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def load_candidates(name):
    p = _env.lab_dir(name, "candidates.json")
    if not os.path.isfile(p):
        sys.exit(f"[build] chưa có {p} — chạy `voice-studio lab mine` trước.")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_clip(model, marker, cands, used):
    """Thử từng clip theo thứ hạng, lấy clip ĐẦU TIÊN qua đủ cổng kiểm và CHƯA bị marker
    khác lấy mất.

    Chống trùng là bắt buộc: marker âm học và marker tình huống đào trên cùng một tập cửa
    sổ, nên hoàn toàn có thể cùng chấm một đoạn. Đã gặp thật — 'cao' và
    'thuc-hanh-cong-cu-theo-script' ra đúng một clip, trùng từng byte. Hai marker khác tên
    mà phát ra y hệt nhau thì vừa tốn chỗ vừa đánh lừa người viết script.
    """
    for c in cands:
        key = (c["source"]["file"], round(c["source"]["start"], 1))
        if key in used:
            print(f"[build]   {marker} #{c['rank']}: bỏ (trùng clip của '{used[key]}')")
            continue
        ok, text, why = V.check(model, c["wav"], f0_fail=c["features"].get("f0_fail"))
        tag = "ĐẠT" if ok else "loại"
        print(f"[build]   {marker} #{c['rank']}: {tag}"
              + ("" if ok else " — " + "; ".join(why)))
        if ok:
            used[key] = marker
            return c, text
    return None, None


def stage_variant(stage, name, marker, src_wav, text):
    """Dàn clip + transcript vào thư mục STAGING, chưa đụng voices/.

    Vì sao không ghi thẳng: vòng chọn có thể chết giữa chừng (cụm trung tính trượt cả 3 clip
    -> dừng, không ghi manifest). Nếu đã ghi đè vài variant rồi mới chết thì trên đĩa các
    variant là bản MỚI còn manifest vẫn là bản CŨ — manifest nói dối, và không ai được báo.
    Dàn xong hết rồi mới commit một lượt thì không có trạng thái nửa vời.
    """
    os.makedirs(stage, exist_ok=True)
    dst = os.path.join(stage, marker + ".wav")
    shutil.copyfile(src_wav, dst)
    with open(os.path.splitext(dst)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write(text.strip())
    return f"{name}.variants/{marker}.wav"


def commit(stage, name, neutral_marker):
    """Chuyển toàn bộ staging vào voices/ — chỉ gọi khi mọi thứ đã chắc chắn."""
    vdir = os.path.join(_voices(), name + ".variants")
    os.makedirs(vdir, exist_ok=True)
    for fn in sorted(os.listdir(stage)):
        shutil.copyfile(os.path.join(stage, fn), os.path.join(vdir, fn))
        if fn.endswith(".wav"):   # prompt cache của clip vừa thay đã lỗi thời
            pt = os.path.join(vdir, fn[:-4] + ".prompt.pt")
            if os.path.isfile(pt):
                os.remove(pt)
    if neutral_marker:
        # Clip trung tính lưu THẲNG ở voices/<name>.wav để mọi pipeline chỉ biết profile phẳng đọc được.
        src = os.path.join(stage, neutral_marker + ".wav")
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(_voices(), name + ".wav"))
            shutil.copyfile(os.path.join(stage, neutral_marker + ".txt"),
                            os.path.join(_voices(), name + ".txt"))
            pt = os.path.join(_voices(), name + ".prompt.pt")
            if os.path.isfile(pt):
                os.remove(pt)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--mode", choices=["new", "add"], default="new")
    ap.add_argument("--speaker", default="")
    ap.add_argument("--force", action="store_true", help="Cho phép ghi đè marker trùng tên.")
    ap.add_argument("--reset-neutral", action="store_true",
                    help="Chế độ add: cho phép đổi luôn clip trung tính.")
    ap.add_argument("--no-demo", action="store_true")
    ap.add_argument("--overwrite-legacy", action="store_true",
                    help="Cho phép đè một profile LỐI CŨ cùng tên (nguy hiểm — xem bên dưới).")
    args = ap.parse_args(argv)

    cand = load_candidates(args.name)
    mpath = vlab.manifest_path(args.name)

    # RÀO AN TOÀN: voices/ đang chứa narrator, speaker-b, "speaker-c" — nhiều pipeline pin cứng
    # các tên này, và kho giọng thường KHÔNG nằm trong git nên đè nhầm là mất vĩnh viễn. Một profile
    # lối cũ = có <name>.wav nhưng KHÔNG có <name>.profile.json.
    legacy_wav = os.path.join(_voices(), args.name + ".wav")
    if os.path.isfile(legacy_wav) and not os.path.isfile(mpath) and not args.overwrite_legacy:
        sys.exit(f"[build] DỪNG: '{args.name}' đã tồn tại như một profile lối cũ "
                 f"({legacy_wav}) và không có manifest.\n"
                 f"        Đè lên là mất giọng đang chạy, không rollback được "
                 f"(kho giọng không có git).\n"
                 f"        Đổi --name, hoặc thêm --overwrite-legacy nếu THẬT SỰ muốn đè.")

    if args.mode == "new":
        manifest = {"name": args.name, "speaker": args.speaker or "",
                    "format_version": 1, "neutral": None, "variants": {}}
    else:
        if not os.path.isfile(mpath):
            sys.exit(f"[build] --mode add nhưng chưa có {mpath}")
        with open(mpath, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    model = engine.load()
    neutral_marker = cand.get("neutral")
    added, skipped = [], []
    stage = _env.lab_dir(args.name, "_stage")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    commit_neutral = None
    used_clips = {}   # (file, start) -> marker đã lấy, chống hai marker trùng một clip

    for marker, info in cand["clusters"].items():
        if marker in manifest["variants"] and not args.force:
            print(f"[build]   {marker}: đã có, bỏ qua (dùng --force để đè)")
            skipped.append(marker)
            continue
        if (marker in manifest["variants"] and args.force
                and marker == manifest.get("neutral") and not args.reset_neutral):
            # Đè variant trung tính mà không đụng voices/<name>.wav sẽ tạo HAI giọng nền
            # phân kỳ: vlab đọc variants/, còn nhiều pipeline cũ đọc wav gốc. Im lặng thì tệ.
            sys.exit(f"[build] DỪNG: --force sẽ đè marker trung tính '{marker}' nhưng "
                     f"voices/{args.name}.wav thì không.\n"
                     f"        Hai đường sẽ phát ra hai giọng nền khác nhau. "
                     f"Thêm --reset-neutral để đổi cả hai.")
        c, text = pick_clip(model, marker, info["candidates"], used_clips)
        if c is None:
            print(f"[build] {marker}: KHÔNG clip nào đạt -> bỏ cụm")
            skipped.append(marker)
            continue
        rel = stage_variant(stage, args.name, marker, c["wav"], text)
        manifest["variants"][marker] = {
            "wav": rel, "text": text.strip(), "speed": 1.0,
            "source": c["source"], "features": c["features"],
            "cluster_size": info["size"], "centroid_pte": info["centroid_pte"],
            "built_at": _now(),
        }
        added.append(marker)
        if marker == neutral_marker and (args.mode == "new" or args.reset_neutral
                                         or not manifest.get("neutral")):
            commit_neutral = marker
            manifest["neutral"] = marker

    if not manifest.get("neutral"):
        sys.exit("[build] không có clip trung tính nào đạt — dừng, "
                 "KHÔNG ghi gì vào voices/ (staging bị bỏ).")

    commit(stage, args.name, commit_neutral)
    shutil.rmtree(stage, ignore_errors=True)
    manifest["updated_at"] = _now()
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[build] manifest -> {mpath}")
    print(f"[build] thêm: {added or '(không)'} | bỏ qua: {skipped or '(không)'}")
    print(f"[build] trung tính: {manifest['neutral']} | tổng marker: {len(manifest['variants'])}")

    if args.no_demo:
        return

    out_dir = _env.lab_dir(args.name, "demo")
    os.makedirs(out_dir, exist_ok=True)
    sent = ("Con số này tăng gấp ba lần chỉ trong một quý, "
            "và đó là điều không ai lường trước.")

    # 1) demo từng marker: cùng một câu, nghe ra khác biệt sắc thái
    parts = []
    for marker in manifest["variants"]:
        a, sr, _ = vlab.synth(model, f"[{marker}] {sent}", args.name, verbose=False)
        parts.append((marker, a, sr))
    if parts:
        import numpy as np
        sr = parts[0][2]
        seq = []
        for marker, a, _ in parts:
            seq.append(a)
            seq.append(np.zeros(int(sr * 0.5), dtype="float32"))
        p = os.path.join(out_dir, f"{args.name}_demo-marker.mp3")
        engine.save(np.concatenate(seq), p, sr)
        print(f"[build] demo từng marker -> {p}  ({', '.join(m for m, _, _ in parts)})")

    # 2) bài kiểm tra nối: một đoạn đi qua đủ mọi marker -> nghe mối nối có vênh không
    lines = [f"[{m}] {t}" for m, t in zip(
        manifest["variants"],
        ["Ta bắt đầu bằng một câu hỏi rất đơn giản.",
         "Con số này tăng gấp ba lần chỉ trong một quý.",
         "Nhưng nếu bỏ qua bước kiểm tra, hậu quả sẽ rất lớn.",
         "Hãy nhìn kỹ vào ba chỉ số dưới đây.",
         "Và đó là toàn bộ câu chuyện của ngày hôm nay.",
         "Chúng ta sẽ quay lại chủ đề này ở phần sau.",
         "Cảm ơn bạn đã theo dõi đến cuối.",
         "Hẹn gặp lại trong số tiếp theo."])]
    a, sr, log = vlab.synth(model, " ".join(lines), args.name, verbose=False)
    p = os.path.join(out_dir, f"{args.name}_test-noi.mp3")
    engine.save(a, p, sr)
    print(f"[build] bài kiểm tra nối -> {p}  ({log['sentences']} câu)")


if __name__ == "__main__":
    sys.exit(main())
