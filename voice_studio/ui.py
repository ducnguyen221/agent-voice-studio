"""ui.py — `voice-studio ui`: giao diện web cục bộ để nghe thử giọng (Gradio).

    voice-studio ui                  # http://127.0.0.1:7861 — panel tạo nhanh + UI đầy đủ của engine
    voice-studio ui --plain          # chỉ UI đầy đủ của engine
    voice-studio ui --asr --port 7870

Một phiên bản: UI đầy đủ lấy từ chính gói engine (`omnivoice.cli.demo.build_demo`) nên tự
cập nhật khi nâng engine; phía trên là panel nhỏ tạo nhanh tiếng Việt — chọn một profile
trong kho, hoặc một preset `instruct`. Chỉ nghe ở 127.0.0.1, không mở ra mạng.

Dừng: Ctrl+C trong cửa sổ đang chạy. Cần thêm gói `gradio` trong venv engine.
Output nghe thử nằm ở `<VOICE_STUDIO_WORK>/ui/` — ngoài repo.
"""
import argparse
import os
import sys

from . import _env

PRESETS = {
    "Nữ trẻ": "female, young adult, moderate pitch",
    "Nữ trưởng thành": "female, middle-aged, moderate pitch",
    "Nam trẻ": "male, young adult, moderate pitch",
    "Nam trầm": "male, middle-aged, low pitch",
    "Nam lớn tuổi": "male, elderly, low pitch",
    "Trẻ em": "child, moderate pitch",
    "Thì thầm (nữ)": "female, young adult, whisper",
}
CUSTOM = "Tùy chỉnh…"


def build_parser(prog="voice-studio ui"):
    ap = argparse.ArgumentParser(prog=prog, description="Giao diện web cục bộ để nghe thử giọng.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("STUDIO_PORT", "7861")))
    ap.add_argument("--asr", action="store_true",
                    help="Nạp thêm ASR để tự chép lời clip tham chiếu (lần đầu tải ~1,5 GB).")
    ap.add_argument("--plain", action="store_true", help="Chỉ UI đầy đủ của engine, không panel.")
    ap.add_argument("--no-browser", action="store_true", help="Không tự mở trình duyệt.")
    return ap


def choices():
    """Danh sách lựa chọn giọng cho panel: profile trong kho trước, rồi preset, rồi tuỳ chỉnh."""
    from . import profiles
    return ([f"profile: {n}" for n in profiles.list_profiles()]
            + list(PRESETS.keys()) + [CUSTOM])


def resolve_choice(choice, custom=""):
    """-> (profile | None, instruct | None)."""
    if choice.startswith("profile: "):
        return choice[len("profile: "):], None
    if choice == CUSTOM:
        return None, (custom or "").strip() or PRESETS["Nữ trẻ"]
    return None, PRESETS.get(choice, PRESETS["Nữ trẻ"])


def build_app(model, plain=False):
    import gradio as gr
    from omnivoice.cli.demo import build_demo
    from . import engine

    official = build_demo(model, engine.MODEL_ID)
    if plain:
        return official
    outdir = os.path.join(_env.work_dir(), "ui")

    def quick_gen(text, choice, custom, speed):
        if not (text or "").strip():
            return None, "⚠ Hãy nhập văn bản."
        try:
            prof, instr = resolve_choice(choice, custom)
            wav, sr = engine.synth(text, prof, instruct=instr, speed=float(speed), model=model)
            out = engine.save(wav, os.path.join(outdir, "quick.mp3"), sr)
            return out, f"✅ {len(wav) / sr:.1f}s — giọng: {prof or instr}"
        except Exception as e:      # noqa: BLE001 — hiện lỗi lên UI thay vì làm sập server
            return None, f"❌ Lỗi: {e}"

    opts = choices()
    with gr.Blocks(title="Voice Studio") as app:
        with gr.Accordion("⚡ Tạo nhanh tiếng Việt", open=True):
            qt = gr.Textbox(label="Văn bản", lines=3, placeholder="Nhập đoạn cần đọc…")
            with gr.Row():
                qchoice = gr.Dropdown(opts, value=opts[0], label="Giọng")
                qcustom = gr.Textbox(label="instruct tuỳ chỉnh", placeholder="vd: male, elderly, low pitch",
                                     scale=2)
                qspeed = gr.Slider(0.5, 1.5, value=1.0, step=0.05, label="Tốc độ")
            qbtn = gr.Button("🔊 Tạo nhanh", variant="primary")
            qaudio = gr.Audio(label="Kết quả", type="filepath")
            qmsg = gr.Markdown()
            qbtn.click(quick_gen, [qt, qchoice, qcustom, qspeed], [qaudio, qmsg])
        gr.Markdown("---\n### Bản đầy đủ của engine (clone + thiết kế giọng)")
        official.render()
    return app


def main(argv=None):
    ap = build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 0 if e.code in (0, None) else 2
    try:
        import gradio  # noqa: F401
    except ImportError:
        print("Thiếu gói gradio trong venv engine: <venv>/python -m pip install gradio", file=sys.stderr)
        return 3
    if args.asr:
        os.environ["OMNIVOICE_ONLINE"] = "1"      # ASR có thể phải tải lần đầu
    from . import engine
    model = engine.load()
    if args.asr:
        model.load_asr_model()
    print(f"[ui] http://127.0.0.1:{args.port}  (Ctrl+C để dừng)", file=sys.stderr)
    build_app(model, plain=args.plain).queue().launch(
        server_name="127.0.0.1", server_port=args.port, inbrowser=not args.no_browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
