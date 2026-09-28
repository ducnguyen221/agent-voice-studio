# Dùng Agent Voice Studio với Claude Desktop (tab chat)

Tab chat của Claude Desktop **không nạp skill** từ repo và **không có terminal** để chạy
`voice-studio`. Thứ duy nhất nó dùng được là **công cụ MCP** — và repo này không tự đăng ký MCP
cho bạn. Muốn đủ quy trình (dựng profile, viết kịch bản, kiểm clip), dùng
[Claude Code](../claude/README.md), [Codex](../codex/README.md) hoặc
[Antigravity](../antigravity/README.md).

## Nếu vẫn muốn công cụ MCP trong tab chat

1. Cài theo [START-HERE.md](../../START-HERE.md) tới khi `voice-studio doctor` không còn lỗi, rồi
   cài thêm phần MCP vào **venv engine**: `pip install -e ".[mcp]"`.
2. Mở cấu hình của Claude Desktop từ **Settings → Developer → Edit Config** (ứng dụng tự mở đúng
   file nó dùng; sao lưu file trước khi sửa). Thêm một mục trong `mcpServers`:

   ```json
   "omnivoice-tts": {
     "command": "<python của venv engine>",
     "args": ["-m", "voice_studio", "mcp"],
     "env": { "VOICE_STATION": "<thư mục trạm>" }
   }
   ```

   `<python của venv engine>`: `<trạm>/omnivoice/.venv/Scripts/python.exe` trên Windows,
   `<trạm>/omnivoice/.venv/bin/python` trên macOS. Đặt `VOICE_STATION` ngay trong mục vì Claude
   Desktop không chạy trong thư mục repo.
3. Thoát hẳn Claude Desktop (khay hệ thống / menu ứng dụng) rồi mở lại; tìm `omnivoice-tts` trong
   danh sách công cụ, hỏi thử "gọi `get_status`".

Tám công cụ: `synthesize_speech`, `clone_voice`, `narrate_video`, `make_voice_profile`,
`list_voice_profiles`, `set_default_voice`, `list_voice_options`, `get_status`. `clone_voice` và
`make_voice_profile` chỉ dùng cho giọng **đã được chủ giọng đồng ý**.

Đường này chưa được lần theo trên host thật trong đợt phát hành này (NOT_CHECKED). Gỡ: xoá mục
`omnivoice-tts` khỏi cấu hình rồi mở lại ứng dụng. Chẩn đoán trạm: `voice-studio doctor` trong
một terminal thường.
