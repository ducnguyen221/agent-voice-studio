# Dùng Agent Voice Studio với Claude Code

Muốn agent cài giúp: dán prompt trong [INSTALL.md](../../INSTALL.md#prompt-copy-dán) vào Claude
Code. Tự cài: làm theo [START-HERE.md](../../START-HERE.md) (clone, venv, `voice-studio init`,
`voice-studio doctor`) — chạy được trên Windows và macOS.

## Hai cách để Claude thấy skill

1. **Mở thư mục repo** trong Claude Code. Claude đọc `CLAUDE.md` → `AGENTS.md` → skill
   `skills/voice-routing/SKILL.md`. Không cần đăng ký gì.
2. **Cài plugin** (tuỳ chọn — để skill có mặt cả khi bạn mở thư mục khác). Lệnh ghi vào cấu hình
   người dùng của Claude Code, nên hỏi người dùng trước:

   ```bash
   claude plugin marketplace add ducnguyen221/agent-voice-studio
   claude plugin install agent-voice-studio@agent-voice-studio
   ```

   Gỡ: `claude plugin uninstall agent-voice-studio@agent-voice-studio`, rồi
   `claude plugin marketplace remove agent-voice-studio`.

Plugin chỉ mang skill. Tổng hợp giọng vẫn cần package `voice-studio` đã cài trong venv engine
và một trạm giọng — `voice-studio doctor` cho biết còn thiếu gì.

## MCP (tuỳ chọn)

Package có MCP server (`voice-studio mcp`, cần `pip install -e ".[mcp]"`) với 8 công cụ như
`synthesize_speech`, `list_voice_profiles`. Claude Code không cần nó — gọi lệnh `voice-studio`
trong terminal là đủ. Muốn đăng ký thì dùng lệnh `claude mcp add` của Claude Code, trỏ tới
**python của venv engine** với tham số `-m voice_studio mcp`.

## Kiểm

Trong phiên mới: nhờ Claude chạy `voice-studio doctor` và đọc từng dòng. `claude plugin list`
cho biết plugin đã cài chưa.
