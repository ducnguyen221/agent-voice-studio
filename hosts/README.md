# Chọn ứng dụng AI để dùng Agent Voice Studio

"Host" là ứng dụng chạy AI agent. Cách dễ nhất: dán prompt trong
[INSTALL.md](../INSTALL.md#prompt-copy-dán) vào ứng dụng bạn đang dùng — agent tự làm đúng các
bước cho host đó. Tự cài thì theo [START-HERE.md](../START-HERE.md) rồi đọc trang của host bên dưới.

| Bạn dùng | Có gì | Đăng ký | Hướng dẫn |
|---|---|---|---|
| Claude Code | skill `voice-routing` + lệnh `voice-studio` | plugin marketplace (tuỳ chọn) | [Claude Code](claude/README.md) |
| Codex (CLI và desktop) | skill + lệnh `voice-studio` | plugin marketplace (tuỳ chọn) | [Codex](codex/README.md) |
| Antigravity | đọc `AGENTS.md` + skill trong repo | không cần | [Antigravity](antigravity/README.md) |
| Claude Desktop (tab chat) | **chỉ công cụ MCP** nếu bạn tự đăng ký; không skill | sửa tay cấu hình MCP | [Claude Desktop](claude-desktop/README.md) |

## Ba điều giống nhau ở mọi host

- **Lệnh là `voice-studio`, chạy bằng python của venv đã cài package.** Agent gọi lệnh trong
  terminal của host; không có dịch vụ nền nào phải chạy.
- **Trạm giọng tách khỏi host.** Trạm ở `<repo>/workspace/` (mặc định) hoặc nơi `VOICE_STATION`
  trỏ tới. Đổi host không đụng tới giọng của bạn. Kiểm bằng `voice-studio doctor`.
- **Skill đọc từ repo.** Mở thư mục repo trong host là agent thấy `AGENTS.md` và
  `skills/voice-routing/SKILL.md`. Plugin chỉ là đường tắt để skill có mặt khi bạn mở thư mục
  KHÁC; nó không thay được lệnh `voice-studio`, vẫn phải cài package.

## Đăng ký ở cấp người dùng

Plugin marketplace và mục MCP (nếu có) ghi vào cấu hình **của người dùng** trên máy, không vào
file trong repo. Repo này **không tự ghi** cấu hình host nào: mọi đăng ký do lệnh của chính host
thực hiện, bạn thấy và duyệt từng lệnh. `voice-studio uninstall` vì thế chỉ **in** lệnh gỡ plugin
của từng host, không tự sửa cấu hình host.

## Trạng thái kiểm trên host thật

| Host | Cài plugin | Skill được nạp | MCP |
|---|---|---|---|
| Claude Code | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED |
| Codex | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED |
| Antigravity | không áp dụng | NOT_CHECKED (đọc thẳng từ repo) | NOT_CHECKED |
| Claude Desktop | không áp dụng | không hỗ trợ | NOT_CHECKED |

`NOT_CHECKED` nghĩa là chưa ai lần theo đường đó trên host thật trong đợt phát hành này — không
phải là hỏng. Bộ test tự động chỉ chứng minh lệnh `voice-studio`, trạm và hợp đồng gọi.
