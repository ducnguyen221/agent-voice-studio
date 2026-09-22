# Làm sạch clip mẫu (`voice-studio clean`)

Clip mẫu bẩn (nhạc nền, tiếng vang, tiếng quạt) làm hỏng MỌI thứ clone ra từ nó. Công cụ này
tách giọng người khỏi nhạc rồi khử tạp âm, ra một file WAV sạch để đưa vào
`voice-studio make-profile`.

| Tầng | Công cụ | Việc | Venv |
|---|---|---|---|
| 1 | `audio-separator` (BS-Roformer) | tách vocal khỏi nhạc / tiếng động | `.venv-sep` |
| 2 | `clearvoice` (MossFormer2_SE_48K) | khử nhiễu + dereverb | `.venv-cv` |

Hai tầng cần **hai venv riêng** vì xung đột numpy (tầng 1 cần numpy ≥ 2, tầng 2 cần numpy < 2).
Không cài chung vào venv engine giọng.

## Thư mục công cụ

Mọi thứ nặng nằm ở **trạm**, không nằm trong repo:

```
<trạm giọng>/voice-clean/
    .venv-sep/      venv tầng 1
    .venv-cv/       venv tầng 2
    models/         model tầng 1 (tự tải lần đầu)
    checkpoints/    model tầng 2 (tự tải lần đầu)
```

Vị trí: `--clean-dir` → biến `VOICE_CLEAN_DIR` → `$VOICE_STATION/voice-clean` →
`~/.voice/voice-clean`.

## Cài đặt

Dùng Python 3.10–3.12. Thay `<dir>` bằng thư mục công cụ ở trên.

Windows (PowerShell):

```powershell
py -3.12 -m venv <dir>\.venv-sep
<dir>\.venv-sep\Scripts\python.exe -m pip install "audio-separator[cpu]" soundfile
py -3.12 -m venv <dir>\.venv-cv
<dir>\.venv-cv\Scripts\python.exe -m pip install clearvoice soundfile "numpy<2"
```

Có GPU NVIDIA thì cài `audio-separator[gpu]` thay cho `[cpu]`.

macOS / Linux:

```bash
python3.12 -m venv <dir>/.venv-sep
<dir>/.venv-sep/bin/python -m pip install "audio-separator[cpu]" soundfile
python3.12 -m venv <dir>/.venv-cv
<dir>/.venv-cv/bin/python -m pip install clearvoice soundfile "numpy<2"
```

**[chưa kiểm]** trên macOS Apple Silicon: bộ lệnh trên chưa được chạy thật trên máy Mac.
Nếu `clearvoice` không có bản dựng sẵn cho arm64, xem trang dự án của nó trước khi cài.

## Model (~821 MB, không vào repo)

Lần chạy đầu tiên cần mạng: tầng 1 tải `model_bs_roformer_ep_317_sdr_12.9755.ckpt` vào
`models/`, tầng 2 tải `MossFormer2_SE_48K` vào `checkpoints/`. Các lần sau chạy offline.
Tổng khoảng 821 MB. Muốn chuyển máy thì chép nguyên hai thư mục này sang, không cần tải lại.

`.gitignore` của repo chặn `*.ckpt`, `*.pt`, `*.onnx` — đừng bao giờ mở chặn để commit model.

## Dùng

```
voice-studio clean ghi_am.mp3                    # ra ghi_am_clean.wav cạnh file gốc
voice-studio clean ghi_am.mp3 --out sach.wav
voice-studio clean ghi_am.wav --enhance-only     # chỉ khử nhiễu (bản thu không có nhạc)
voice-studio clean nhac.mp3 --no-enhance         # chỉ tách vocal
```

Lệnh tự chạy lại bằng python của `.venv-sep` nếu venv hiện tại không có `audio-separator`,
và gọi tầng 2 bằng python của `.venv-cv` — người dùng không phải tự chuyển venv.

Mã thoát: 0 ok · 1 lỗi xử lý · 2 gọi sai · 3 thiếu venv/công cụ.
