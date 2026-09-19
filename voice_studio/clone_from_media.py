"""clone_from_media.py — dựng profile giọng từ một file audio/video dài (hoặc một URL video).

    voice-studio clone --file talk.m4a --name demo --consent
    voice-studio clone --url <link-video> --name demo --dur 12 --consent

ĐẠO ĐỨC — ĐỌC TRƯỚC KHI DÙNG: chỉ clone giọng của chính bạn hoặc của người đã đồng ý rõ
ràng. Có link công khai KHÔNG có nghĩa là được phép clone giọng người trong đó. Lệnh đòi cờ
`--consent` để người chạy xác nhận điều này mỗi lần.

Cách làm: (tải bestaudio bằng yt-dlp nếu là URL) → thử lần lượt các mốc giây, cắt ~12 s,
nhận dạng bằng faster-whisper → chọn đoạn ĐỦ DÀI và KHÔNG có từ đệm ("ừ", "ờ"…) → lưu profile
(không đổi mặc định) → đọc thử một câu và nghe ngược để kiểm.

Phụ thuộc thêm (không bắt buộc cho phần còn lại của package): `yt-dlp` (chỉ khi dùng --url),
`faster-whisper`. Clip trung gian nằm ở `<VOICE_STUDIO_WORK>/lab/<tên>/clone/` — ngoài repo.
"""
import argparse
import os
import re
import subprocess
import sys

from . import _env, contract, engine, profiles
from .contract import ContractError, log

FILLER = re.compile(r"(^|[\s,.])(ừ|ờ|à|ưm|hử|ợ|ạ|ê)([\s,.]|$)", re.IGNORECASE)
MIN_CHARS = 80
DEFAULT_OFFSETS = "60,90,120,150,180,210,240,300,360,420,480,540"
VERIFY_TEXT = "Chương một. Đây là câu đọc thử để kiểm tra giọng vừa dựng."


def build_parser(prog="voice-studio clone"):
    ap = argparse.ArgumentParser(
        prog=prog, description="Dựng profile giọng từ media dài. CHỈ với giọng đã được đồng ý.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="File audio/video cục bộ.")
    src.add_argument("--url", help="URL video (tải bằng yt-dlp).")
    ap.add_argument("--name", required=True, help="Tên profile sẽ tạo.")
    ap.add_argument("--dur", type=float, default=12.0, help="Độ dài đoạn mẫu (3–15 s cho clone tốt).")
    ap.add_argument("--offsets", default=DEFAULT_OFFSETS, help="Các mốc giây thử, cách nhau dấu phẩy.")
    ap.add_argument("--consent", action="store_true",
                    help="Xác nhận: giọng này là của bạn hoặc người đã đồng ý cho clone.")
    ap.add_argument("--no-verify", action="store_true", help="Bỏ bước đọc thử + nghe ngược.")
    ap.add_argument("--json", action="store_true")
    return ap


def _download(url, workdir):
    out = os.path.join(workdir, "src.m4a")
    log("[clone] tải bestaudio bằng yt-dlp …")
    subprocess.run([sys.executable, "-m", "yt_dlp", "-f", "bestaudio", "-x", "--audio-format", "m4a",
                    "-o", out, "--force-overwrites", url], check=True, capture_output=True, timeout=600)
    if os.path.isfile(out):
        return out
    cands = sorted(f for f in os.listdir(workdir) if f.startswith("src."))
    if not cands:
        raise contract.EngineError("yt-dlp không tạo ra file audio nào")
    return os.path.join(workdir, cands[0])


def pick_segment(cut, transcribe, offsets):
    """Chọn đoạn đầu tiên đủ dài và không có từ đệm; không có thì lấy đoạn đủ dài đầu tiên.

    `cut(offset) -> wav`, `transcribe(wav) -> text` được truyền vào để test không cần ASR thật.
    Trả (wav, text) hoặc (None, "").
    """
    fallback = None
    for off in offsets:
        try:
            w = cut(off)
        except Exception as e:      # noqa: BLE001 — mốc vượt quá độ dài file là chuyện thường
            log(f"[clone]   mốc {off}: cắt lỗi {e}")
            continue
        t = transcribe(w)
        bad = bool(FILLER.search(t))
        log(f"[clone]   mốc {off}: {len(t)} ký tự [{'từ đệm' if bad else 'SẠCH'}] {t[:60]!r}")
        if len(t) >= MIN_CHARS and not bad:
            return w, t
        if fallback is None and len(t) >= MIN_CHARS:
            fallback = (w, t)
    if fallback:
        log("[clone]   không có đoạn sạch hoàn toàn — dùng đoạn đủ dài đầu tiên.")
        return fallback
    return None, ""


def clone(args):
    if not args.consent:
        raise ContractError("thiếu --consent: chỉ clone giọng của bạn hoặc người đã đồng ý.")
    workdir = _env.lab_dir(args.name, "clone")
    os.makedirs(workdir, exist_ok=True)
    if args.file:
        src = os.path.abspath(args.file)
        if not os.path.isfile(src):
            raise ContractError(f"không thấy file: {src}")
    else:
        src = _download(args.url, workdir)

    from faster_whisper import WhisperModel
    asr = WhisperModel("small", device="cpu", compute_type="int8")

    def transcribe(path):
        segs, _ = asr.transcribe(path, language="vi", beam_size=5)
        return "".join(s.text for s in segs).strip()

    def cut(off):
        wav = os.path.join(workdir, f"seg_{int(off)}.wav")
        subprocess.run([engine.ffmpeg(), "-y", "-ss", str(off), "-t", str(args.dur), "-i", src,
                        "-ac", "1", "-ar", "24000", wav], check=True, capture_output=True)
        return wav

    try:
        offsets = [float(x) for x in args.offsets.split(",") if x.strip()]
    except ValueError as e:
        raise ContractError(f"--offsets không hợp lệ: {e}") from e
    ref_wav, ref_text = pick_segment(cut, transcribe, offsets)
    if not ref_wav:
        raise ContractError("không tìm được đoạn lời đủ dài — thử --offsets khác")

    profiles.save_profile_from_wav(ref_wav, ref_text, args.name, set_as_default=False)
    log(f"[clone] đã lưu profile '{args.name}' (mặc định KHÔNG đổi). Lời: {ref_text[:90]!r}")
    result = {"profile": args.name, "ref_text": ref_text, "voices_dir": profiles.voices_dir()}
    if not args.no_verify:
        import numpy as np
        import soundfile as sf
        a, sr = engine.synth(VERIFY_TEXT, args.name, seed=42)
        vwav = os.path.join(workdir, "verify.wav")
        sf.write(vwav, np.asarray(a, dtype=np.float32), sr)
        heard = transcribe(vwav)
        log(f"[clone] nghe ngược bản đọc thử: {heard[:90]!r}")
        result["verify_heard"] = heard
    return result


def main(argv=None):
    args, code = contract.parse(build_parser(), argv)
    if args is None:
        return code
    return contract.run(clone, args, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
