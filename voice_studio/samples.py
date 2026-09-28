"""samples.py — bài mẫu cố định của repo và bộ soi "bẫy phát âm" chạy offline.

`samples/` trong repo có một câu tiếng Việt ngắn ở hai dạng:

    cau-ngan.txt         văn bản THÔ — cố ý chứa đủ loại bẫy đã đo (giờ, ngày, phiên bản dính
                         viết tắt, tên miền)
    cau-ngan.script.txt  cùng câu đã VIẾT LẠI theo `vietnamese-tts-script.md` — không còn bẫy
    speak-expected.json  hình dạng kết quả `voice-studio speak --json` (khoá, không phải số đo)

`traps(text)` là phần máy kiểm được của bảng phát âm: nó KHÔNG phát âm gì, chỉ bắt những dạng
viết mà engine đã được đo là đọc sai. `doctor` dùng nó để xác minh bài mẫu mà không cần mạng,
torch hay model — và agent dùng được nó để soát kịch bản trước khi tổng hợp.
"""
import json
import os
import re

from . import _env

SAMPLES_DIR = "samples"
RAW = "cau-ngan.txt"
SCRIPT = "cau-ngan.script.txt"
EXPECTED = "speak-expected.json"
MAX_CHARS = 200

# Mỗi mẫu ứng với MỘT dòng đã đo trong bảng phát âm (skills/voice-routing/references/
# vietnamese-tts-script.md §2). Thêm mẫu ở đây là thêm luật: phải có số đo đi kèm ở đó trước.
TRAPS = {
    "gio": (r"\b\d{1,2}:\d{2}\b", "giờ 14:30 → viết `14 giờ 30`"),
    "ngay": (r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "ngày 22/8/2026 → viết `22 tháng 8 năm 2026`"),
    "phien-ban": (r"\b[A-Z]{2,}[- ]?\d+\.\d+\b", "`GPT 5.2` dính thành một cụm → `GPT phiên bản 5.2`"),
    "ten-mien": (r"\b\w+\.(?:ai|com|io|vn|net|org)\b", "`Z.ai` → viết `Z chấm AI`"),
}


def traps(text):
    """-> [(khoá, đoạn khớp, cách sửa)] cho mọi bẫy trong `text` (rỗng = không thấy bẫy nào)."""
    out = []
    for key, (pat, fix) in TRAPS.items():
        for m in re.finditer(pat, text, flags=re.IGNORECASE if key == "ten-mien" else 0):
            out.append((key, m.group(0), fix))
    return out


def samples_dir(repo=None):
    repo = repo or _env.repo_root()
    d = os.path.join(repo, SAMPLES_DIR) if repo else None
    return d if d and os.path.isdir(d) else None


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def check(repo=None):
    """Xác minh bài mẫu offline -> (ok, chi tiết). Ném FileNotFoundError nếu không có samples/."""
    from .speak import RESULT_KEYS
    d = samples_dir(repo)
    if not d:
        raise FileNotFoundError("không có thư mục samples/ (bản cài không kèm repo)")
    raw, script = _read(os.path.join(d, RAW)), _read(os.path.join(d, SCRIPT))
    with open(os.path.join(d, EXPECTED), "r", encoding="utf-8") as f:
        expected = json.load(f)
    problems = []
    if not raw or len(raw) > MAX_CHARS:
        problems.append(f"{RAW} phải có 1–{MAX_CHARS} ký tự")
    if not traps(raw):
        problems.append(f"{RAW} không còn bẫy nào — bài mẫu mất tác dụng")
    left = traps(script)
    if left:
        problems.append(f"{SCRIPT} còn bẫy: " + ", ".join(f"{k} '{s}'" for k, s, _ in left))
    if set(expected) != set(RESULT_KEYS):
        problems.append(f"{EXPECTED} lệch hợp đồng speak: {sorted(expected)} ≠ {sorted(RESULT_KEYS)}")
    if problems:
        return False, "; ".join(problems)
    return True, f"{len(traps(raw))} bẫy trong bản thô, 0 trong bản viết lại, hợp đồng speak khớp"
