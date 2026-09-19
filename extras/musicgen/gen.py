"""gen.py — sinh MỘT (hoặc vài) bản nhạc nền từ mô tả bằng MusicGen, qua `transformers`.

Công cụ TUỲ CHỌN, không thuộc package `voice_studio`, không có trong phụ thuộc: chạy bằng một
venv có `torch` + `transformers` + `soundfile` (có thể chính venv engine). Lần đầu tải weights
từ Hugging Face (large cỡ chục GB) — tự bạn quyết.

GIẤY PHÉP: code MusicGen là MIT, nhưng WEIGHTS `facebook/musicgen-*` theo **CC-BY-NC 4.0 —
KHÔNG dùng thương mại**. Nhạc sinh ra dùng cho kênh có kiếm tiền là việc bạn phải tự cân nhắc.
Xem docs/bgm-generation.md.

    python extras/musicgen/gen.py --prompt "calm ambient pad, 80 BPM, instrumental" --name calm
    python extras/musicgen/gen.py --prompt "..." --name x --model small --seconds 20 --out <thư mục>

Output: `<out>/<name>.wav` (mặc định `<out>` = `$VOICE_STUDIO_WORK/musicgen`, tức trong trạm,
không bao giờ trong repo). Thêm `--mp3` để đổi sang mp3 bằng ffmpeg — dạng thư viện nhạc nền đọc.
Mã thoát: 0 ok · 2 gọi sai · 3 thiếu torch/transformers.
"""
import argparse
import os
import subprocess
import sys

MODELS = {
    "small": "facebook/musicgen-small",
    "medium": "facebook/musicgen-medium",
    "large": "facebook/musicgen-large",
}
DEFAULT_MODEL = "large"
FRAMES_PER_SECOND = 50          # MusicGen sinh ~50 token âm thanh mỗi giây


def default_out():
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from voice_studio import _env
        return os.path.join(_env.work_dir(), "musicgen")
    except Exception:           # noqa: BLE001 — chạy lẻ ngoài repo
        return os.path.join(os.getcwd(), "musicgen-out")


class Generator:
    """Nạp model một lần, sinh nhiều bản. Import torch/transformers LƯỜI — trong __init__."""

    def __init__(self, model="large", device=None):
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        self.torch = torch
        self.model_id = MODELS.get(model, model)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        print(f"[musicgen] model={self.model_id} device={self.device}", file=sys.stderr, flush=True)
        self.proc = AutoProcessor.from_pretrained(self.model_id)
        self.model = MusicgenForConditionalGeneration.from_pretrained(
            self.model_id, torch_dtype=dtype).to(self.device)
        self.sr = self.model.config.audio_encoder.sampling_rate

    def generate(self, prompt, seconds=30, guidance=3.0):
        inp = self.proc(text=[prompt], padding=True, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(**inp, max_new_tokens=int(seconds * FRAMES_PER_SECOND),
                                      do_sample=True, guidance_scale=guidance)
        return out[0, 0].cpu().float().numpy(), self.sr


def write(audio, sr, out_dir, name, mp3=False):
    import soundfile as sf
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, f"{name}.wav")
    sf.write(wav, audio, sr)
    if not mp3:
        return wav
    try:
        from voice_studio import _env
        ff = _env.ffmpeg_exe()
    except Exception:           # noqa: BLE001
        ff = "ffmpeg"
    mp3_path = os.path.join(out_dir, f"{name}.mp3")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k", mp3_path], check=True)
    os.remove(wav)
    return mp3_path


def build_parser():
    ap = argparse.ArgumentParser(prog="gen.py", description="Sinh nhạc nền từ mô tả bằng MusicGen "
                                 "(weights CC-BY-NC 4.0 — không thương mại).")
    ap.add_argument("--prompt", required=True, help="mô tả tiếng Anh (nên có 'instrumental', BPM)")
    ap.add_argument("--name", required=True, help="tên file (không đuôi)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="small | medium | large | <model id>")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--guidance", type=float, default=3.0)
    ap.add_argument("--out", default=None, help="thư mục output (mặc định trong trạm)")
    ap.add_argument("--mp3", action="store_true", help="đổi sang mp3 bằng ffmpeg")
    return ap


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return 0 if e.code in (0, None) else 2
    try:
        g = Generator(args.model)
    except ImportError as e:
        print(f"[musicgen] thiếu thư viện ({e}). Cài: pip install torch transformers soundfile",
              file=sys.stderr)
        return 3
    audio, sr = g.generate(args.prompt, args.seconds, args.guidance)
    path = write(audio, sr, args.out or default_out(), args.name, args.mp3)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
