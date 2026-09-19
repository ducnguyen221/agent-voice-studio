"""cli.py — lệnh `voice-studio` (và `python -m voice_studio`): một cửa cho mọi công cụ của trạm giọng.

Mỗi lệnh con nằm trong module riêng và chỉ được import khi được gọi — `voice-studio --help`
chạy được trên máy chưa cài torch/engine. Tham số sau tên lệnh chuyển nguyên cho lệnh con.
"""
import importlib
import sys

from . import API_VERSION, __version__, contract

# tên lệnh -> (module, mô tả một dòng)
COMMANDS = {
    "speak":        ("voice_studio.speak", "text → file audio (hợp đồng ổn định, --json, mã 0/1/2/3)"),
    "narrate":      ("voice_studio.narrate", "video câm + lời dẫn → MP4 có giọng (+ nhạc nền)"),
    "make-profile": ("voice_studio.make_profile", "tạo profile giọng từ bản ghi / video / instruct"),
    "clone":        ("voice_studio.clone_from_media", "dựng profile từ media dài hoặc URL (cần --consent)"),
    "verify":       ("voice_studio.lab.verify", "soi một clip mẫu qua 6 cổng kiểm"),
    "reftext":      ("voice_studio.reftext_punct", "thêm dấu ngắt vào lời mẫu theo khoảng lặng thật"),
    "clean":        ("voice_studio.clean.clean_voice", "tách giọng + khử tạp âm cho clip mẫu"),
    "bgm":          ("voice_studio.bgm", "thư viện nhạc nền: list | pick <style>"),
    "tts":          ("voice_studio.tts", "đọc nhanh một câu ra file"),
    "ui":           ("voice_studio.ui", "giao diện web cục bộ để nghe thử"),
    "doctor":       ("voice_studio.doctor", "kiểm trạm giọng, chỉ bước cài còn thiếu"),
    "mcp":          ("voice_studio.mcp_server", "chạy MCP server (stdio) cho agent"),
    "lab":          (None, "bộ dựng profile đa sắc thái: mine | build | split | organize"),
    "init":         (None, "dựng cây trạm + station.json"),
    "export":       (None, "đóng gói giọng cá nhân để chuyển máy"),
    "import":       (None, "nhập gói giọng cá nhân"),
}
LAB = {
    "mine": "voice_studio.lab.mine",
    "build": "voice_studio.lab.build",
    "split": "voice_studio.lab.split",
    "organize": "voice_studio.lab.organize",
}
NOT_YET = ("init", "export", "import")


def _console_utf8():
    # Console Windows mặc định cp1252 sẽ sập khi in tiếng Việt.
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def usage():
    lines = [f"voice-studio {__version__} (hợp đồng API {API_VERSION})", "",
             "Cách dùng: voice-studio <lệnh> [tham số…]   ·   voice-studio <lệnh> --help", "",
             "Lệnh:"]
    for name, (_, desc) in COMMANDS.items():
        lines.append(f"  {name:<13} {desc}")
    lines += ["", "Mã thoát chung: 0 ok · 1 lỗi engine · 2 gọi/cấu hình sai · 3 trạm/engine chưa cài."]
    return "\n".join(lines)


def _call(module, argv):
    mod = importlib.import_module(module)
    if module == "voice_studio.mcp_server":
        mod.main()
        return contract.OK
    rc = mod.main(argv)
    return contract.OK if rc is None else int(rc)


def main(argv=None):
    _console_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage())
        return contract.OK
    if argv[0] in ("-V", "--version"):
        print(f"voice-studio {__version__} (API {API_VERSION})")
        return contract.OK
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        contract.log(f"lệnh lạ: '{cmd}'\n\n{usage()}")
        return contract.CONTRACT_ERROR
    if cmd in NOT_YET:
        contract.log(f"`voice-studio {cmd}` chưa có trong bản này (đang phát triển).")
        return contract.CONTRACT_ERROR
    if cmd == "lab":
        if not rest or rest[0] in ("-h", "--help") or rest[0] not in LAB:
            print("Cách dùng: voice-studio lab <" + "|".join(LAB) + "> [tham số…]")
            return contract.OK if (not rest or rest[0] in ("-h", "--help")) else contract.CONTRACT_ERROR
        return _call(LAB[rest[0]], rest[1:])
    return _call(COMMANDS[cmd][0], rest)


if __name__ == "__main__":
    sys.exit(main())
