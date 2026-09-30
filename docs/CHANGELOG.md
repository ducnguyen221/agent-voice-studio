# Lịch sử phát hành

Mới nhất trước. Mỗi mục là thứ **người dùng** thấy khác đi; chi tiết từng thay đổi nằm trong lịch
sử git. Số phiên bản ở đây, trong `pyproject.toml`, `voice_studio/__init__.py` và ba manifest
plugin luôn cùng một số — `tests/test_version_sync.py` đỏ nếu lệch.

## 0.3.1 — 2026-09-30

**Chạy ổn trên Mac mini (máy embedded), Windows giữ nguyên.**

- `doctor` dòng `bgm-library` giờ kiểm cả **file nhạc**: style khai trong `bgm-library.json` mà
  thiếu `<style>.mp3` là `[WARN]` kèm tên style thiếu — trước đây chỉ kiểm file json, và pipeline
  chọn đúng style đó chết ở bước ghép sau khi đã tốn cả lượt tổng hợp. Repo không có lệnh sinh
  nhạc; cách tự sinh (và giấy phép CC-BY-NC của weights MusicGen) ở `docs/bgm-generation.md`.
- Tên profile so theo Unicode **NFC**: file tên có dấu ở dạng NFD (chép từ gói/máy khác) giờ khớp
  tên viết trong cấu hình; `list_profiles()` / `get_default()` trả tên NFC. Không đổi tên file nào.
- Luật cài package có thêm dòng **máy embedded**: giọng cài vào venv của repo video thì luôn
  `pip install -e` (trùng `agent-video-studio/INSTALL.md` mục 5b); bản sao chỉ dành cho xưởng
  Windows chạy lịch có trạm giọng riêng. `docs/INSTALL.md` mục 3.
- `voice-studio init` nhận ra khi `voice_studio` đang chạy từ venv của dự án khác (vd `.venv` của
  repo video): không còn bảo tạo `<trạm>/omnivoice/.venv` hay tải lại weights đã có trong cache.
- Tài liệu cài: macOS dùng `python3.12` (không phải `python3` = 3.9), ghi chú uv/pyenv; dung lượng
  tách theo máy — torch CUDA ~2,5 GB, macOS arm64 ~130 MB, weights ~3,3 GB.
- JSON của `speak`, `narrate`, `doctor` (và `get_status` của MCP) thêm khoá `version` = phiên bản
  package; `voice_studio` **vẫn** là phiên bản hợp đồng (`API_VERSION`, nay `1.1.0` vì thêm khoá —
  không phá khoá cũ). Bên gọi ghim theo `voice_studio`, truy lỗi theo `version`.

## 0.3.0 — 2026-09-29

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
