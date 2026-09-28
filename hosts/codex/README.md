# Dùng Agent Voice Studio với Codex

Muốn agent cài giúp: dán prompt trong [INSTALL.md](../../INSTALL.md#prompt-copy-dán) vào Codex
(CLI hoặc desktop). Tự cài: làm theo [START-HERE.md](../../START-HERE.md) — chạy được trên
Windows và macOS.

## Hai cách để Codex thấy skill

1. **Mở thư mục repo** làm project (Codex desktop: tin cậy thư mục). Codex đọc `AGENTS.md`, file
   này chỉ tới `skills/voice-routing/SKILL.md`. Không cần đăng ký gì.
2. **Cài plugin** (tuỳ chọn). Manifest `.codex-plugin/plugin.json` khai `skills: ./skills/`. Lệnh
   ghi vào cấu hình người dùng của Codex, nên hỏi người dùng trước:

   ```bash
   codex plugin marketplace add ducnguyen221/agent-voice-studio
   codex plugin install agent-voice-studio@agent-voice-studio
   ```

   Tên lệnh con có thể khác giữa các bản Codex; `codex --help` là nguồn đúng. Đường này chưa
   được lần theo trên host thật trong đợt phát hành này (NOT_CHECKED).

## Sandbox của Codex

Tổng hợp giọng lần đầu cần mạng (tải weights) và ghi ra cache Hugging Face ngoài thư mục repo.
Sandbox của Codex có thể chặn cả hai. **Không** đổi thiết lập sandbox để lách: đưa đúng lệnh
cho người dùng tự chạy trong terminal thường, rồi quay lại với kết quả.

## Kiểm

Trong phiên mới: nhờ Codex chạy `voice-studio doctor` và chép nguyên từng dòng. Lỗi `station`
hay `torch` thì làm tiếp theo INSTALL.md; `NOT_CHECKED` không phải lỗi.
