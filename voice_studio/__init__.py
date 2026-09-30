"""voice_studio — engine mẫu chạy giọng quanh OmniVoice, cài được như một package.

Bốn module lõi, nạp riêng lẻ (import package này KHÔNG kéo torch vào):

    voice_studio.profiles   kho profile giọng: liệt kê, mặc định, clone prompt có cache
    voice_studio.engine     nạp model (cuda → mps → cpu), seed, tổng hợp, ghi file, chuẩn hoá
    voice_studio.av         ghép giọng vào video, trộn nhạc nền
    voice_studio.bgm        thư viện nhạc nền: đọc bgm-library.json, chọn style

`API_VERSION` là phiên bản HỢP ĐỒNG (semver) mà pipeline khác ghim tối thiểu — tách khỏi
phiên bản phát hành của repo. Đổi chữ ký hàm công khai ⇒ tăng số đầu; thêm khoá/tính năng mà
không phá cái cũ ⇒ tăng số giữa.

Trong JSON của `speak` / `narrate` / `doctor`: khoá `voice_studio` LUÔN là `API_VERSION` (hợp đồng
để ghim), khoá `version` là `__version__` (bản phát hành, để truy lỗi). Không bao giờ đảo nghĩa.
"""

__version__ = "0.3.2"
API_VERSION = "1.1.0"

__all__ = ["API_VERSION", "__version__"]
