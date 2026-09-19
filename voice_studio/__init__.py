"""voice_studio — engine mẫu chạy giọng quanh OmniVoice, cài được như một package.

Bốn module lõi, nạp riêng lẻ (import package này KHÔNG kéo torch vào):

    voice_studio.profiles   kho profile giọng: liệt kê, mặc định, clone prompt có cache
    voice_studio.engine     nạp model (cuda → mps → cpu), seed, tổng hợp, ghi file, chuẩn hoá
    voice_studio.av         ghép giọng vào video, trộn nhạc nền
    voice_studio.bgm        thư viện nhạc nền: đọc bgm-library.json, chọn style

`API_VERSION` là phiên bản HỢP ĐỒNG (semver) mà pipeline khác ghim tối thiểu — tách khỏi
phiên bản phát hành của repo. Đổi chữ ký hàm công khai ⇒ tăng số đầu.
"""

__version__ = "0.2.0.dev0"
API_VERSION = "1.0.0"

__all__ = ["API_VERSION", "__version__"]
