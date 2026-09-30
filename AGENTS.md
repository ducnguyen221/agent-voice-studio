# AGENTS.md — Agent Voice Studio

> File hướng dẫn CHUẨN cho mọi AI agent (Claude Code · Codex · Google Antigravity · bất kỳ công
> cụ nào đọc AGENTS.md). `CLAUDE.md` và `GEMINI.md` chỉ là con trỏ về file này — sửa Ở ĐÂY.

## 0. Ranh giới: mã ở repo, giọng ở trạm

**Mã, skill và tài liệu chạy từ repo này. Dữ liệu riêng sống ở TRẠM GIỌNG, ngoài git.** Không
chép skill hay engine sang trạm; không đưa giọng vào repo.

| Ở đâu | Chứa gì |
|---|---|
| Repo (git theo dõi) | package `voice_studio`, lệnh `voice-studio`, skill `skills/voice-routing/`, tài liệu, test |
| Trạm giọng (git bỏ qua) | venv engine, profile giọng (`omnivoice/voices/`), nhạc nền, output (`out/`), `station.json` |

Trạm nằm ở đâu — mọi lệnh dùng chung một thứ tự (chi tiết `docs/WORKSPACE.md`):
`VOICE_STATION` → `studio.local.json` do `init` ghi → **mặc định `<repo>/workspace/`** (bị git bỏ
qua). Chưa biết trạm ở đâu thì chạy `voice-studio doctor`, dòng `station` ghi đường và nguồn.

`workspace/` là dữ liệu riêng dù nằm trong checkout: không commit, không đóng gói. Repo **không
chứa audio nào**; `.gitignore`, hook `pre-commit` (chế độ embedded) và `tests/test_no_identity_leak.py`
chặn file audio/model, tên profile thật và đường dẫn máy.

## 1. Cài đặt

Người dùng nhờ cài: làm theo **[INSTALL.md](INSTALL.md)** từ mục 0 (luật an toàn) tới mục cuối
(báo cáo). Tự gõ lệnh: [START-HERE.md](START-HERE.md). Từng host: [hosts/README.md](hosts/README.md).

Hai điều không được làm thay người dùng:

- **Chọn chế độ trạm.** `voice-studio init` không có người trả lời thì in bảng hai lựa chọn rồi
  thoát **mã 2, chưa ghi gì**. Trình nguyên bảng đó cho người dùng, chờ họ chọn, rồi chạy lại với
  `--mode embedded|separate` (hoặc `--yes` = embedded, khuyến nghị).
- **Tải engine.** torch (CUDA ~2,5 GB, macOS arm64 ~130 MB) và weights (~3,3 GB, giấy phép
  **CC-BY-NC**) chỉ tải khi người dùng đồng ý. Khung (CLI, trạm, test) chạy được không cần chúng.

## 2. Làm việc với giọng

Đọc `skills/voice-routing/SKILL.md` trước — nó chỉ nạp **đúng một** reference cho bước hiện tại.
Bốn luật đè mọi thứ (đầy đủ trong SKILL.md): đo chứ đừng tin tai · ghim seed · clip tham chiếu hỏng
đầu độc mọi thứ · **chỉ clone giọng của chính mình hoặc người đã đồng ý bằng văn bản** (`clone` đòi
cờ `--consent`).

| Việc | Lệnh |
|---|---|
| Kiểm trạm, biết còn thiếu gì | `voice-studio doctor` (`--json` cho máy đọc) |
| Đọc text ra audio (hợp đồng ổn định) | `voice-studio speak --file script.txt --out out.mp3 --json` |
| Dựng profile từ bản ghi đã được đồng ý | `voice-studio make-profile …` · `voice-studio lab mine` rồi `lab build` |
| Chuyển máy | `voice-studio export --personal --out <ngoài trạm>/voice.zip` → `voice-studio import` |
| Gỡ | `voice-studio uninstall --dry-run` rồi `--yes` (giữ trạm) |

Output đặt trong trạm (`<trạm>/out/`) hoặc nơi người dùng chỉ, **không bao giờ** trong cây git.

**Hợp đồng cho pipeline khác** (`speak`, `narrate`, `doctor`): mã thoát `0` ok · `1` lỗi engine ·
`2` gọi/cấu hình sai · `3` trạm/engine chưa cài; với `--json`, dòng cuối stdout là đúng một dòng
JSON, log ra stderr. Đổi khoá JSON hay mã thoát = tăng số đầu của `API_VERSION`.

## 3. Quy ước khi sửa mã repo này

- Chạy `python -m pytest -q` trước khi báo xong. Test không cần torch/GPU (engine giả trong
  `tests/conftest.py`), dùng trạm tạm và HOME giả — **không bao giờ** đọc trạm thật của máy.
- Mã phải chạy trên **Windows và macOS**: đường dẫn qua `os.path`/`pathlib`, không cứng `C:\`,
  không `Scripts\python.exe` cố định (chọn theo `os.name`), không `cmd /c`, không registry.
- Đổi phiên bản: sửa đủ `pyproject.toml`, `voice_studio/__init__.py` và 3 manifest plugin —
  `tests/test_version_sync.py` đỏ nếu lệch. Thêm/bớt lệnh CLI: sửa README, README.vi, trang
  `docs/index.html` — `tests/test_docs_drift.py` bắt chỗ quên.
- Không ghi tên người, tên profile thật, đường dẫn máy vào file được theo dõi.

## 4. File nào host nào đọc

| Host | Đọc | Skill |
|---|---|---|
| Claude Code | `CLAUDE.md` → file này | plugin (`.claude-plugin/`) hoặc đọc thẳng `skills/voice-routing/SKILL.md` |
| Codex | `AGENTS.md` | plugin (`.codex-plugin/`, khoá `skills`) hoặc đọc thẳng skill |
| Antigravity | `GEMINI.md` → file này | đọc thẳng skill (thư mục skill riêng của host chưa kiểm) |
| Claude Desktop (tab chat) | — | không có skill; chỉ công cụ MCP nếu người dùng tự đăng ký |
