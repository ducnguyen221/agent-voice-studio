"""tts.py — `voice-studio tts`: đọc nhanh một câu ra file, không cần nhớ tham số hợp đồng.

    voice-studio tts --text "Xin chào" --out a.mp3
    voice-studio tts --text "Xin chào" --out a.wav --profile demo
    voice-studio tts --text "Hello" --out en.wav --instruct "male, middle-aged, british accent" --lang English
    voice-studio tts --text "Xin chào" --out c.wav --ref-audio mau.wav --ref-text "lời của mẫu"

Cùng đường chạy với tool MCP `synthesize_speech` / `clone_voice` (profile → mặc định → `instruct`),
in ra đúng một dòng kết quả. Thay cho vỏ PowerShell cũ — chạy được mọi hệ điều hành.
Cho pipeline tự động, dùng `voice-studio speak --json` (hợp đồng ổn định, mã thoát 0/1/2/3).
"""
import argparse
import sys

from . import contract


def build_parser(prog="voice-studio tts"):
    ap = argparse.ArgumentParser(prog=prog, description="Đọc nhanh một câu ra file audio.")
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True, help="File ra (.wav hoặc .mp3).")
    ap.add_argument("--profile", default="", help="Profile giọng (bỏ trống = mặc định).")
    ap.add_argument("--instruct", default="female, young adult, moderate pitch",
                    help="Dùng khi không có profile nào.")
    ap.add_argument("--lang", default="Vietnamese")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--ref-audio", default="", help="Clone một lần theo clip tham chiếu.")
    ap.add_argument("--ref-text", default="", help="Lời của clip tham chiếu.")
    return ap


def main(argv=None):
    args, code = contract.parse(build_parser(), argv)
    if args is None:
        return code
    from .mcp_server import clone_voice, synthesize_speech
    try:
        if args.ref_audio:
            msg = clone_voice(text=args.text, output_path=args.out, ref_audio=args.ref_audio,
                                ref_text=args.ref_text, language=args.lang, speed=args.speed)
        else:
            msg = synthesize_speech(text=args.text, output_path=args.out, instruct=args.instruct,
                                      language=args.lang, speed=args.speed,
                                      voice_profile=args.profile)
    except Exception as e:      # noqa: BLE001 — biên CLI
        code = contract.classify(e)
        contract.log(f"[tts] LỖI ({code}): {e}")
        return code
    print(msg)
    return contract.OK if msg.startswith("OK") else contract.CONTRACT_ERROR


if __name__ == "__main__":
    sys.exit(main())
