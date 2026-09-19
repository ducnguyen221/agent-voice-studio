"""clean_voice.py — tách giọng người + khử tạp âm → WAV sạch cho voice-clone. Chạy được trên Windows và macOS.

    voice-studio clean input.mp3
    voice-studio clean input.mp3 --out sach.wav
    voice-studio clean ghi_am.wav --enhance-only
    voice-studio clean nhac.mp3 --no-enhance

Tầng 1 (audio-separator) cần venv `.venv-sep`; tầng 2 (ClearerVoice) cần venv `.venv-cv` —
hai venv ở THƯ MỤC CÔNG CỤ LÀM SẠCH của trạm:

    --clean-dir → VOICE_CLEAN_DIR → $VOICE_STATION/voice-clean → <cha OMNIVOICE_DIR>/voice-clean
    → ~/.voice/voice-clean

Python của venv chọn theo hệ điều hành (`Scripts/python.exe` trên Windows, `bin/python` nơi
khác). Tiến trình hiện tại không có `audio_separator` ⇒ tự chạy lại chính file này bằng python
của `.venv-sep` (tiến trình con, chuyển nguyên mã thoát) — thay cho vỏ `.ps1` chỉ chạy trên
Windows. File tự chứa (không import `voice_studio`) vì venv tách không cài package.

Model (~821 MB) KHÔNG nằm trong repo: tầng 1 tải vào `<clean-dir>/models/`, tầng 2 vào
`<clean-dir>/checkpoints/` ở lần chạy đầu. Cài đặt: README.md cạnh file này.
Mã thoát: 0 ok · 1 lỗi xử lý · 2 gọi sai · 3 thiếu venv/công cụ.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CV_HELPER = HERE / "cv_enhance.py"
DEFAULT_SEP_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
DEFAULT_CV_MODEL = "MossFormer2_SE_48K"
SEP_VENV, CV_VENV = ".venv-sep", ".venv-cv"


def log(msg):
    print(f"[clean_voice] {msg}", file=sys.stderr, flush=True)


def _envv(name):
    return (os.environ.get(name) or "").strip() or None


def resolve_clean_dir(explicit=None):
    """Thư mục công cụ làm sạch (chứa hai venv, models/, checkpoints/)."""
    for cand in (explicit, _envv("VOICE_CLEAN_DIR")):
        if cand:
            return Path(cand).expanduser().resolve()
    st = _envv("VOICE_STATION")
    if st:
        return Path(st).expanduser().resolve() / "voice-clean"
    eng = _envv("OMNIVOICE_DIR")
    if eng:
        return Path(eng).expanduser().resolve().parent / "voice-clean"
    return Path.home() / ".voice" / "voice-clean"


def venv_python(root, venv, windows=None):
    """Đường python của một venv theo hệ điều hành."""
    windows = (os.name == "nt") if windows is None else windows
    base = Path(root) / venv
    return base / "Scripts" / "python.exe" if windows else base / "bin" / "python"


def stats(path):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    rms = float(np.sqrt(np.mean(np.square(data, dtype=np.float64)))) if data.size else 0.0
    return {"path": str(path), "sr": sr, "duration": (len(data) / sr) if sr else 0.0,
            "rms": rms, "peak": float(np.max(np.abs(data))) if data.size else 0.0}


def separate(src, tmpdir, model, clean_dir):
    """Tầng 1: trả đường dẫn vocal stem."""
    from audio_separator.separator import Separator
    sep = Separator(output_dir=str(tmpdir), output_format="WAV",
                    model_file_dir=str(Path(clean_dir) / "models"))
    sep.load_model(model_filename=model)
    produced = sep.separate(str(src))
    files = [Path(tmpdir) / Path(p).name for p in produced]
    vocals = [p for p in files if "vocal" in p.name.lower()]
    if not vocals:
        raise RuntimeError("không thấy vocal stem trong output: " + ", ".join(p.name for p in files))
    return vocals[0]


def enhance_cmd(cv_py, src, dst, model, clean_dir):
    return [str(cv_py), str(CV_HELPER), "--input", str(src), "--out", str(dst),
            "--model", model, "--workdir", str(clean_dir)]


def enhance(src, dst, model, clean_dir):
    """Tầng 2: gọi cv_enhance.py bằng python của `.venv-cv`."""
    cv_py = venv_python(clean_dir, CV_VENV)
    if not cv_py.is_file():
        raise FileNotFoundError(f"thiếu venv ClearerVoice: {cv_py}")
    proc = subprocess.run(enhance_cmd(cv_py, src, dst, model, clean_dir))
    if proc.returncode != 0:
        raise RuntimeError(f"cv_enhance thất bại (mã {proc.returncode})")
    if not Path(dst).is_file():
        raise RuntimeError(f"cv_enhance không tạo ra file: {dst}")
    return Path(dst)


def build_parser(prog="voice-studio clean"):
    ap = argparse.ArgumentParser(prog=prog,
                                 description="Tách giọng người + khử tạp âm → WAV sạch cho voice-clone")
    ap.add_argument("input", help="file audio đầu vào (mp3/wav/m4a/…)")
    ap.add_argument("--out", help="WAV kết quả (mặc định <tên>_clean.wav cạnh input)")
    ap.add_argument("--no-enhance", action="store_true", help="chỉ tách vocal, bỏ tầng khử nhiễu")
    ap.add_argument("--enhance-only", action="store_true", help="chỉ khử nhiễu, bỏ tầng tách nhạc")
    ap.add_argument("--sep-model", default=DEFAULT_SEP_MODEL, help="model audio-separator")
    ap.add_argument("--cv-model", default=DEFAULT_CV_MODEL, help="model ClearerVoice SE")
    ap.add_argument("--clean-dir", default=None, help="thư mục công cụ làm sạch (xem docstring)")
    ap.add_argument("--keep-temp", action="store_true", help="giữ file trung gian để debug")
    return ap


def _need_reexec(args):
    """Cần tầng 1 mà tiến trình này không có audio_separator ⇒ chạy lại bằng .venv-sep."""
    if args.enhance_only:
        return False
    try:
        import audio_separator  # noqa: F401
        return False
    except ImportError:
        return True


def main(argv=None):
    ap = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code in (0, None) else 2
    if args.no_enhance and args.enhance_only:
        log("LỖI: --no-enhance và --enhance-only loại trừ nhau")
        return 2
    clean_dir = resolve_clean_dir(args.clean_dir)

    if _need_reexec(args):
        sep_py = venv_python(clean_dir, SEP_VENV)
        if not sep_py.is_file():
            log(f"LỖI: thiếu venv audio-separator: {sep_py} — xem README.md của voice_studio/clean")
            return 3
        raw = sys.argv[1:] if argv is None else list(argv)
        if "--clean-dir" not in raw:
            raw += ["--clean-dir", str(clean_dir)]
        return subprocess.run([str(sep_py), str(Path(__file__).resolve()), *raw]).returncode

    src = Path(args.input).expanduser().resolve()
    if not src.is_file():
        log(f"LỖI: không tìm thấy input: {src}")
        return 2
    out = (Path(args.out).expanduser().resolve() if args.out
           else src.with_name(f"{src.stem}_clean.wav"))
    tmpdir = Path(tempfile.mkdtemp(prefix="voiceclean_"))
    t_sep = t_cv = 0.0
    try:
        stage = src
        if not args.enhance_only:
            log(f"tầng 1/2 tách vocal ({args.sep_model}) …")
            t0 = time.perf_counter()
            stage = separate(src, tmpdir, args.sep_model, clean_dir)
            t_sep = time.perf_counter() - t0
        if not args.no_enhance:
            log(f"tầng 2/2 khử tạp âm ({args.cv_model}) …")
            t0 = time.perf_counter()
            stage = enhance(stage, tmpdir / "enhanced.wav", args.cv_model, clean_dir)
            t_cv = time.perf_counter() - t0
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stage, out)
    except FileNotFoundError as exc:
        log(f"LỖI: {exc}")
        return 3
    except Exception as exc:  # noqa: BLE001 — biên CLI: báo lỗi rõ
        log(f"LỖI: {exc}")
        return 1
    finally:
        if args.keep_temp:
            log(f"giữ file trung gian: {tmpdir}")
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)

    st = stats(out)
    log(f"xong: {st['duration']:.2f}s @ {st['sr']} Hz, RMS {st['rms']:.6f}, peak {st['peak']:.4f}; "
        f"tách {t_sep:.1f}s + khử nhiễu {t_cv:.1f}s")
    print(st["path"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
