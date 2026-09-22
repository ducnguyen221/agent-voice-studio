"""speak.py — `voice-studio speak`: text → một file audio, theo hợp đồng gọi giữa các trạm.

    voice-studio speak --text "Xin chào" --profile demo --out a.wav --json
    voice-studio speak --file script.txt --out bai.mp3 --seed 42 --normalize --json

Đây là lệnh ỔN ĐỊNH mà pipeline khác gọi (một lần mỗi bài). Script đọc hàng trăm câu thì
đừng gọi CLI từng câu — `import voice_studio` trong cùng venv để model chỉ nạp một lần.

- Profile: `--profile` → profile mặc định của kho. Không có ⇒ mã 2 (không bao giờ lùi về
  giọng ngẫu nhiên). `--instruct` là chế độ thiết kế giọng TƯỜNG MINH, chỉ để thử.
- Text có thể chứa marker sắc thái `[tên-marker]` nếu profile có manifest đa biến thể;
  profile thường thì marker bị gỡ, không bao giờ bị đọc thành tiếng.
- Cắt câu, tổng hợp từng câu, vuốt mối nối; seed ghim mặc định 42 để render tái lập được
  (`--seed -1` = chạy tự do). Tái lập chỉ có nghĩa trên CÙNG loại thiết bị.
- `--normalize`: đưa cả bài về RMS chuẩn (−20 dB) — chuẩn theo khối, không theo câu.

Kết quả (`--json`, dòng cuối stdout):
    {"ok": true, "outputs": [{"kind": "audio", "path": …, "duration": …}],
     "profile": …, "timings": {"load": …, "synth": …, "total": …},
     "engine": {"voice_studio": API_VERSION, "device": …}}
Mã thoát: 0 ok · 1 engine lỗi · 2 hợp đồng sai · 3 trạm/engine chưa cài.
"""
import argparse
import os
import time

from . import API_VERSION, contract, engine, profiles
from .contract import ContractError, StationMissing, log

DEFAULT_SEED = 42


def add_voice_args(ap):
    ap.add_argument("--profile", default=None, help="Tên profile giọng (mặc định: profile mặc định của kho).")
    ap.add_argument("--instruct", default=None,
                    help="Thiết kế giọng bằng từ khoá (mỗi lần một giọng khác — chỉ để thử).")
    ap.add_argument("--lang", default=engine.DEFAULT_LANGUAGE, help="Tên ngôn ngữ (mặc định Vietnamese).")
    ap.add_argument("--speed", type=float, default=None, help="Hệ số tốc độ (1.0 = bình thường).")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed ghim; -1 = tự do.")
    ap.add_argument("--normalize", action="store_true", help="Chuẩn RMS cả bài về −20 dB.")
    ap.add_argument("--json", action="store_true", help="Một dòng JSON kết quả cuối stdout.")


def build_parser(prog="voice-studio speak"):
    ap = argparse.ArgumentParser(prog=prog, description="Đọc text thành một file audio (.wav/.mp3).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="Text cần đọc (có thể chứa marker).")
    g.add_argument("--file", help="File UTF-8 chứa text.")
    ap.add_argument("--out", required=True, help="File audio ra (.wav hoặc .mp3).")
    add_voice_args(ap)
    return ap


def read_text(args):
    text = args.text
    if getattr(args, "file", None):
        if not os.path.isfile(args.file):
            raise ContractError(f"không thấy file text: {args.file}")
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    text = (text or "").strip()
    if not text:
        raise ContractError("text rỗng")
    return text


def resolve_profile(name, instruct=None):
    """-> tên profile dùng được, hoặc None nếu chạy chế độ `instruct`.

    Kho giọng chưa tồn tại ⇒ StationMissing (3); profile không có / không có mặc định ⇒
    ContractError (2).
    """
    d = profiles.voices_dir()
    if instruct and not name:
        return None
    if not os.path.isdir(d):
        raise StationMissing(
            f"chưa có kho giọng {d}. Dựng trạm bằng `voice-studio init` (hoặc đặt VOICE_STATION), "
            f"rồi tạo profile bằng `voice-studio make-profile`.")
    try:
        return profiles.ensure_default(name=name)
    except profiles.ProfileError as e:
        raise ContractError(str(e)) from e


def synthesize(text, profile, *, instruct=None, language=engine.DEFAULT_LANGUAGE, speed=None,
               seed=DEFAULT_SEED, normalize=False, model=None):
    """Tổng hợp cả đoạn → (wav float32, sr). Dùng chung cho `speak` và `narrate`."""
    import numpy as np
    m = model or engine.load()
    seed = None if (seed is None or seed < 0) else seed
    if profile is None:
        wav, sr = engine.synth(text, None, instruct=instruct, language=language,
                               speed=speed or 1.0, seed=seed, model=m)
        wav = np.asarray(wav, dtype="float32")
    else:
        from .lab import vlab
        wav, sr, _ = vlab.synth(m, text, profile, language=language, speed=speed, seed=seed)
    if wav is None or len(wav) == 0:
        raise contract.EngineError("engine không sinh được audio nào")
    if normalize:
        wav = engine.normalize(wav)
    return wav, sr


def speak(args):
    t0 = time.perf_counter()
    text = read_text(args)
    profile = resolve_profile(args.profile, args.instruct)
    m = engine.load()
    t1 = time.perf_counter()
    wav, sr = synthesize(text, profile, instruct=args.instruct, language=args.lang,
                         speed=args.speed, seed=args.seed, normalize=args.normalize, model=m)
    t2 = time.perf_counter()
    path = engine.save(wav, args.out, sr)
    dur = len(wav) / float(sr)
    log(f"[speak] {dur:.2f}s, giọng {profile or 'instruct:' + str(args.instruct)} → {path}")
    return {
        "outputs": [{"kind": "audio", "path": path, "duration": round(dur, 3)}],
        "profile": profile,
        "timings": {"load": round(t1 - t0, 3), "synth": round(t2 - t1, 3),
                    "total": round(time.perf_counter() - t0, 3)},
        "engine": {"voice_studio": API_VERSION, "device": engine.loaded_device()},
    }


def main(argv=None):
    ap = build_parser()
    args, code = contract.parse(ap, argv)
    if args is None:
        return code
    return contract.run(speak, args, as_json=args.json)


if __name__ == "__main__":
    import sys
    sys.exit(main())
