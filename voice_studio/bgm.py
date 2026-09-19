"""bgm.py — thư viện nhạc nền của trạm giọng: đọc `bgm-library.json`, chọn style, dựng khung rỗng.

Thư viện là MỘT thư mục (mặc định `$VOICE_STATION/assets/bgm`, đổi bằng `VOICE_BGM_DIR`)
chứa `bgm-library.json` và các file `<style>.mp3` nằm cạnh nó:

    {
      "volume": 0.10,                 # âm lượng lớp nhạc dưới giọng (mặc định 0.10)
      "default": "<style>",           # style dùng khi không chọn / chọn tên lạ
      "styles": [{"name": "<style>", "mood": "...", "use": "..."}]
    }

Khoá `"dir"` của bản cũ bị BỎ QUA: thư mục luôn suy từ vị trí file json, để chép cả thư
viện sang máy khác (hay đổi tên trạm) không phải sửa đường dẫn nào.

Repo KHÔNG chứa file nhạc nào — `init_library()` chỉ dựng khung rỗng + json mẫu + README
hướng dẫn tự sinh nhạc bằng MusicGen (hoặc bỏ nhạc bản quyền sạch của mình vào).

CLI:  python -m voice_studio.bgm list [--dir D] [--json]
      python -m voice_studio.bgm pick [STYLE] [--dir D] [--json]
Mã thoát: 0 ok · 2 gọi sai · 3 thư viện chưa có (chạy init).
"""
import argparse
import json
import os
import sys
import warnings

from . import _env

LIBRARY_FILE = "bgm-library.json"
DEFAULT_VOLUME = 0.10

SAMPLE_LIBRARY = {
    "_doc": ("Thư viện nhạc nền. Mỗi style là một file <name>.mp3 nằm cạnh file này. "
             "Người tạo nội dung chọn một style theo nội dung; renderer trộn ở mức 'volume'."),
    "volume": DEFAULT_VOLUME,
    "default": "neutral",
    "styles": [
        {"name": "neutral", "mood": "trung tính, chuyên nghiệp", "use": "Mặc định an toàn cho mọi nội dung."},
        {"name": "uplifting", "mood": "tươi sáng, tích cực", "use": "Tin tốt, ra mắt, cột mốc."},
        {"name": "ambient", "mood": "trầm lắng, sâu", "use": "Phân tích dài, chủ đề nghiêm túc."},
    ],
}

README_TEXT = """# Thư viện nhạc nền

Thư mục này chứa nhạc nền dùng chung cho mọi pipeline gọi trạm giọng.

- `bgm-library.json` — danh sách style, style mặc định, âm lượng trộn (mặc định 0.10).
- `<style>.mp3` — một file cho mỗi style, **tên file trùng `name`** trong json.

Repo không phát hành file nhạc nào. Hai cách có nhạc:

1. **Tự sinh bằng MusicGen** (công cụ ở `extras/musicgen/` của repo): sinh mỗi style một bản
   ~60 giây, lưu thành `<style>.mp3` ở đây. Kiểm lại giấy phép weights của MusicGen trước
   khi dùng cho mục đích thương mại.
2. **Dùng nhạc bạn có quyền dùng** — đổi tên thành `<style>.mp3` và khai trong json.

Kiểm: `python -m voice_studio.bgm list` phải liệt kê đủ style, không báo thiếu file.
"""


class Library:
    def __init__(self, dir, data):
        self.dir = dir
        self.data = data
        self.styles = [s for s in data.get("styles", []) if isinstance(s, dict) and s.get("name")]
        try:
            self.volume = float(data.get("volume", DEFAULT_VOLUME))
        except (TypeError, ValueError):
            self.volume = DEFAULT_VOLUME
        names = self.names()
        d = data.get("default")
        self.default = d if d in names else (names[0] if names else None)

    def names(self):
        return [s["name"] for s in self.styles]

    def path_of(self, style):
        return os.path.join(self.dir, f"{style}.mp3")

    def resolve(self, style=None):
        """Tên style hợp lệ: style đưa vào nếu có trong thư viện, không thì mặc định."""
        if style and style in self.names():
            return style
        if style:
            warnings.warn(f"style nhạc nền '{style}' không có trong thư viện — dùng mặc định "
                          f"'{self.default}'", UserWarning, stacklevel=3)
        if not self.default:
            raise FileNotFoundError(f"thư viện nhạc nền {self.dir} chưa khai style nào")
        return self.default


def bgm_dir():
    return _env.bgm_dir()


def library(dir=None):
    d = os.path.abspath(os.path.expanduser(dir)) if dir else bgm_dir()
    f = os.path.join(d, LIBRARY_FILE)
    if not os.path.isfile(f):
        raise FileNotFoundError(
            f"chưa có thư viện nhạc nền ({f}). Dựng khung bằng voice_studio.bgm.init_library() "
            f"hoặc `voice-studio init`, rồi thêm file <style>.mp3.")
    with open(f, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return Library(d, data)


def pick(style=None, dir=None):
    """Đường dẫn file nhạc cho `style` (None / tên lạ → mặc định). Thiếu file ⇒ FileNotFoundError."""
    lib = library(dir)
    path = lib.path_of(lib.resolve(style))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"thư viện khai style nhưng thiếu file nhạc: {path}")
    return path


def volume(dir=None):
    return library(dir).volume


def init_library(dir=None):
    """Dựng khung thư viện rỗng: thư mục + json mẫu + README. Không đè file đã có."""
    d = os.path.abspath(os.path.expanduser(dir)) if dir else bgm_dir()
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, LIBRARY_FILE)
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(SAMPLE_LIBRARY, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    r = os.path.join(d, "README.md")
    if not os.path.exists(r):
        with open(r, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(README_TEXT)
    return d


def _parser():
    p = argparse.ArgumentParser(prog="voice-studio bgm", description="Thư viện nhạc nền của trạm giọng.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("list", "liệt kê style"), ("pick", "in đường dẫn nhạc của một style")):
        sp = sub.add_parser(name, help=helptext)
        if name == "pick":
            sp.add_argument("style", nargs="?", default=None)
        sp.add_argument("--dir", default=None, help="thư viện (mặc định VOICE_BGM_DIR / trạm giọng)")
        sp.add_argument("--json", action="store_true", help="một dòng JSON cuối stdout")
    return p


def main(argv=None):
    try:
        a = _parser().parse_args(argv)
    except SystemExit as e:
        return 0 if e.code == 0 else 2
    try:
        lib = library(a.dir)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        if a.json:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 3
    if a.cmd == "list":
        missing = [n for n in lib.names() if not os.path.isfile(lib.path_of(n))]
        if a.json:
            print(json.dumps({"ok": True, "dir": lib.dir, "default": lib.default,
                              "volume": lib.volume, "styles": lib.names(), "missing": missing},
                             ensure_ascii=False))
        else:
            for s in lib.styles:
                mark = "*" if s["name"] == lib.default else " "
                gone = "  [THIẾU FILE]" if s["name"] in missing else ""
                print(f"{mark} {s['name']:<20} {s.get('mood', '')}{gone}")
        return 0
    try:
        style = lib.resolve(a.style)
        path = pick(style, a.dir)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        if a.json:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 3
    if a.json:
        print(json.dumps({"ok": True, "style": style, "path": path, "volume": lib.volume},
                         ensure_ascii=False))
    else:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
