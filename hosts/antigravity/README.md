# Dùng Agent Voice Studio với Antigravity

Muốn agent cài giúp: dán prompt trong [INSTALL.md](../../INSTALL.md#prompt-copy-dán) vào
Antigravity. Tự cài: làm theo [START-HERE.md](../../START-HERE.md) — chạy được trên Windows và
macOS.

## Skill

Antigravity không có plugin cho repo này. **Mở thư mục repo** làm workspace: agent đọc
`GEMINI.md` → `AGENTS.md` → `skills/voice-routing/SKILL.md`. Repo không có adapter trong thư mục
skill riêng của Antigravity; việc host tự phát hiện skill theo đường đó **chưa kiểm**
(NOT_CHECKED) — nếu agent không tự nạp, bảo nó: "đọc `skills/voice-routing/SKILL.md` trong repo
rồi làm theo".

## MCP (tuỳ chọn)

Không cần cho việc thường ngày — agent gọi lệnh `voice-studio` trong terminal. Muốn đăng ký MCP
server (`voice-studio mcp`, cần `pip install -e ".[mcp]"`) thì thêm một mục trỏ tới **python
của venv engine** với tham số `-m voice_studio mcp` qua màn cấu hình MCP của Antigravity. Chưa
kiểm trên host thật (NOT_CHECKED).

## Kiểm

Nhờ agent chạy `voice-studio doctor` và chép nguyên từng dòng vào báo cáo.
