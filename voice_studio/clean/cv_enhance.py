"""cv_enhance.py — tầng 2: khử tạp âm / dereverb bằng ClearerVoice (`clearvoice`).

Chạy TRONG venv `.venv-cv` (numpy<2), do `clean_voice.py` gọi qua tiến trình con bằng ĐƯỜNG DẪN
FILE — venv đó không cài `voice_studio`, nên file này tự chứa. Đọc 1 file audio → ghi 1 WAV.

clearvoice tải checkpoint vào thư mục `checkpoints/` TƯƠNG ĐỐI theo thư mục hiện hành, nên
phải `--workdir` về thư mục công cụ làm sạch của trạm để không tải lại model mỗi lần (và để
model không rơi vào trong repo).
"""
import argparse
import os
import sys
from pathlib import Path

# sample rate đầu ra của từng model SE của ClearerVoice
MODEL_SR = {
    "MossFormer2_SE_48K": 48000,
    "MossFormerGAN_SE_16K": 16000,
    "FRCRN_SE_16K": 16000,
}


def unwrap_to_mono(result):
    """ClearVoice trả ndarray / tensor / dict{model: arr} tuỳ phiên bản → mảng mono float32."""
    import numpy as np
    while isinstance(result, dict):
        if not result:
            raise RuntimeError("ClearVoice trả về dict rỗng")
        result = next(iter(result.values()))
    if isinstance(result, (list, tuple)):
        if not result:
            raise RuntimeError("ClearVoice trả về list rỗng")
        result = result[0]
    if hasattr(result, "detach"):  # torch.Tensor
        result = result.detach().cpu().numpy()
    arr = np.squeeze(np.asarray(result, dtype=np.float32))
    if arr.ndim > 1:
        # có thể là (ch, n) hoặc (n, ch) → gộp về mono
        arr = arr.mean(axis=0) if arr.shape[0] < arr.shape[1] else arr.mean(axis=1)
    return np.ascontiguousarray(arr, dtype=np.float32)


def main(argv=None):
    ap = argparse.ArgumentParser(description="ClearerVoice speech enhancement helper")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="MossFormer2_SE_48K")
    ap.add_argument("--workdir", default=None, help="Thư mục chứa checkpoints/ (mặc định: cwd).")
    args = ap.parse_args(argv)

    src = Path(args.input).resolve()
    dst = Path(args.out).resolve()
    if not src.is_file():
        print(f"[cv_enhance] không tìm thấy input: {src}", file=sys.stderr)
        return 1
    if args.workdir:
        os.makedirs(args.workdir, exist_ok=True)
        os.chdir(args.workdir)      # BẮT BUỘC: checkpoint của clearvoice là đường dẫn tương đối

    import numpy as np
    import soundfile as sf
    from clearvoice import ClearVoice

    cv = ClearVoice(task="speech_enhancement", model_names=[args.model])
    audio = unwrap_to_mono(cv(input_path=str(src), online_write=False))
    if audio.size == 0:
        print("[cv_enhance] output rỗng", file=sys.stderr)
        return 1
    peak = float(np.max(np.abs(audio)))
    if peak > 1.0:  # chống clip khi model trả biên độ > 1
        audio = audio / peak * 0.99
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), audio, MODEL_SR.get(args.model, 48000), subtype="PCM_16")
    print(f"[cv_enhance] ok -> {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
