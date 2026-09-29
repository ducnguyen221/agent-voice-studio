# Lịch sử phát hành

Mới nhất trước. Mỗi mục là thứ **người dùng** thấy khác đi; chi tiết từng thay đổi nằm trong lịch
sử git. Số phiên bản ở đây, trong `pyproject.toml`, `voice_studio/__init__.py` và ba manifest
plugin luôn cùng một số — `tests/test_version_sync.py` đỏ nếu lệch.

## 0.3.0 — chưa ghi ngày (điền khi tag)

**Cài đặt cho agent, hai hệ điều hành.**

- `INSTALL.md` ở gốc repo: hướng dẫn dành cho AI agent (Windows và macOS) kèm prompt copy-dán
  tiếng Việt và tiếng Anh. Agent phải hỏi trước khi cài phần mềm, tải engine, hay chọn chỗ đặt trạm.
- `START-HERE.md`, `AGENTS.md` (+ `CLAUDE.md`, `GEMINI.md` trỏ về), `hosts/` cho Claude Code, Codex,
  Antigravity, Claude Desktop; `docs/troubleshooting.md`; trang web `/install/`.
- **Trạm mặc định là `<repo>/workspace/`** khi không đặt biến nào — không còn tự chọn `~/.voice`.
  `~/.voice` chỉ được dùng khi bạn đã chọn nó hoặc nó đã là một trạm. Cài dạng wheel mà chưa đặt
  `VOICE_STATION`: lệnh cần trạm dừng với mã 3 kèm cách đặt.
- Lệnh mới `voice-studio uninstall`: gỡ package và hook `pre-commit`, **giữ** trạm và giọng;
  `--dry-run` để xem trước.
- `doctor` có bốn trạng thái `PASS` / `WARN` / `FAIL` / `NOT_CHECKED`; JSON thêm mức
  `not_checked` và danh sách `not_checked` (các mức cũ giữ nguyên tên). Dòng mới `samples` và
  `synthesis`.
- `samples/`: một câu tiếng Việt ngắn ở dạng thô (4 bẫy phát âm đã đo) và dạng viết lại, cùng hình
  dạng JSON của `speak --json`. Doctor xác minh offline.
- Sửa: tài liệu từng bảo `OMNIVOICE_ONLINE=1 voice-studio doctor` để tải weights — doctor không
  bao giờ tải gì; lần tổng hợp đầu mới tải. Lệnh `init` in ra giờ đúng cú pháp PowerShell trên
  Windows.
- Phần phụ `engine` giữ `transformers` trong khoảng đã chạy thật (`>=5.10.2,<5.18`), không ghim
  cứng một số; cài engine bằng `pip install "<repo>[engine]"`. Doctor in phiên bản transformers và
  `[WARN]` khi nó nằm ngoài khoảng.
- Cài package có **một** luật, ở `docs/INSTALL.md` mục 3: máy phát triển `pip install -e`, máy
  chạy lịch cài **bản sao** (không `-e`) để sửa hay `git pull` repo không đổi lượt đang chạy; có
  lệnh Windows và macOS. `voice-studio update` trên bản sao in lại lệnh cài để mã mới vào venv.

## 0.2.0 — 2026-09-22

**Engine thành package, clone là chạy.**

- Engine giọng thành package cài được `voice_studio` với lệnh `voice-studio`; mã thoát là hợp đồng
  (`2` cấu hình sai, `3` thiếu engine) và một dòng JSON cuối stdout.
- `embedded` là chế độ mặc định: clone repo rồi chạy là đường bình thường. Trạm và bí mật nằm đâu,
  chuyển thế nào: `voice-studio migrate`.
- Cứng hơn: nhập gói từ chối thành phần mang ký tự ổ đĩa ở bất kỳ đoạn nào và kiểm lại sau khi
  phân giải đường thật; xuất gói từ chối thứ trông như bí mật; ba biến môi trường không còn lặng
  lẽ trỏ trạm đi chỗ khác.
- CI chạy trên Windows và macOS.

## 0.1.0 — 2026-08-26

Bản đầu: bộ công cụ tạo và quản lý giọng cho AI agent — đào sắc thái từ bản ghi dài, sáu cổng
kiểm clip tham chiếu, profile nhiều sắc thái điều khiển bằng marker, bảng phát âm tiếng Việt đã đo.
