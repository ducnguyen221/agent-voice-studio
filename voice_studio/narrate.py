"""narrate.py — `voice-studio narrate`: video câm + lời dẫn → MP4 hoàn chỉnh có giọng (và nhạc nền).

    voice-studio narrate --video silent.mp4 --text "Xin chào…" --out final.mp4 --json
    voice-studio narrate --video silent.mp4 --file script.txt --out final.mp4 \
                         --profile demo --bgm neutral --mode fit --json

Dùng CÙNG đường tổng hợp với `speak` (profile → mặc định; không bao giờ lùi về giọng ngẫu
nhiên), rồi `voice_studio.av.mux` ghép vào video:
  --mode fit       độ dài = max(video, giọng): giữ khung cuối / đệm im lặng (mặc định)
  --mode shortest  cắt theo cái ngắn hơn
Nhạc nền: `--bgm <style|đường dẫn>` tra thư viện `VOICE_BGM_DIR`; `--bgm none` tắt hẳn;
bỏ trống thì theo biến `VOICE_BGM` như pipeline cũ.

Kết quả (`--json`): {"ok": true, "outputs": [{"kind": "video", "path", "duration"}],
"voice_duration", "video_duration", "profile", "timings", "engine"}. Mã thoát như `speak`.
"""
import argparse
import os
import time

from . import API_VERSION, av, contract, engine
from .contract import ContractError, log
from .speak import add_voice_args, read_text, resolve_profile, synthesize


def build_parser(prog="voice-studio narrate"):
    ap = argparse.ArgumentParser(prog=prog, description="Lồng giọng đọc vào một video câm.")
    ap.add_argument("--video", required=True, help="Video câm đầu vào (.mp4).")
    ap.add_argument("--out", required=True, help="Video hoàn chỉnh (.mp4).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", help="Lời dẫn.")
    g.add_argument("--file", "--text-file", dest="file", help="File UTF-8 chứa lời dẫn.")
    ap.add_argument("--mode", choices=av.MODES, default="fit")
    ap.add_argument("--bgm", default=None,
                    help="Style nhạc nền, đường dẫn file, hoặc 'none' để tắt.")
    ap.add_argument("--bgm-volume", type=float, default=None, help="Âm lượng nhạc nền (0.10 = 10%%).")
    add_voice_args(ap)
    return ap


def _bgm_arg(value):
    if value is None:
        return None                 # theo VOICE_BGM như cũ
    if value.strip().lower() in ("none", "off", "0", ""):
        return False
    return value


def narrate(args):
    t0 = time.perf_counter()
    if not os.path.isfile(args.video):
        raise ContractError(f"không thấy video: {args.video}")
    text = read_text(args)
    profile = resolve_profile(args.profile, args.instruct)
    m = engine.load()
    t1 = time.perf_counter()
    wav, sr = synthesize(text, profile, instruct=args.instruct, language=args.lang,
                         speed=args.speed, seed=args.seed, normalize=args.normalize, model=m)
    t2 = time.perf_counter()
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp_wav = out + ".__voice.wav"
    engine.save(wav, tmp_wav, sr)
    try:
        vdur = av.video_duration(args.video)
        adur = len(wav) / float(sr)
        log(f"[narrate] video {vdur:.1f}s + giọng {adur:.1f}s → ghép (mode={args.mode})")
        av.mux(args.video, tmp_wav, out, mode=args.mode, bgm=_bgm_arg(args.bgm),
               volume=args.bgm_volume)
    finally:
        # Không để lại wav tạm cạnh sản phẩm — cùng bài học với engine.save().
        try:
            os.remove(tmp_wav)
        except OSError:
            pass
    final = max(vdur, adur) if args.mode == "fit" else min(vdur, adur)
    log(f"[narrate] XONG → {out}")
    return {
        "outputs": [{"kind": "video", "path": out, "duration": round(final, 3)}],
        "voice_duration": round(adur, 3), "video_duration": round(vdur, 3),
        "profile": profile,
        "timings": {"load": round(t1 - t0, 3), "synth": round(t2 - t1, 3),
                    "total": round(time.perf_counter() - t0, 3)},
        "engine": {"voice_studio": API_VERSION, "device": engine.loaded_device()},
    }


def main(argv=None):
    args, code = contract.parse(build_parser(), argv)
    if args is None:
        return code
    return contract.run(narrate, args, as_json=args.json)


if __name__ == "__main__":
    import sys
    sys.exit(main())
