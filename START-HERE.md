# Bắt đầu ở đây

Agent Voice Studio là quy trình dựng và dùng **giọng đọc của chính bạn** cho AI agent, chạy trên
Windows và macOS. Repo chứa mã và phương pháp; giọng, nhạc nền, output nằm ở **trạm giọng** —
mặc định `workspace/` trong repo, bị git bỏ qua. Repo không chứa một file audio nào.

## Cách nhanh: nhờ agent cài

Dán khối này vào Claude Code, Codex hoặc Antigravity (luật và từng bước agent làm: [INSTALL.md](INSTALL.md)):

```text
Hãy cài Agent Voice Studio lên máy này (Windows hoặc macOS) cho chính ứng dụng AI bạn đang chạy.
Nguồn duy nhất: https://github.com/ducnguyen221/agent-voice-studio
Đọc trước rồi làm đúng từng bước trong hướng dẫn dành cho agent:
https://raw.githubusercontent.com/ducnguyen221/agent-voice-studio/main/INSTALL.md
(không mở được link thì clone repo rồi đọc file INSTALL.md trong đó).
Hỏi tôi trước khi cài phần mềm, cần quyền admin, tải engine nặng vài GB hoặc chọn chỗ đặt trạm giọng.
Không đổi chính sách hệ thống, không tải script về rồi chạy, không đọc hay ghi mật khẩu, khóa, file .env.
Chạy voice-studio doctor và chép nguyên từng dòng; gặp lỗi thì dừng và giải thích bằng lời thường.
Kết thúc bằng tóm tắt: đường dẫn repo, chỗ đặt trạm, kết quả doctor, phần mềm đã cài, việc tôi làm tiếp.
```

## Tự cài

Cần Git và Python 3.10–3.13 (khuyến nghị 3.12); ffmpeg nên có. Clone vào thư mục cục bộ, **không**
để trong OneDrive/iCloud/Dropbox:

```bash
git clone https://github.com/ducnguyen221/agent-voice-studio "$HOME/agent-voice-studio"
cd "$HOME/agent-voice-studio"
```

| Bước | Windows (PowerShell) | macOS (Terminal) |
|---|---|---|
| venv nhẹ | `py -3.12 -m venv .venv` | `python3.12 -m venv .venv` (không dùng `python3` = 3.9 của máy) |
| cài lệnh | `.\.venv\Scripts\python.exe -m pip install -e .` | `.venv/bin/python -m pip install -e .` |
| gọi lệnh | `.\.venv\Scripts\voice-studio.exe …` | `.venv/bin/voice-studio …` |

Rồi, với `voice-studio` là lệnh ở dòng cuối bảng:

1. `voice-studio init` — trình bảng hai chỗ đặt trạm; Enter = `embedded` (trong repo, khuyến nghị).
2. `voice-studio doctor` — đọc từng dòng. Chưa cài engine thì `[FAIL] torch/omnivoice` là đúng;
   dòng `[PASS] samples` xác nhận bài mẫu ([samples/README.md](samples/README.md)).
3. Engine (torch: CUDA ~2,5 GB, macOS arm64 ~130 MB · weights ~3,3 GB, giấy phép weights **không thương mại**): làm đúng các lệnh
   `init` in ra, chi tiết ở [install-omnivoice.md](skills/voice-routing/references/install-omnivoice.md).
   Máy chạy lịch cài **bản sao** thay cho `-e`: [docs/INSTALL.md](docs/INSTALL.md) mục 3.
4. Thử đọc: `voice-studio speak --file samples/cau-ngan.script.txt --instruct "female, young adult" --out workspace/out/thu.wav --json`
   (lần đầu đặt `OMNIVOICE_ONLINE=1` để tải weights).

Giọng của chính bạn: `voice-studio make-profile` hoặc bộ `voice-studio lab` — chỉ dùng bản ghi của
bạn hoặc của người đã đồng ý bằng văn bản. Toàn bộ quy trình: [GUIDE.vi.md](GUIDE.vi.md).

## Chuyển máy, cập nhật, gỡ

- Chuyển máy: `voice-studio export --personal --out <ngoài trạm>/voice.zip`, máy mới `init` rồi `voice-studio import voice.zip`.
- Cập nhật: `voice-studio update` (chỉ `git pull --ff-only`, không xoá gì).
- Gỡ: `voice-studio uninstall --dry-run` để xem, rồi `python -m voice_studio uninstall --yes` —
  gỡ phần mềm, **giữ** trạm và giọng.

Gặp lỗi: [docs/troubleshooting.md](docs/troubleshooting.md). Từng ứng dụng AI: [hosts/README.md](hosts/README.md).
