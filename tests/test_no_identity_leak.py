"""Cổng chống rò danh tính: repo public không được mang tên profile giọng thật, tên người viết
ngoài chỗ ghi công, tiền tố biến của pipeline riêng, hay đường dẫn máy.

Mọi chuỗi cấm dựng bằng chr() để chính file này không tự khớp. Quét mọi file git theo dõi
+ file mới chưa bị ignore (bắt được trước khi `git add`).

MIỄN TRỪ THEO SỐ ĐẾM, không miễn cả file: mỗi mục ghi số lần KỲ VỌNG hiện tại. Vượt số đó
là đỏ — nhét thêm một chỗ vào file đã được miễn cũng bị bắt. Sửa nội dung làm số đổi thì phải
sửa con số ở đây, tức là người sửa buộc phải nhìn thấy mình đang đổi gì.
"""
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SELF = "tests/test_no_identity_leak.py"


def s(*codes):
    return "".join(map(chr, codes))


# khoá → regex (không phân biệt hoa thường)
PATTERNS = {
    "profile-a": re.escape(s(109, 121, 45, 118, 111, 105, 99, 101)),                 # tên profile thật 1
    "profile-b": r"\b" + re.escape(s(97, 45, 116, 117, 110)) + r"\b",                 # tên profile thật 2
    "ten-nguoi": r"(?-i:\b" + re.escape(s(0x110, 0x1EE9, 0x63)) + r"\b)",            # tên riêng (viết hoa; "đạo đức" không khớp)
    "tien-to-pipeline": re.escape(s(78, 69, 87, 83, 95)),                             # tiền tố biến pipeline riêng
    "tac-gia": re.escape(s(100, 117, 99, 110, 103, 117, 121, 101, 110)) + "|" +
               re.escape(s(100, 117, 99, 32, 110, 103, 117, 121, 101, 110)),        # tên tác giả (chỉ ở chỗ ghi công)
    "duong-may-win": re.escape(s(67, 58, 92, 85, 115, 101, 114, 115, 92)),            # ổ C + thư mục người dùng
    "duong-may-posix": r"/(?:home|Users)/[a-z][a-z0-9_-]+/",
}

# (file, khoá) → số lần tối đa được phép. Lý do bên cạnh.
ALLOW = {
    # Bảng tương thích tên biến BGM cũ (đọc được một phiên bản, kèm DeprecationWarning) + test của nó.
    ("voice_studio/_env.py", "tien-to-pipeline"): 7,
    ("voice_studio/av.py", "tien-to-pipeline"): 3,
    ("voice_studio/doctor.py", "tien-to-pipeline"): 3,
    ("tests/conftest.py", "tien-to-pipeline"): 4,
    ("tests/test_av_mux.py", "tien-to-pipeline"): 8,
    ("tests/test_bgm_pick.py", "tien-to-pipeline"): 1,
    # Ghi công tác giả + địa chỉ repo công khai: đúng chỗ, là điều kiện của license.
    (".claude-plugin/marketplace.json", "tac-gia"): 4,
    (".claude-plugin/plugin.json", "tac-gia"): 3,
    (".codex-plugin/plugin.json", "tac-gia"): 3,
    ("LICENSE", "tac-gia"): 1,
    ("NOTICE", "tac-gia"): 1,
    ("README.md", "tac-gia"): 3,
    ("README.vi.md", "tac-gia"): 3,
}

TEXT_EXT = {".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt", ".cfg", ".ini", ".sh",
            ".ps1", ".gitignore", ".gitattributes", ""}


def repo_files():
    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("cần bản clone git")
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others",
                          "--exclude-standard", "-z"], capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    for rel in sorted({p for p in out.split("\0") if p}):
        p = ROOT / rel
        if rel == SELF or not p.is_file():
            continue
        if p.suffix.lower() in TEXT_EXT or p.name.startswith("."):
            yield rel, p


def count_hits():
    hits = Counter()
    for rel, p in repo_files():
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for key, pat in PATTERNS.items():
            n = len(re.findall(pat, text, flags=re.IGNORECASE))
            if n:
                hits[(rel, key)] = n
    return hits


def test_no_identity_leak():
    over = {k: n for k, n in count_hits().items() if n > ALLOW.get(k, 0)}
    assert over == {}, "rò danh tính / vượt số miễn trừ: " + ", ".join(
        f"{f} [{k}] {n} > {ALLOW.get((f, k), 0)}" for (f, k), n in sorted(over.items()))


def test_allowlist_is_not_stale():
    """Mục miễn trừ không còn dùng tới thì phải gỡ — cửa mở sẵn là cửa sẽ bị lợi dụng."""
    hits = count_hits()
    stale = [k for k in ALLOW if k not in hits and (ROOT / k[0]).exists()]
    assert stale == [], f"mục ALLOW không còn khớp gì, gỡ đi: {stale}"


def test_patterns_catch_their_target(tmp_path):
    """Đột biến: mỗi mẫu phải bắt được chuỗi nó nhắm tới (không để regex hỏng thành xanh giả)."""
    samples = {
        "profile-a": s(109, 121, 45, 118, 111, 105, 99, 101),
        "profile-b": "--profile " + s(97, 45, 116, 117, 110),
        "ten-nguoi": "anh " + s(0x110, 0x1EE9, 0x63) + " viết",
        "tien-to-pipeline": s(78, 69, 87, 83, 95) + "X",
        "tac-gia": s(68, 117, 99, 32, 78, 103, 117, 121, 101, 110),
        "duong-may-win": s(67, 58, 92, 85, 115, 101, 114, 115, 92) + "x",
        "duong-may-posix": "/home/someone/",
    }
    for key, text in samples.items():
        assert re.search(PATTERNS[key], text, flags=re.IGNORECASE), key
    # "đạo đức" (chữ thường) không phải tên người
    assert not re.search(PATTERNS["ten-nguoi"], s(0x111, 0x1EA1, 0x6F, 32, 0x111, 0x1EE9, 0x63),
                         flags=re.IGNORECASE)
