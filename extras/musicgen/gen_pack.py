"""gen_pack.py — sinh CẢ BỘ nhạc nền theo `styles.json` rồi khai vào thư viện nhạc nền của trạm.

Mỗi style sinh một bản `<name>.mp3` vào thư viện (mặc định `VOICE_BGM_DIR` / `<trạm>/assets/bgm`)
và thêm style đó vào `bgm-library.json` — KHÔNG đè mô tả, style mặc định hay âm lượng bạn đã
chỉnh. File nhạc đã có thì bỏ qua (thêm `--force` để sinh lại).

    python extras/musicgen/gen_pack.py                       # cả bộ, model large, 30 giây/bản
    python extras/musicgen/gen_pack.py --only lofi-chill tech-pulse --seconds 45
    python extras/musicgen/gen_pack.py --styles my-styles.json --dir <thư viện>

GIẤY PHÉP weights `facebook/musicgen-*`: CC-BY-NC 4.0 — không thương mại. Xem docs/bgm-generation.md.
Mã thoát: 0 ok · 2 gọi sai · 3 thiếu torch/transformers/ffmpeg.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))          # gốc repo → voice_studio

LIBRARY_FILE = "bgm-library.json"
DEFAULT_VOLUME = 0.10


def load_styles(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["styles"]


def update_library(lib_dir, styles):
    """Thêm style mới vào `<lib_dir>/bgm-library.json`; giữ nguyên mọi thứ người dùng đã có."""
    os.makedirs(lib_dir, exist_ok=True)
    path = os.path.join(lib_dir, LIBRARY_FILE)
    data = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("volume", DEFAULT_VOLUME)
    have = data.setdefault("styles", [])
    names = {s.get("name") for s in have}
    for s in styles:
        if s["name"] not in names:
            have.append({k: v for k, v in s.items() if k in ("name", "mood", "use")})
            names.add(s["name"])
    if not data.get("default") and have:
        data["default"] = have[0]["name"]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def default_lib_dir():
    try:
        from voice_studio import _env
        return _env.bgm_dir()
    except Exception:           # noqa: BLE001
        return os.path.join(os.getcwd(), "bgm")


def build_parser():
    ap = argparse.ArgumentParser(prog="gen_pack.py", description="Sinh bộ nhạc nền theo styles.json "
                                 "và khai vào bgm-library.json (weights CC-BY-NC 4.0).")
    ap.add_argument("--styles", default=os.path.join(HERE, "styles.json"))
    ap.add_argument("--only", nargs="*", default=None, help="chỉ sinh các style này")
    ap.add_argument("--dir", default=None, help="thư viện nhạc nền (mặc định của trạm)")
    ap.add_argument("--model", default="large")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--force", action="store_true", help="sinh lại cả style đã có file")
    return ap


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return 0 if e.code in (0, None) else 2
    styles = load_styles(args.styles)
    if args.only:
        unknown = set(args.only) - {s["name"] for s in styles}
        if unknown:
            print(f"[pack] style lạ: {sorted(unknown)}", file=sys.stderr)
            return 2
        styles = [s for s in styles if s["name"] in args.only]
    lib = args.dir or default_lib_dir()
    todo = [s for s in styles if args.force or not os.path.isfile(os.path.join(lib, f"{s['name']}.mp3"))]
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import gen
    try:
        g = gen.Generator(args.model) if todo else None
    except ImportError as e:
        print(f"[pack] thiếu thư viện ({e}). Cài: pip install torch transformers soundfile",
              file=sys.stderr)
        return 3
    for s in todo:
        audio, sr = g.generate(s["prompt"], args.seconds)
        print(gen.write(audio, sr, lib, s["name"], mp3=True), flush=True)
    print(update_library(lib, styles))
    return 0


if __name__ == "__main__":
    sys.exit(main())
