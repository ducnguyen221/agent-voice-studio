---
title: Troubleshooting
summary: Symptom-first fixes for voice-studio on Windows and macOS - exit code 3, old variable names, offline weights, fp16 on Apple Silicon, PowerShell stderr, uninstall file locks.
audience: anyone whose voice-studio command or doctor line is not what they expected
---

# Gỡ vướng — tra theo triệu chứng

Bắt đầu luôn bằng `voice-studio doctor` (thêm `--json` nếu một chương trình khác đọc). Mỗi dòng
`[FAIL]`/`[WARN]` có một dòng `→` chỉ việc cần làm; trang này giải thích những trường hợp dòng đó
chưa đủ. `[NOT_CHECKED]` **không phải lỗi**: doctor nói thẳng điều nó không kiểm được.

## Mã thoát 3 — "trạm/engine chưa cài"

| Doctor báo | Nguyên nhân | Sửa |
|---|---|---|
| `[FAIL] station (chưa xác định)` | cài dạng wheel (không có repo) và chưa đặt `VOICE_STATION` | đặt `VOICE_STATION=<thư mục trạm>` rồi `voice-studio init --station <thư mục đó>` |
| `[FAIL] station <đường>` | trạm chưa dựng | `voice-studio init` |
| `[FAIL] voices` | trạm có nhưng thiếu `omnivoice/voices/` | `voice-studio init` (chạy lại an toàn, không đè gì) |
| `[FAIL] torch` / `omnivoice` | đang chạy bằng python không có engine | gọi bằng python của **venv engine** (`<trạm>/omnivoice/.venv`), hoặc cài engine theo [install-omnivoice.md](../skills/voice-routing/references/install-omnivoice.md) |
| `[FAIL] two-sources` | vừa có `<repo>/workspace/` vừa có trạm ngoài (biến hoặc `~/.voice`) | giữ **một** trạm: gộp dữ liệu, rồi xoá `workspace/` hoặc gỡ biến; hoặc `voice-studio migrate --to separate` |

Trạm nằm ở đâu khi không đặt gì: `<repo>/workspace/`. Thứ tự tìm đầy đủ ở
[WORKSPACE.md](WORKSPACE.md#thứ-tự-tìm-trạm-mọi-lệnh-dùng-chung-một-hàm).

## Tên biến cũ — `[WARN] env-name`

`OMNIVOICE_DIR` là tên cũ, trỏ **thư mục engine** (`<trạm>/omnivoice`), không phải gốc trạm. Vẫn
đọc được, nhưng đặt `VOICE_STATION=<gốc trạm>` rồi gỡ biến cũ. `NEWS_BGM*` tương tự → `VOICE_BGM*`.
`[WARN] station-source`: trạm `~/.voice` được nhận vì nó đã có sẵn — đặt `VOICE_STATION` trỏ vào
đó để lịch chạy và máy khác thấy cùng một trạm.

## Weights — offline theo mặc định

Engine chạy **offline** để lịch chạy không bao giờ treo vì mạng. Hệ quả:

- `[WARN] weights` sau khi vừa cài engine là **đúng**: doctor không bao giờ tải gì.
- Lần tổng hợp đầu (`speak`, `make-profile`…) chạy với `OMNIVOICE_ONLINE=1` cho riêng lệnh đó
  (zsh: đầu lệnh; PowerShell: `$env:OMNIVOICE_ONLINE = "1"` trước, `Remove-Item Env:OMNIVOICE_ONLINE` sau).
- Lỗi kiểu "không tìm thấy file trong cache" / "offline mode" ở lần đầu = quên bước trên.
- Weights nằm trong cache Hugging Face (`HF_HOME`), **không** trong trạm; chuyển máy thì tải lại.

## Apple Silicon (MPS)

- fp16 trên MPS với transformers 5.17: nạp weights song song có thể sập tiến trình. Package tự đặt
  `HF_DEACTIVATE_ASYNC_LOAD=1` trên macOS; đừng gỡ biến đó.
- Chọn độ chính xác bằng `OMNIVOICE_DTYPE`; ép thiết bị bằng `OMNIVOICE_DEVICE` (`mps` · `cpu`).
- Tổng hợp giọng thật qua package trên Mac **chưa được kiểm** trong bản phát hành này — báo lại số
  đo nếu bạn chạy được.
- Cặp phiên bản đã đo: Windows + CUDA với torch 2.12/transformers 5.10.2 và torch 2.13/transformers
  5.17.0 (cài sạch 28/09); Mac spike với transformers 5.17.0.
- Vì vậy phần phụ `engine` ghim transformers theo **khoảng** đã đo (`>=5.10.2,<5.18`, nguồn duy
  nhất là `pyproject.toml`), không một số cứng: cài qua `pip install "<repo>[engine]"` là pip giữ
  bản trong khoảng. Doctor in phiên bản đang có và `[WARN] transformers` khi nó nằm ngoài khoảng
  (cài `omnivoice` trần thì pip kéo bản mới nhất, chưa ai đo) — cài lại phần phụ `engine` để về
  khoảng.

## Windows

- **`pip install torch` gãy với WinError 206 ("filename or extension is too long")**: Windows
  chưa bật đường dài và đường venv engine quá dài — torch có thư mục lồng ~160 ký tự bên trong
  venv. Doctor báo `[WARN] win-path` khi gốc venv dài hơn 80 ký tự. Torch lúc đó **cài dở**
  (doctor báo thiếu `torchgen`): xoá venv engine, đưa repo về đường ngắn
  (`<home>\agent-voice-studio`) hoặc đặt trạm `separate` ở thư mục ngắn, rồi cài lại.
  Bật `LongPathsEnabled` cần quyền quản trị — việc của bạn hoặc IT, không phải của agent.
- **PowerShell 5.1 và stderr:** đừng `2>&1` khi gọi `voice-studio` — mỗi dòng log (đi ra stderr)
  bị bọc thành lỗi và `$?` thành False dù mã thoát là 0. Đọc `$LASTEXITCODE`.
- **Console in chữ Việt ra rác:** đặt `PYTHONIOENCODING=utf-8`, hoặc đọc dòng JSON cuối (`--json`).
- **Gỡ báo `voice-studio.exe` đang bị giữ:** gọi `python -m voice_studio uninstall --yes` thay cho
  `voice-studio uninstall`.
- **Gọi exe có dấu nháy trong PowerShell** phải có `&` đứng trước: `& "<venv>\Scripts\python.exe" -m voice_studio doctor`.

## Repo trong thư mục đồng bộ đám mây — `[WARN] cloud-sync`

OneDrive/iCloud/Dropbox/Google Drive sẽ đẩy giọng trong `workspace/` và `.env` lên cloud, và hay
khoá file giữa lúc ghi. Chuyển trạm ra ngoài (`voice-studio migrate --to separate`) hoặc clone lại
repo vào thư mục cục bộ.

## Bài mẫu — `[WARN] samples`

File trong `samples/` bị sửa lệch kỳ vọng. `git status samples/` rồi `git checkout -- samples/`
nếu thay đổi không phải của bạn. Kỳ vọng cố định ở [samples/README.md](../samples/README.md).
